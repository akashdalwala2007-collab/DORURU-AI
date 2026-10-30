#include <iostream>
#include <map>
#include <string>
#include <cassert>
#include "motor_controller.h"
#include "sensor_interface.h"

using namespace doruru;
using namespace doruru::motor;
using namespace doruru::sensors;

/**
 * Mock GPIO driver tracking pin operations and simulated millisecond clock.
 */
class MockGpioDriver : public IGpioDriver {
public:
    std::map<uint8_t, bool> is_output;
    std::map<uint8_t, uint8_t> digital_state;
    std::map<uint8_t, uint8_t> pwm_duty;
    uint32_t simulated_millis{0};

    void setPinModeOutput(uint8_t pin) override {
        is_output[pin] = true;
    }

    void writeDigital(uint8_t pin, uint8_t level) override {
        digital_state[pin] = level;
        if (level == 0) {
            pwm_duty[pin] = 0;
        }
    }

    void writePwm(uint8_t pin, uint8_t duty_cycle) override {
        pwm_duty[pin] = duty_cycle;
        digital_state[pin] = (duty_cycle > 0) ? 1 : 0;
    }

    uint32_t getMillis() override {
        return simulated_millis;
    }

    void advanceTime(uint32_t delta_ms) {
        simulated_millis += delta_ms;
    }

    void reset() {
        is_output.clear();
        digital_state.clear();
        pwm_duty.clear();
        simulated_millis = 0;
    }
};

static int g_tests_passed = 0;
static int g_tests_total = 0;

#define TEST_ASSERT(cond, msg) \
    do { \
        if (!(cond)) { \
            std::cerr << "  ❌ ASSERTION FAILED: " << msg << " (" << #cond << ") at line " << __LINE__ << std::endl; \
            return false; \
        } \
    } while(0)

#define RUN_TEST(fn) \
    do { \
        g_tests_total++; \
        std::cout << "[TEST " << g_tests_total << "] Running " << #fn << "..." << std::endl; \
        if (fn()) { \
            g_tests_passed++; \
            std::cout << "  ✅ PASSED" << std::endl; \
        } else { \
            std::cerr << "  ❌ FAILED" << std::endl; \
        } \
    } while(0)

// ----------------------------------------------------------------------------
// Test 1: Startup Default State
// ----------------------------------------------------------------------------
bool test_startup_default_state() {
    MockGpioDriver mock;
    DisabledSensorProvider sensors;
    MotorController controller(mock, sensors);

    // Prior to init, controller must reject commands
    MotionCommand testCmd{Direction::FORWARD, 150, 1000};
    TEST_ASSERT(controller.executeCommand(testCmd) == CommandResult::REJECTED_NOT_INITIALIZED,
                "Command must be rejected before init()");

    // Initialize controller
    controller.init();

    // Verify all 4 pins configured as output
    TEST_ASSERT(mock.is_output[pins::MOTOR_IN1] == true, "IN1 must be configured as output");
    TEST_ASSERT(mock.is_output[pins::MOTOR_IN2] == true, "IN2 must be configured as output");
    TEST_ASSERT(mock.is_output[pins::MOTOR_IN3] == true, "IN3 must be configured as output");
    TEST_ASSERT(mock.is_output[pins::MOTOR_IN4] == true, "IN4 must be configured as output");

    // Verify all 4 pins driven LOW at boot
    TEST_ASSERT(mock.digital_state[pins::MOTOR_IN1] == 0, "IN1 must be driven LOW at boot");
    TEST_ASSERT(mock.digital_state[pins::MOTOR_IN2] == 0, "IN2 must be driven LOW at boot");
    TEST_ASSERT(mock.digital_state[pins::MOTOR_IN3] == 0, "IN3 must be driven LOW at boot");
    TEST_ASSERT(mock.digital_state[pins::MOTOR_IN4] == 0, "IN4 must be driven LOW at boot");

    auto status = controller.getStatus();
    TEST_ASSERT(status.active_direction == Direction::STOP, "Initial direction must be STOP");
    TEST_ASSERT(status.is_initialized == true, "Controller must be marked initialized");
    TEST_ASSERT(status.is_emergency_stopped == false, "Emergency stop must not be active at boot");

    return true;
}

