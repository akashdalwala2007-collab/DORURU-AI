#include "motor_controller.h"

namespace doruru {
namespace motor {

MotorController::MotorController(IGpioDriver& gpio_driver,
                                 sensors::ISensorProvider& sensor_provider)
    : gpio_(gpio_driver),
      sensors_(sensor_provider) {
}

void MotorController::init() {
    // Configure all MX1508 motor driver pins as OUTPUT
    gpio_.setPinModeOutput(pins::MOTOR_IN1);
    gpio_.setPinModeOutput(pins::MOTOR_IN2);
    gpio_.setPinModeOutput(pins::MOTOR_IN3);
    gpio_.setPinModeOutput(pins::MOTOR_IN4);

    // Startup Default: strictly drive all pins LOW (Stop / Coast)
    gpio_.writeDigital(pins::MOTOR_IN1, 0);
    gpio_.writeDigital(pins::MOTOR_IN2, 0);
    gpio_.writeDigital(pins::MOTOR_IN3, 0);
    gpio_.writeDigital(pins::MOTOR_IN4, 0);

    initialized_ = true;
    emergency_stopped_ = false;
    timed_out_ = false;
    heartbeat_lost_ = false;
    active_direction_ = Direction::STOP;
    target_speed_pwm_ = 0;
    current_ramped_pwm_ = 0;

    uint32_t now = gpio_.getMillis();
    last_heartbeat_time_ = now;
    last_ramp_time_ = now;
}

CommandResult MotorController::validateCommand(const MotionCommand& cmd) const {
    if (!initialized_) {
        return CommandResult::REJECTED_NOT_INITIALIZED;
    }
    if (emergency_stopped_) {
        return CommandResult::REJECTED_EMERGENCY_STOP_ACTIVE;
    }

    switch (cmd.direction) {
        case Direction::STOP:
            return CommandResult::ACCEPTED;

        case Direction::FORWARD:
        case Direction::REVERSE:
        case Direction::PIVOT_LEFT:
        case Direction::PIVOT_RIGHT:
            break;

        default:
            return CommandResult::REJECTED_INVALID_DIRECTION;
    }

    // Speed boundaries check
    if (cmd.speed_pwm < MIN_SPEED_PWM || cmd.speed_pwm > MAX_SPEED_PWM) {
        return CommandResult::REJECTED_SPEED_OUT_OF_BOUNDS;
    }

    // Duration boundaries check
    if (cmd.duration_ms < MIN_DURATION_MS || cmd.duration_ms > MAX_DURATION_MS) {
        return CommandResult::REJECTED_DURATION_OUT_OF_BOUNDS;
    }

    return CommandResult::ACCEPTED;
}

CommandResult MotorController::executeCommand(const MotionCommand& cmd) {
    CommandResult validation = validateCommand(cmd);
    if (validation != CommandResult::ACCEPTED) {
        return validation;
    }

    if (cmd.direction == Direction::STOP) {
        stop();
        return CommandResult::ACCEPTED;
    }

    bool direction_changed = (active_direction_ != cmd.direction);

    // If direction changes while PWM is active, stop both motor bridges
    // and reset current_ramped_pwm_ so the new direction starts through the soft-start ramp.
    if (direction_changed && current_ramped_pwm_ > 0) {
        applyHardwareOutputs(Direction::STOP, 0);
        current_ramped_pwm_ = 0;
    }

    uint32_t now = gpio_.getMillis();
    active_direction_ = cmd.direction;
    target_speed_pwm_ = cmd.speed_pwm;
    command_duration_ms_ = cmd.duration_ms;
    command_start_time_ = now;
    last_heartbeat_time_ = now;
    last_ramp_time_ = now;
    timed_out_ = false;
    heartbeat_lost_ = false;

    // Initialize soft-start ramp to mitigate sudden inductive inrush
    if (current_ramped_pwm_ == 0) {
        current_ramped_pwm_ = (target_speed_pwm_ < RAMP_STEP_PWM) ? 
                               target_speed_pwm_ : RAMP_STEP_PWM;
    }

    applyHardwareOutputs(active_direction_, current_ramped_pwm_);
    return CommandResult::ACCEPTED;
}

CommandResult MotorController::forward(uint8_t speed_pwm, uint32_t duration_ms) {
    MotionCommand cmd{Direction::FORWARD, speed_pwm, duration_ms};
    return executeCommand(cmd);
}

CommandResult MotorController::reverse(uint8_t speed_pwm, uint32_t duration_ms) {
    MotionCommand cmd{Direction::REVERSE, speed_pwm, duration_ms};
    return executeCommand(cmd);
}

CommandResult MotorController::pivotLeft(uint8_t speed_pwm, uint32_t duration_ms) {
    MotionCommand cmd{Direction::PIVOT_LEFT, speed_pwm, duration_ms};
    return executeCommand(cmd);
}

CommandResult MotorController::pivotRight(uint8_t speed_pwm, uint32_t duration_ms) {
    MotionCommand cmd{Direction::PIVOT_RIGHT, speed_pwm, duration_ms};
    return executeCommand(cmd);
}

void MotorController::stop() {
    active_direction_ = Direction::STOP;
    target_speed_pwm_ = 0;
    current_ramped_pwm_ = 0;
    command_duration_ms_ = 0;
    applyHardwareOutputs(Direction::STOP, 0);
}

void MotorController::emergencyStop() {
    emergency_stopped_ = true;
    stop();
}

void MotorController::clearEmergencyStop() {
    emergency_stopped_ = false;
    stop();
}

void MotorController::feedHeartbeat() {
    last_heartbeat_time_ = gpio_.getMillis();
    heartbeat_lost_ = false;
}

void MotorController::update() {
    if (!initialized_) {
        return;
    }

    // Emergency stop override
    if (emergency_stopped_) {
        applyHardwareOutputs(Direction::STOP, 0);
        return;
    }

    if (active_direction_ == Direction::STOP) {
        return;
    }

    uint32_t now = gpio_.getMillis();

    // 1. Communication Loss Watchdog
    if ((now - last_heartbeat_time_) >= HEARTBEAT_TIMEOUT_MS) {
        heartbeat_lost_ = true;
        stop();
        return;
    }

    // 2. Command Duration Timeout Watchdog
    if ((now - command_start_time_) >= command_duration_ms_) {
        timed_out_ = true;
        stop();
        return;
    }

    // 3. Current Spike Mitigation / Slew-Rate Ramping
    updateRamping(now);
}

void MotorController::updateRamping(uint32_t now) {
    if ((now - last_ramp_time_) < RAMP_TICK_INTERVAL_MS) {
        return;
    }

    uint32_t elapsed_ticks = (now - last_ramp_time_) / RAMP_TICK_INTERVAL_MS;
    last_ramp_time_ += elapsed_ticks * RAMP_TICK_INTERVAL_MS;
    uint32_t total_ramp_delta = elapsed_ticks * RAMP_STEP_PWM;

    if (current_ramped_pwm_ < target_speed_pwm_) {
        uint32_t next = static_cast<uint32_t>(current_ramped_pwm_) + total_ramp_delta;
        current_ramped_pwm_ = (next >= target_speed_pwm_) ? 
                               target_speed_pwm_ : static_cast<uint8_t>(next);
        applyHardwareOutputs(active_direction_, current_ramped_pwm_);
    } else if (current_ramped_pwm_ > target_speed_pwm_) {
        int32_t next = static_cast<int32_t>(current_ramped_pwm_) - total_ramp_delta;
        current_ramped_pwm_ = (next <= target_speed_pwm_) ? 
                               target_speed_pwm_ : static_cast<uint8_t>(next);
        applyHardwareOutputs(active_direction_, current_ramped_pwm_);
    }
}

void MotorController::applyHardwareOutputs(Direction dir, uint8_t duty_cycle) {
    // MX1508 Dual H-Bridge Control Truth Table:
    // Motor A (Left):  IN1 = GPIO4, IN2 = GPIO3
    // Motor B (Right): IN3 = GPIO2, IN4 = GPIO1
    //
    // Safety ordering: ALWAYS explicitly clear inactive bridge inputs by zeroing
    // PWM duty and driving LOW before enabling PWM on the active input.
    // This prevents shoot-through and cross-conduction even if digitalWrite
    // does not detach hardware LEDC timers on certain framework cores.

    switch (dir) {
        case Direction::STOP:
            // Safe Coast / Standby: explicitly zero PWM duty and drive all inputs LOW
            gpio_.writePwm(pins::MOTOR_IN1, 0);
            gpio_.writePwm(pins::MOTOR_IN2, 0);
            gpio_.writePwm(pins::MOTOR_IN3, 0);
            gpio_.writePwm(pins::MOTOR_IN4, 0);
            gpio_.writeDigital(pins::MOTOR_IN1, 0);
            gpio_.writeDigital(pins::MOTOR_IN2, 0);
            gpio_.writeDigital(pins::MOTOR_IN3, 0);
            gpio_.writeDigital(pins::MOTOR_IN4, 0);
            break;

        case Direction::FORWARD:
            // Left forward, Right forward
            // Clear IN2 and IN4 PWM and set LOW first, then apply PWM to IN1 and IN3
            gpio_.writePwm(pins::MOTOR_IN2, 0);
            gpio_.writePwm(pins::MOTOR_IN4, 0);
            gpio_.writeDigital(pins::MOTOR_IN2, 0);
            gpio_.writeDigital(pins::MOTOR_IN4, 0);
            gpio_.writePwm(pins::MOTOR_IN1, duty_cycle);
            gpio_.writePwm(pins::MOTOR_IN3, duty_cycle);
            break;

        case Direction::REVERSE:
            // Left reverse, Right reverse
            // Clear IN1 and IN3 PWM and set LOW first, then apply PWM to IN2 and IN4
            gpio_.writePwm(pins::MOTOR_IN1, 0);
            gpio_.writePwm(pins::MOTOR_IN3, 0);
            gpio_.writeDigital(pins::MOTOR_IN1, 0);
            gpio_.writeDigital(pins::MOTOR_IN3, 0);
            gpio_.writePwm(pins::MOTOR_IN2, duty_cycle);
            gpio_.writePwm(pins::MOTOR_IN4, duty_cycle);
            break;

        case Direction::PIVOT_LEFT:
            // Left reverse, Right forward
            // Clear IN1 and IN4 PWM and set LOW first, then apply PWM to IN2 and IN3
            gpio_.writePwm(pins::MOTOR_IN1, 0);
            gpio_.writePwm(pins::MOTOR_IN4, 0);
            gpio_.writeDigital(pins::MOTOR_IN1, 0);
            gpio_.writeDigital(pins::MOTOR_IN4, 0);
            gpio_.writePwm(pins::MOTOR_IN2, duty_cycle);
            gpio_.writePwm(pins::MOTOR_IN3, duty_cycle);
            break;

        case Direction::PIVOT_RIGHT:
            // Left forward, Right reverse
            // Clear IN2 and IN3 PWM and set LOW first, then apply PWM to IN1 and IN4
            gpio_.writePwm(pins::MOTOR_IN2, 0);
            gpio_.writePwm(pins::MOTOR_IN3, 0);
            gpio_.writeDigital(pins::MOTOR_IN2, 0);
            gpio_.writeDigital(pins::MOTOR_IN3, 0);
            gpio_.writePwm(pins::MOTOR_IN1, duty_cycle);
            gpio_.writePwm(pins::MOTOR_IN4, duty_cycle);
            break;
    }
}

ControllerStatus MotorController::getStatus() const {
    ControllerStatus status;
    status.active_direction = active_direction_;
    status.target_speed_pwm = target_speed_pwm_;
    status.current_ramped_pwm = current_ramped_pwm_;
    status.is_emergency_stopped = emergency_stopped_;
    status.is_timed_out = timed_out_;
    status.is_heartbeat_lost = heartbeat_lost_;
    status.is_initialized = initialized_;

    if (active_direction_ == Direction::STOP || !initialized_) {
        status.remaining_duration_ms = 0;
    } else {
        uint32_t elapsed = gpio_.getMillis() - command_start_time_;
        status.remaining_duration_ms = (elapsed >= command_duration_ms_) ? 
                                       0 : (command_duration_ms_ - elapsed);
    }

    return status;
}

} // namespace motor
} // namespace doruru
