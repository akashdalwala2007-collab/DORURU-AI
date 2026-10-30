#pragma once

#include <stdint.h>
#include <stdbool.h>
#include "motor_controller.h"

namespace doruru {
namespace safety {

/**
 * Result returned by the firmware's independent command validator.
 */
enum class ValidationResult : uint8_t {
    ACCEPTED = 0,
    REJECTED_STALE_PACKET = 1,
    REJECTED_REPLAY_ATTACK = 2,
    REJECTED_UNSUPPORTED_AUTONOMY_LEVEL = 3,
    REJECTED_INVALID_DIRECTION = 4,
    REJECTED_SPEED_OUT_OF_BOUNDS = 5,
    REJECTED_DURATION_OUT_OF_BOUNDS = 6,
    REJECTED_EMERGENCY_STOP_ACTIVE = 7
};

/**
 * Inbound command packet received from local FastAPI backend or network.
 */
struct InboundCommandPacket {
    uint32_t sequence_id;     // Monotonically increasing sequence number
    uint8_t direction;        // 0=STOP, 1=FORWARD, 2=REVERSE, 3=PIVOT_LEFT, 4=PIVOT_RIGHT
    uint8_t speed_pwm;        // 60..220
    uint32_t duration_ms;     // 50..3000
    uint32_t timestamp_ms;    // Timestamp when packet was created
    uint32_t ttl_ms;          // Maximum allowable transit age (default 1000ms)
    uint8_t autonomy_level;   // Must be 1 (Level 1 Bounded Timed Movement)
};

/**
 * Independent Firmware Command Validator.
 * 
 * Enforces defense-in-depth safety invariants on the ESP32:
 * 1. Independent validation: never trusts remote backend or model text blindly.
 * 2. Replay protection: sequence IDs must be strictly increasing.
 * 3. Freshness check: packets exceeding TTL are dropped as stale.
 * 4. Autonomy gating: rejects any command requesting autonomy Level > 1.
 * 5. Parameter boundaries: enforces hardware speed and duration limits.
 */
class CommandValidator {
public:
    static constexpr uint8_t  ACTIVE_AUTONOMY_LEVEL   = 1;
    static constexpr uint32_t DEFAULT_TTL_MS          = 1000; // 1 second validity window
    static constexpr uint32_t MAX_ALLOWABLE_TTL_MS    = 3000;
    static constexpr uint32_t MAX_FUTURE_SKEW_MS      = 200;  // 200ms tolerance for network/clock skew allowance

    CommandValidator() = default;

    /**
     * Resets sequence counter and freshness tracking (e.g. at boot, re-pairing,
     * or recovery when the 32-bit sequence space is exhausted).
     */
    void reset();

    /**
     * Returns true if sequence counter has reached UINT32_MAX and requires recovery reset.
     */
    bool isSequenceExhausted() const {
        return has_received_first_packet_ && (last_sequence_id_ == UINT32_MAX);
    }

    /**
     * Validates an inbound packet against independent firmware safety rules.
     * 
     * @param packet The candidate inbound command packet.
     * @param current_device_time_ms Current ESP32 millis() timestamp.
     * @param controller Active MotorController to verify emergency stop state.
     * @param out_cmd If ACCEPTED, populated with safe MotionCommand.
     */
    ValidationResult validate(const InboundCommandPacket& packet,
                              uint32_t current_device_time_ms,
                              const motor::MotorController& controller,
                              motor::MotionCommand& out_cmd);

    uint32_t getLastSequenceId() const { return last_sequence_id_; }

private:
    uint32_t last_sequence_id_{0};
    bool has_received_first_packet_{false};
};

} // namespace safety
} // namespace doruru