// ----------------------------------------------------------------------------
// Test 2: Input Validation and Rejection of Unknown/Invalid Commands
// ----------------------------------------------------------------------------
bool test_input_validation() {
    MockGpioDriver mock;
    DisabledSensorProvider sensors;
    MotorController controller(mock, sensors);
    controller.init();

    // 1. Valid command accepted
    MotionCommand validCmd{Direction::FORWARD, 150, 1000};
    TEST_ASSERT(controller.validateCommand(validCmd) == CommandResult::ACCEPTED,
                "Valid command must be accepted");

    // 2. Invalid direction
    MotionCommand invalidDirCmd{static_cast<Direction>(99), 150, 1000};
    TEST_ASSERT(controller.validateCommand(invalidDirCmd) == CommandResult::REJECTED_INVALID_DIRECTION,
                "Unknown direction enum must be rejected");

    // 3. Speed below minimum
    MotionCommand slowCmd{Direction::FORWARD, MotorController::MIN_SPEED_PWM - 1, 1000};
    TEST_ASSERT(controller.validateCommand(slowCmd) == CommandResult::REJECTED_SPEED_OUT_OF_BOUNDS,
                "Speed below minimum threshold must be rejected");

    // 4. Speed above maximum
    MotionCommand fastCmd{Direction::FORWARD, MotorController::MAX_SPEED_PWM + 1, 1000};
    TEST_ASSERT(controller.validateCommand(fastCmd) == CommandResult::REJECTED_SPEED_OUT_OF_BOUNDS,
                "Speed above maximum threshold must be rejected");

    // 5. Duration below minimum
    MotionCommand briefCmd{Direction::FORWARD, 150, MotorController::MIN_DURATION_MS - 1};
    TEST_ASSERT(controller.validateCommand(briefCmd) == CommandResult::REJECTED_DURATION_OUT_OF_BOUNDS,
                "Duration below minimum must be rejected");

    // 6. Duration above maximum ceiling (3000ms)
    MotionCommand excessiveCmd{Direction::FORWARD, 150, MotorController::MAX_DURATION_MS + 1};
    TEST_ASSERT(controller.validateCommand(excessiveCmd) == CommandResult::REJECTED_DURATION_OUT_OF_BOUNDS,
                "Duration exceeding 3000ms ceiling must be rejected");

    // 7. STOP command always accepted regardless of speed/duration fields
    MotionCommand stopCmd{Direction::STOP, 0, 0};
    TEST_ASSERT(controller.validateCommand(stopCmd) == CommandResult::ACCEPTED,
                "STOP command must always be accepted");

    return true;
}

// ----------------------------------------------------------------------------
// Test 3: Automatic Command Duration Timeout
// ----------------------------------------------------------------------------
bool test_command_duration_timeout() {
    MockGpioDriver mock;
    DisabledSensorProvider sensors;
    MotorController controller(mock, sensors);
    controller.init();

    // Start motion for 500ms
    TEST_ASSERT(controller.forward(150, 500) == CommandResult::ACCEPTED, "Forward must start");

    // Advance time by 200ms -> motion should remain active
    mock.advanceTime(200);
    controller.update();
    auto status = controller.getStatus();
    TEST_ASSERT(status.active_direction == Direction::FORWARD, "Motion must remain active at 200ms");
    TEST_ASSERT(status.is_timed_out == false, "Must not be timed out at 200ms");

    // Advance time by 301ms (total 501ms elapsed, exceeding 500ms limit)
    mock.advanceTime(301);
    controller.update();
    status = controller.getStatus();

    TEST_ASSERT(status.active_direction == Direction::STOP, "Direction must transition to STOP upon timeout");
    TEST_ASSERT(status.is_timed_out == true, "Status must record timed_out = true");
    TEST_ASSERT(mock.digital_state[pins::MOTOR_IN1] == 0, "IN1 must be 0 after timeout");
    TEST_ASSERT(mock.digital_state[pins::MOTOR_IN2] == 0, "IN2 must be 0 after timeout");
    TEST_ASSERT(mock.digital_state[pins::MOTOR_IN3] == 0, "IN3 must be 0 after timeout");
    TEST_ASSERT(mock.digital_state[pins::MOTOR_IN4] == 0, "IN4 must be 0 after timeout");

    return true;
}

