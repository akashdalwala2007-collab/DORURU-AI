#pragma once

#include <stdint.h>
#include <stdbool.h>
#include "board_pins.h"
#include "sensor_interface.h"

namespace doruru {
namespace motor {

/**
 * Validated movement direction enums.
 */
enum class Direction : uint8_t {
    STOP = 0,
    FORWARD = 1,
    REVERSE = 2,
    PIVOT_LEFT = 3,
    PIVOT_RIGHT = 4
};

/**
 * Result returned upon validating and applying a motion command.
 */
enum class CommandResult : uint8_t {
    ACCEPTED = 0,
    REJECTED_EMERGENCY_STOP_ACTIVE = 1,
    REJECTED_INVALID_DIRECTION = 2,
    REJECTED_SPEED_OUT_OF_BOUNDS = 3,
    REJECTED_DURATION_OUT_OF_BOUNDS = 4,
    REJECTED_NOT_INITIALIZED = 5
};

/**
 * Structured motion command envelope.
 * 
 * In accordance with DORURU architecture rules:
 * - Movement is strictly approximate and time-bounded (no encoders installed).
 * - Max duration is strictly capped at MAX_DURATION_MS (3000ms).
 */
struct MotionCommand {
    Direction direction;
    uint8_t speed_pwm;       // Target speed (MIN_SPEED_PWM to MAX_SPEED_PWM)
    uint32_t duration_ms;    // Duration in ms (MIN_DURATION_MS to MAX_DURATION_MS)
};

/**
 * Telemetry and status snapshot of the motor safety controller.
 */
struct ControllerStatus {
    Direction active_direction;
    uint8_t target_speed_pwm;
    uint8_t current_ramped_pwm;
    uint32_t remaining_duration_ms;
    bool is_emergency_stopped;
    bool is_timed_out;
    bool is_heartbeat_lost;
    bool is_initialized;
};

/**
 * Abstract GPIO and PWM hardware driver interface.
 * Enables dependency injection for both on-device ESP32 execution
 * and host-based native mock verification.
 */
class IGpioDriver {
public:
    virtual ~IGpioDriver() = default;
    virtual void setPinModeOutput(uint8_t pin) = 0;
    virtual void writeDigital(uint8_t pin, uint8_t level) = 0;
    virtual void writePwm(uint8_t pin, uint8_t duty_cycle) = 0;
    virtual uint32_t getMillis() = 0;
};

/**
 * DORURU Motor Controller & Local Safety Supervisor.
 * 
 * Hardware allocation:
 * - Motor A (Left):  IN1 = GPIO4 (D3), IN2 = GPIO3 (D2)
 * - Motor B (Right): IN3 = GPIO2 (D1), IN4 = GPIO1 (D0)
 * 
 * Safety invariants enforced locally:
 * 1. Startup default is strictly STOP; pins driven LOW.
 * 2. Emergency stop has highest priority and locks controller until explicit clear.
 * 3. Automatic stop watchdog terminates movement after duration elapses.
 * 4. Heartbeat watchdog stops motors if backend/Wi-Fi communication is lost.
 * 5. Software PWM slew-rate limiter smoothly ramps duty cycle to prevent
 *    inductive current inrush spikes and ESP32 brownout resets.
 * 6. Autonomous navigation is locked out (SensorProvider returns disabled).
 */
class MotorController {
public:
    // Safety Bounds
    static constexpr uint32_t MAX_DURATION_MS        = 3000; // 3.0s hard safety ceiling
    static constexpr uint32_t DEFAULT_DURATION_MS    = 1000; // 1.0s default
    static constexpr uint32_t MIN_DURATION_MS        = 50;   // 50ms min duration
    static constexpr uint8_t  MAX_SPEED_PWM          = 220;  // 86% duty cycle safety cap
    static constexpr uint8_t  MIN_SPEED_PWM          = 60;   // Minimum threshold to prevent stall
    static constexpr uint8_t  DEFAULT_SPEED_PWM      = 150;  // Safe default operating speed
    static constexpr uint32_t HEARTBEAT_TIMEOUT_MS   = 1500; // 1.5s loss-of-comm timeout
    static constexpr uint8_t  RAMP_STEP_PWM          = 15;   // PWM increment per 20ms tick
    static constexpr uint32_t RAMP_TICK_INTERVAL_MS  = 20;   // Ramp evaluation interval

    explicit MotorController(IGpioDriver& gpio_driver, 
                             sensors::ISensorProvider& sensor_provider);

    /**
     * Initializes motor driver pins to OUTPUT and forces immediate STOP state.
     */
    void init();

    /**
     * Executes a validated motion command.
     * Rejects invalid directions, out-of-bounds speeds, excessive durations,
     * or any command while an emergency stop is active.
     */
    CommandResult executeCommand(const MotionCommand& cmd);

    /**
     * Shorthand movement helpers (automatically validated).
     */
    CommandResult forward(uint8_t speed_pwm = DEFAULT_SPEED_PWM, 
                          uint32_t duration_ms = DEFAULT_DURATION_MS);
    CommandResult reverse(uint8_t speed_pwm = DEFAULT_SPEED_PWM, 
                          uint32_t duration_ms = DEFAULT_DURATION_MS);
    CommandResult pivotLeft(uint8_t speed_pwm = DEFAULT_SPEED_PWM, 
                            uint32_t duration_ms = DEFAULT_DURATION_MS);
    CommandResult pivotRight(uint8_t speed_pwm = DEFAULT_SPEED_PWM, 
                             uint32_t duration_ms = DEFAULT_DURATION_MS);
    void stop();

    /**
     * Emergency Stop: Highest priority safety command.
     * Instantly cuts all PWM outputs to 0, drives pins LOW, and engages
     * the emergency stop lockout flag.
     */
    void emergencyStop();

    /**
     * Clears emergency stop lockout, permitting subsequent movement commands.
     */
    void clearEmergencyStop();

    /**
     * Feeds the communication heartbeat watchdog.
     * Must be called whenever a valid backend or Wi-Fi message is received.
     */
    void feedHeartbeat();

    /**
     * Non-blocking periodic update loop.
     * Evaluates duration timeouts, communication loss, and PWM ramp updates.
     * Must be called regularly inside the main control loop.
     */
    void update();

    /**
     * Validates a motion command without applying it.
     */
    CommandResult validateCommand(const MotionCommand& cmd) const;

    /**
     * Returns current controller telemetry and safety status.
     */
    ControllerStatus getStatus() const;

private:
    IGpioDriver& gpio_;
    sensors::ISensorProvider& sensors_;

    bool initialized_{false};
    bool emergency_stopped_{false};
    bool timed_out_{false};
    bool heartbeat_lost_{false};

    Direction active_direction_{Direction::STOP};
    uint8_t target_speed_pwm_{0};
    uint8_t current_ramped_pwm_{0};

    uint32_t command_start_time_{0};
    uint32_t command_duration_ms_{0};
    uint32_t last_heartbeat_time_{0};
    uint32_t last_ramp_time_{0};

    void applyHardwareOutputs(Direction dir, uint8_t duty_cycle);
    void updateRamping(uint32_t now);
};

} // namespace motor
} // namespace doruru

