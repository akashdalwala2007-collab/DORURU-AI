#include "command_validator.h"

namespace doruru {
namespace safety {

void CommandValidator::reset() {
    last_sequence_id_ = 0;
    has_received_first_packet_ = false;
}

ValidationResult CommandValidator::validate(const InboundCommandPacket& packet,
                                           uint32_t current_device_time_ms,
                                           const motor::MotorController& controller,
                                           motor::MotionCommand& out_cmd) {
    // 1. Controller safety lockout check (Emergency Stop has highest priority)
    if (controller.getStatus().is_emergency_stopped) {
        return ValidationResult::REJECTED_EMERGENCY_STOP_ACTIVE;
    }

    // 2. Autonomy Level check (strictly Level 1 allowed without hardware encoders/sensors)
    if (packet.autonomy_level != ACTIVE_AUTONOMY_LEVEL) {
        return ValidationResult::REJECTED_UNSUPPORTED_AUTONOMY_LEVEL;
    }

    // 3. Replay attack protection (monotonically increasing sequence numbers)
    if (has_received_first_packet_) {
        if (packet.sequence_id <= last_sequence_id_) {
            return ValidationResult::REJECTED_REPLAY_ATTACK;
        }
    }

    // 4. Packet freshness / stale packet rejection
    uint32_t ttl = (packet.ttl_ms > 0 && packet.ttl_ms <= MAX_ALLOWABLE_TTL_MS) ? 
                    packet.ttl_ms : DEFAULT_TTL_MS;

    if (packet.timestamp_ms > current_device_time_ms) {
        uint32_t future_skew_ms = packet.timestamp_ms - current_device_time_ms;
        if (future_skew_ms > MAX_FUTURE_SKEW_MS) {
            return ValidationResult::REJECTED_STALE_PACKET;
        }
    } else {
        uint32_t age_ms = current_device_time_ms - packet.timestamp_ms;
        if (age_ms > ttl) {
            return ValidationResult::REJECTED_STALE_PACKET;
        }
    }

    // 5. Direction validity check
    if (packet.direction > static_cast<uint8_t>(motor::Direction::PIVOT_RIGHT)) {
        return ValidationResult::REJECTED_INVALID_DIRECTION;
    }

    motor::Direction target_dir = static_cast<motor::Direction>(packet.direction);

    // 6. Parameter boundary check (for active motion commands)
    if (target_dir != motor::Direction::STOP) {
        if (packet.speed_pwm < motor::MotorController::MIN_SPEED_PWM || 
            packet.speed_pwm > motor::MotorController::MAX_SPEED_PWM) {
            return ValidationResult::REJECTED_SPEED_OUT_OF_BOUNDS;
        }

        if (packet.duration_ms < motor::MotorController::MIN_DURATION_MS || 
            packet.duration_ms > motor::MotorController::MAX_DURATION_MS) {
            return ValidationResult::REJECTED_DURATION_OUT_OF_BOUNDS;
        }
    }

    // Packet is valid: commit sequence ID and populate outbound MotionCommand
    last_sequence_id_ = packet.sequence_id;
    has_received_first_packet_ = true;

    out_cmd.direction = target_dir;
    out_cmd.speed_pwm = (target_dir == motor::Direction::STOP) ? 0 : packet.speed_pwm;
    out_cmd.duration_ms = (target_dir == motor::Direction::STOP) ? 0 : packet.duration_ms;

    return ValidationResult::ACCEPTED;
}

} // namespace safety
} // namespace doruru