// ----------------------------------------------------------------------------
// Test 4: Heartbeat Communication Loss Watchdog
// ----------------------------------------------------------------------------
bool test_heartbeat_loss_watchdog() {
    MockGpioDriver mock;
    DisabledSensorProvider sensors;
    MotorController controller(mock, sensors);
    controller.init();

    // Start 2500ms motion
    TEST_ASSERT(controller.forward(150, 2500) == CommandResult::ACCEPTED, "Motion started");

    // Feed heartbeat at 500ms -> motion continues
    mock.advanceTime(500);
    controller.feedHeartbeat();
    controller.update();
    TEST_ASSERT(controller.getStatus().active_direction == Direction::FORWARD, "Active after heartbeat");

    // Advance time by 1501ms without feeding heartbeat (exceeds HEARTBEAT_TIMEOUT_MS = 1500ms)
    mock.advanceTime(1501);
    controller.update();
    auto status = controller.getStatus();

    TEST_ASSERT(status.active_direction == Direction::STOP, "Motors must stop on heartbeat loss");
    TEST_ASSERT(status.is_heartbeat_lost == true, "heartbeat_lost flag must be set");
    TEST_ASSERT(mock.digital_state[pins::MOTOR_IN1] == 0, "Pins must be driven LOW");

    return true;
}

// ----------------------------------------------------------------------------
// Test 5: Emergency Stop Highest Priority and Command Lockout
// ----------------------------------------------------------------------------
bool test_emergency_stop_lockout() {
    MockGpioDriver mock;
    DisabledSensorProvider sensors;
    MotorController controller(mock, sensors);
    controller.init();

    // Start motion
    controller.forward(150, 2000);
    TEST_ASSERT(controller.getStatus().active_direction == Direction::FORWARD, "Moving forward");

    // Trigger Emergency Stop
    controller.emergencyStop();
    auto status = controller.getStatus();

    TEST_ASSERT(status.active_direction == Direction::STOP, "Emergency stop must halt motion");
    TEST_ASSERT(status.is_emergency_stopped == true, "E-Stop flag must be set");
    TEST_ASSERT(mock.digital_state[pins::MOTOR_IN1] == 0, "IN1 must be 0");
    TEST_ASSERT(mock.digital_state[pins::MOTOR_IN2] == 0, "IN2 must be 0");
    TEST_ASSERT(mock.digital_state[pins::MOTOR_IN3] == 0, "IN3 must be 0");
    TEST_ASSERT(mock.digital_state[pins::MOTOR_IN4] == 0, "IN4 must be 0");

    // Attempt to execute new movement command during E-stop -> REJECTED
    MotionCommand cmd{Direction::FORWARD, 150, 1000};
    TEST_ASSERT(controller.executeCommand(cmd) == CommandResult::REJECTED_EMERGENCY_STOP_ACTIVE,
                "New command must be rejected during emergency stop");

    // Clear Emergency Stop
    controller.clearEmergencyStop();
    TEST_ASSERT(controller.getStatus().is_emergency_stopped == false, "E-Stop cleared");

    // New command now accepted
    TEST_ASSERT(controller.executeCommand(cmd) == CommandResult::ACCEPTED,
                "Command must be accepted after clearing emergency stop");

    return true;
}

// ----------------------------------------------------------------------------
// Test 6: Slew-Rate / PWM Current-Spike Ramp Limiting
// ----------------------------------------------------------------------------
bool test_pwm_ramp_limiting() {
    MockGpioDriver mock;
    DisabledSensorProvider sensors;
    MotorController controller(mock, sensors);
    controller.init();

    // Execute forward command with target speed 150 from dead stop
    controller.forward(150, 1000);

    // Initial ramp step should be RAMP_STEP_PWM (15), NOT instantaneous 150
    uint8_t initialPwm = controller.getStatus().current_ramped_pwm;
    TEST_ASSERT(initialPwm == MotorController::RAMP_STEP_PWM,
                "Initial PWM must be clamped to RAMP_STEP_PWM (15) to prevent inrush spike");
    TEST_ASSERT(mock.pwm_duty[pins::MOTOR_IN1] == MotorController::RAMP_STEP_PWM,
                "Hardware PWM duty must match ramped PWM");

    // Advance by 20ms and update -> ramps to 30
    mock.advanceTime(20);
    controller.update();
    TEST_ASSERT(controller.getStatus().current_ramped_pwm == 30, "Ramped to 30 PWM");

    // Advance by 40ms (2 ticks) -> ramps to 60
    mock.advanceTime(40);
    controller.update();
    TEST_ASSERT(controller.getStatus().current_ramped_pwm == 60, "Ramped to 60 PWM");

    return true;
}

