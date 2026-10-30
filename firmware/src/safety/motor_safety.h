/**
 * @file motor_safety.h
 * @brief Motor Safety Controller and Stale-Command Rejection for DORURU.
 *
 * Safety Invariants:
 * - Local emergency stop has absolute priority and immediately halts motors.
 * - Loss of network connection or backend communication immediately stops motors.
 * - Stale commands (exceeding TTL or older sequence IDs) are strictly rejected.
 * - Network recovery CANNOT replay old commands.
 * - Watchdog halts motors if commands cease arriving within command_timeout_ms.
 * - When offline, basic movement is blocked unless explicitly enabled.
 */

#pragma once

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    MOTOR_CMD_STOP = 0,
    MOTOR_CMD_FORWARD,
    MOTOR_CMD_REVERSE,
    MOTOR_CMD_TURN_LEFT,
    MOTOR_CMD_TURN_RIGHT,
    MOTOR_CMD_EMERGENCY_STOP
} motor_intent_t;

typedef enum {
    SAFETY_OK = 0,
    SAFETY_ERR_EMERGENCY_STOP_ACTIVE,
    SAFETY_ERR_STALE_COMMAND,
    SAFETY_ERR_SEQUENCE_REPLAY,
    SAFETY_ERR_OFFLINE_DISABLED,
    SAFETY_ERR_INVALID_BOUNDS
} safety_status_t;

typedef struct {
    uint32_t command_id;    // Monotonic sequence number
    motor_intent_t intent;  // Direction / Stop
    uint8_t speed;          // 0-255 PWM speed
    uint32_t duration_ms;   // Movement duration in ms (capped at 2000)
    uint32_t timestamp_ms;  // When command was issued
    uint32_t ttl_ms;        // Time-to-live in ms (default 1000)
} motor_command_t;

#define MAX_ALLOWED_COMMAND_TTL_MS 5000

typedef struct {
    bool is_online;
    bool allow_offline_movement;
    bool is_emergency_stop;
    bool are_motors_active;
    uint32_t last_executed_sequence;
    uint32_t last_command_time_ms;
    uint32_t command_timeout_ms;
    uint32_t active_duration_ms;
    uint32_t movement_deadline_ms;
    motor_intent_t current_intent;
} motor_safety_state_t;

/**
 * @brief Initialize motor safety subsystem.
 */
void motor_safety_init(uint32_t command_timeout_ms);

/**
 * @brief Process an incoming movement command with strict validation.
 */
safety_status_t motor_safety_process_command(const motor_command_t* cmd, uint32_t current_time_ms);

/**
 * @brief Periodic watchdog tick. Stops motors if command_timeout_ms is exceeded.
 */
void motor_safety_tick(uint32_t current_time_ms);

/**
 * @brief Trigger immediate emergency stop. Halts motors and sets display state.
 */
void motor_safety_emergency_stop(void);

/**
 * @brief Clear emergency stop state after manual reset/verification.
 */
void motor_safety_clear_emergency_stop(void);

/**
 * @brief Invoked upon network loss. Immediately halts motors and displays offline state.
 */
void motor_safety_on_network_loss(void);

/**
 * @brief Invoked upon network reconnect. Advances sequence threshold to prevent replaying old commands.
 */
void motor_safety_on_network_reconnect(uint32_t current_time_ms);

/**
 * @brief Set whether offline movement is allowed.
 */
void motor_safety_set_allow_offline_movement(bool allow);

/**
 * @brief Retrieve current motor safety telemetry and state.
 */
const motor_safety_state_t* motor_safety_get_state(void);

#ifdef __cplusplus
}
#endif