// ----------------------------------------------------------------------------
// Test 7: Differential Turning (Pivot Left and Pivot Right)
// ----------------------------------------------------------------------------
bool test_differential_turning() {
    MockGpioDriver mock;
    DisabledSensorProvider sensors;
    MotorController controller(mock, sensors);
    controller.init();

    // 1. Pivot Left: Left motor reverse (IN1=0, IN2=PWM), Right motor forward (IN3=PWM, IN4=0)
    controller.pivotLeft(150, 1000);
    TEST_ASSERT(controller.getStatus().active_direction == Direction::PIVOT_LEFT, "Direction is PIVOT_LEFT");
    TEST_ASSERT(mock.digital_state[pins::MOTOR_IN1] == 0, "Pivot Left: IN1 must be 0");
    TEST_ASSERT(mock.pwm_duty[pins::MOTOR_IN2] > 0, "Pivot Left: IN2 must have PWM");
    TEST_ASSERT(mock.pwm_duty[pins::MOTOR_IN3] > 0, "Pivot Left: IN3 must have PWM");
    TEST_ASSERT(mock.digital_state[pins::MOTOR_IN4] == 0, "Pivot Left: IN4 must be 0");

    controller.stop();

    // 2. Pivot Right: Left motor forward (IN1=PWM, IN2=0), Right motor reverse (IN3=0, IN4=PWM)
    controller.pivotRight(150, 1000);
    TEST_ASSERT(controller.getStatus().active_direction == Direction::PIVOT_RIGHT, "Direction is PIVOT_RIGHT");
    TEST_ASSERT(mock.pwm_duty[pins::MOTOR_IN1] > 0, "Pivot Right: IN1 must have PWM");
    TEST_ASSERT(mock.digital_state[pins::MOTOR_IN2] == 0, "Pivot Right: IN2 must be 0");
    TEST_ASSERT(mock.digital_state[pins::MOTOR_IN3] == 0, "Pivot Right: IN3 must be 0");
    TEST_ASSERT(mock.pwm_duty[pins::MOTOR_IN4] > 0, "Pivot Right: IN4 must have PWM");

    return true;
}

// ----------------------------------------------------------------------------
// Test 8: Disabled Sensor Interfaces and Autonomy Gating
// ----------------------------------------------------------------------------
bool test_disabled_sensors_autonomy_gating() {
    DisabledSensorProvider sensors;

    TEST_ASSERT(sensors.isDistanceSensorAvailable() == false, "Distance sensor must be reported false");
    TEST_ASSERT(sensors.getDistanceSensorStatus() == SensorStatus::UNAVAILABLE, "Distance status must be UNAVAILABLE");
    TEST_ASSERT(sensors.getDistanceCm() == -1.0f, "Distance reading must be -1.0f");

    TEST_ASSERT(sensors.isWheelEncoderAvailable() == false, "Wheel encoder must be reported false");
    TEST_ASSERT(sensors.getEncoderStatus() == SensorStatus::UNAVAILABLE, "Encoder status must be UNAVAILABLE");
    TEST_ASSERT(sensors.getLeftEncoderTicks() == 0, "Left encoder ticks must be 0");
    TEST_ASSERT(sensors.getRightEncoderTicks() == 0, "Right encoder ticks must be 0");

    TEST_ASSERT(sensors.isObstacleAvoidanceSupported() == false, "Obstacle avoidance must be strictly unsupported");
    TEST_ASSERT(sensors.isOdometrySupported() == false, "Odometry must be strictly unsupported");

    return true;
}

// ----------------------------------------------------------------------------
// Test 9: Direction Change While Moving Resets PWM to Soft-Start
// ----------------------------------------------------------------------------
bool test_direction_change_soft_start() {
    MockGpioDriver mock;
    DisabledSensorProvider sensors;
    MotorController controller(mock, sensors);
    controller.init();

    // 1. Start forward motion and ramp up to 60 PWM
    controller.forward(150, 1000);
    mock.advanceTime(60);
    controller.update();
    TEST_ASSERT(controller.getStatus().current_ramped_pwm == 60, "Ramped up to 60 PWM");
    TEST_ASSERT(mock.pwm_duty[pins::MOTOR_IN1] == 60, "IN1 PWM is 60");

    // 2. Change direction to REVERSE while moving
    controller.reverse(150, 1000);

    // Direction changed: PWM must reset to soft-start (RAMP_STEP_PWM = 15), NOT stay at 60
    auto status = controller.getStatus();
    TEST_ASSERT(status.active_direction == Direction::REVERSE, "Direction transitioned to REVERSE");
    TEST_ASSERT(status.current_ramped_pwm == MotorController::RAMP_STEP_PWM,
                "PWM must reset to soft-start step (15) upon direction change");

    // Former bridge inputs (IN1 and IN3) must be 0
    TEST_ASSERT(mock.digital_state[pins::MOTOR_IN1] == 0, "Former IN1 must be 0");
    TEST_ASSERT(mock.digital_state[pins::MOTOR_IN3] == 0, "Former IN3 must be 0");

    // New active inputs (IN2 and IN4) must have initial soft-start PWM
    TEST_ASSERT(mock.pwm_duty[pins::MOTOR_IN2] == MotorController::RAMP_STEP_PWM, "IN2 must have soft-start PWM");
    TEST_ASSERT(mock.pwm_duty[pins::MOTOR_IN4] == MotorController::RAMP_STEP_PWM, "IN4 must have soft-start PWM");

    // 3. Same direction update: do NOT reset soft-start if direction doesn't change
    mock.advanceTime(20);
    controller.update();
    TEST_ASSERT(controller.getStatus().current_ramped_pwm == 30, "Ramped up to 30 PWM");

    // Re-issue REVERSE at new speed (180): direction is unchanged
    controller.reverse(180, 1000);
    TEST_ASSERT(controller.getStatus().current_ramped_pwm == 30,
                "PWM must NOT reset when reissuing same direction");

    return true;
}

// ----------------------------------------------------------------------------
// Test 10: Explicit PWM Zeroing on STOP Command and Transition
// ----------------------------------------------------------------------------
bool test_explicit_pwm_zero_on_stop() {
    MockGpioDriver mock;
    DisabledSensorProvider sensors;
    MotorController controller(mock, sensors);
    controller.init();

    // 1. Run forward at full ramp
    controller.forward(150, 1000);
    mock.advanceTime(200);
    controller.update();
    TEST_ASSERT(mock.pwm_duty[pins::MOTOR_IN1] > 0, "IN1 PWM active");
    TEST_ASSERT(mock.pwm_duty[pins::MOTOR_IN3] > 0, "IN3 PWM active");

    // 2. Call stop()
    controller.stop();

    // Verify all 4 pins have PWM duty explicitly set to 0 and digital state 0
    TEST_ASSERT(mock.pwm_duty[pins::MOTOR_IN1] == 0, "IN1 PWM must be 0 after stop()");
    TEST_ASSERT(mock.pwm_duty[pins::MOTOR_IN2] == 0, "IN2 PWM must be 0 after stop()");
    TEST_ASSERT(mock.pwm_duty[pins::MOTOR_IN3] == 0, "IN3 PWM must be 0 after stop()");
    TEST_ASSERT(mock.pwm_duty[pins::MOTOR_IN4] == 0, "IN4 PWM must be 0 after stop()");

    TEST_ASSERT(mock.digital_state[pins::MOTOR_IN1] == 0, "IN1 digital state must be 0");
    TEST_ASSERT(mock.digital_state[pins::MOTOR_IN2] == 0, "IN2 digital state must be 0");
    TEST_ASSERT(mock.digital_state[pins::MOTOR_IN3] == 0, "IN3 digital state must be 0");
    TEST_ASSERT(mock.digital_state[pins::MOTOR_IN4] == 0, "IN4 digital state must be 0");

    return true;
}

int main() {
    std::cout << "==================================================" << std::endl;
    std::cout << "  DORURU MOTOR CONTROLLER & SAFETY UNIT TEST SUITE " << std::endl;
    std::cout << "==================================================" << std::endl;

    RUN_TEST(test_startup_default_state);
    RUN_TEST(test_input_validation);
    RUN_TEST(test_command_duration_timeout);
    RUN_TEST(test_heartbeat_loss_watchdog);
    RUN_TEST(test_emergency_stop_lockout);
    RUN_TEST(test_pwm_ramp_limiting);
    RUN_TEST(test_differential_turning);
    RUN_TEST(test_disabled_sensors_autonomy_gating);
    RUN_TEST(test_direction_change_soft_start);
    RUN_TEST(test_explicit_pwm_zero_on_stop);

    std::cout << "==================================================" << std::endl;
    std::cout << "TEST SUMMARY: " << g_tests_passed << " / " << g_tests_total << " passed." << std::endl;
    std::cout << "==================================================" << std::endl;

    return (g_tests_passed == g_tests_total) ? 0 : 1;
}

