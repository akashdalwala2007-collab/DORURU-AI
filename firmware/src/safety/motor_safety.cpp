/**
 * @file motor_safety.cpp
 * @brief Implementation of Motor Safety Controller and Stale-Command Rejection.
 */

#include "motor_safety.h"
#include "display_interface.h"
#include <string.h>
#include <stdio.h>

#if defined(ESP32) || defined(ARDUINO)
#include <Arduino.h>
#include "board_pins.h"
#endif

static motor_safety_state_t s_state = {
    .is_online = true,
    .allow_offline_movement = false,
    .is_emergency_stop = false,
    .are_motors_active = false,
    .last_executed_sequence = 0,
    .last_command_time_ms = 0,
    .command_timeout_ms = 500, // 500ms watchdog
    .active_duration_ms = 0,
    .movement_deadline_ms = 0,
    .current_intent = MOTOR_CMD_STOP
};

static void apply_hardware_motor_stop(void) {
    s_state.are_motors_active = false;
    s_state.current_intent = MOTOR_CMD_STOP;
    s_state.active_duration_ms = 0;
    s_state.movement_deadline_ms = 0;

#if defined(ESP32) || defined(ARDUINO)
    // Low on all MX1508 H-bridge pins for active brake / coast to stop
    digitalWrite(MOTOR_PIN_IN1, LOW);
    digitalWrite(MOTOR_PIN_IN2, LOW);
    digitalWrite(MOTOR_PIN_IN3, LOW);
    digitalWrite(MOTOR_PIN_IN4, LOW);
#endif
}

static void apply_hardware_motor_drive(motor_intent_t intent, uint8_t speed) {
    s_state.are_motors_active = (intent != MOTOR_CMD_STOP && intent != MOTOR_CMD_EMERGENCY_STOP);
    s_state.current_intent = intent;

#if defined(ESP32) || defined(ARDUINO)
    // Drive MX1508 according to intent
    switch (intent) {
        case MOTOR_CMD_FORWARD:
            analogWrite(MOTOR_PIN_IN1, speed);
            digitalWrite(MOTOR_PIN_IN2, LOW);
            analogWrite(MOTOR_PIN_IN3, speed);
            digitalWrite(MOTOR_PIN_IN4, LOW);
            break;
        case MOTOR_CMD_REVERSE:
            digitalWrite(MOTOR_PIN_IN1, LOW);
            analogWrite(MOTOR_PIN_IN2, speed);
            digitalWrite(MOTOR_PIN_IN3, LOW);
            analogWrite(MOTOR_PIN_IN4, speed);
            break;
        case MOTOR_CMD_TURN_LEFT:
            digitalWrite(MOTOR_PIN_IN1, LOW);
            analogWrite(MOTOR_PIN_IN2, speed);
            analogWrite(MOTOR_PIN_IN3, speed);
            digitalWrite(MOTOR_PIN_IN4, LOW);
            break;
        case MOTOR_CMD_TURN_RIGHT:
            analogWrite(MOTOR_PIN_IN1, speed);
            digitalWrite(MOTOR_PIN_IN2, LOW);
            digitalWrite(MOTOR_PIN_IN3, LOW);
            analogWrite(MOTOR_PIN_IN4, speed);
            break;
        case MOTOR_CMD_STOP:
        case MOTOR_CMD_EMERGENCY_STOP:
        default:
            apply_hardware_motor_stop();
            break;
    }
#endif
}

void motor_safety_init(uint32_t command_timeout_ms) {
    s_state.command_timeout_ms = (command_timeout_ms > 0) ? command_timeout_ms : 500;
    s_state.is_online = true;
    s_state.allow_offline_movement = false;
    s_state.is_emergency_stop = false;
    s_state.are_motors_active = false;
    s_state.last_executed_sequence = 0;
    s_state.last_command_time_ms = 0;
    s_state.current_intent = MOTOR_CMD_STOP;

#if defined(ESP32) || defined(ARDUINO)
    pinMode(MOTOR_PIN_IN1, OUTPUT);
    pinMode(MOTOR_PIN_IN2, OUTPUT);
    pinMode(MOTOR_PIN_IN3, OUTPUT);
    pinMode(MOTOR_PIN_IN4, OUTPUT);
#endif
    apply_hardware_motor_stop();
}

safety_status_t motor_safety_process_command(const motor_command_t* cmd, uint32_t current_time_ms) {
    if (!cmd) {
        return SAFETY_ERR_INVALID_BOUNDS;
    }

    // 1. Emergency stop check
    if (s_state.is_emergency_stop) {
        apply_hardware_motor_stop();
        display_set_state(DISPLAY_STATE_EMERGENCY_STOP, "E-Stop Active: Command Denied");
        return SAFETY_ERR_EMERGENCY_STOP_ACTIVE;
    }

    // Explicit E-Stop command
    if (cmd->intent == MOTOR_CMD_EMERGENCY_STOP) {
        motor_safety_emergency_stop();
        return SAFETY_OK;
    }

    // Stop command is always executed immediately regardless of sequence or timing
    if (cmd->intent == MOTOR_CMD_STOP) {
        apply_hardware_motor_stop();
        // Preserve sequence watermark: only update if cmd->command_id > current watermark
        if (cmd->command_id > s_state.last_executed_sequence) {
            s_state.last_executed_sequence = cmd->command_id;
        }
        s_state.last_command_time_ms = current_time_ms;
        display_set_state(DISPLAY_STATE_IDLE_READY, "Motors Stopped");
        return SAFETY_OK;
    }

    // 2. Monotonic sequence check (Replay Prevention)
    if (cmd->command_id <= s_state.last_executed_sequence) {
        printf("[MotorSafety] Rejecting replay/stale sequence %u <= %u\n",
               cmd->command_id, s_state.last_executed_sequence);
        return SAFETY_ERR_SEQUENCE_REPLAY;
    }

    // 3. Staleness check (Timestamp + TTL)
    uint32_t ttl = (cmd->ttl_ms > 0) ? cmd->ttl_ms : 1000;
    if (ttl > MAX_ALLOWED_COMMAND_TTL_MS) {
        ttl = MAX_ALLOWED_COMMAND_TTL_MS; // Cap TTL to prevent old commands lingering indefinitely
    }
    if (current_time_ms >= cmd->timestamp_ms) {
        uint32_t elapsed = current_time_ms - cmd->timestamp_ms;
        if (elapsed > ttl) {
            printf("[MotorSafety] Rejecting stale command %u (age %ums > ttl %ums)\n",
                   cmd->command_id, elapsed, ttl);
            return SAFETY_ERR_STALE_COMMAND;
        }
    } else {
        // Clock skew check: if command timestamp is in the future by > 1000ms, reject
        if (cmd->timestamp_ms - current_time_ms > 1000) {
            printf("[MotorSafety] Rejecting future timestamp command %u\n", cmd->command_id);
            return SAFETY_ERR_STALE_COMMAND;
        }
    }

    // 4. Offline mode safety constraint
    if (!s_state.is_online && !s_state.allow_offline_movement) {
        printf("[MotorSafety] Rejecting movement command while offline\n");
        display_set_state(DISPLAY_STATE_WIFI_DISCONNECTED, "Offline: Movement Disabled");
        return SAFETY_ERR_OFFLINE_DISABLED;
    }

    // 5. Bounds check & clamping
    uint8_t speed = cmd->speed;
    uint32_t duration = (cmd->duration_ms > 2000) ? 2000 : ((cmd->duration_ms < 50) ? 50 : cmd->duration_ms);

    // Apply movement
    s_state.last_executed_sequence = cmd->command_id;
    s_state.last_command_time_ms = current_time_ms;
    s_state.active_duration_ms = duration;
    s_state.movement_deadline_ms = current_time_ms + duration;
    apply_hardware_motor_drive(cmd->intent, speed);
    display_set_state(DISPLAY_STATE_MOTOR_MOVING, "Moving...");

    return SAFETY_OK;
}

void motor_safety_tick(uint32_t current_time_ms) {
    if (s_state.are_motors_active) {
        // Wrap-safe time comparison for movement deadline
        bool deadline_reached = (s_state.movement_deadline_ms != 0) &&
                                ((int32_t)(current_time_ms - s_state.movement_deadline_ms) >= 0);
        bool watchdog_timeout = (current_time_ms - s_state.last_command_time_ms > s_state.command_timeout_ms);

        if (deadline_reached) {
            apply_hardware_motor_stop();
            display_set_state(DISPLAY_STATE_IDLE_READY, "Movement Complete");
        } else if (watchdog_timeout) {
            printf("[MotorSafety] Watchdog timeout (%ums). Halting motors.\n",
                   current_time_ms - s_state.last_command_time_ms);
            apply_hardware_motor_stop();
            display_set_state(DISPLAY_STATE_IDLE_READY, "Watchdog: Motors Stopped");
        }
    }
}

void motor_safety_emergency_stop(void) {
    s_state.is_emergency_stop = true;
    apply_hardware_motor_stop();
    display_set_state(DISPLAY_STATE_EMERGENCY_STOP, "EMERGENCY STOP ENGAGED");
    printf("[MotorSafety] EMERGENCY STOP ENGAGED! Motors halted immediately.\n");
}

void motor_safety_clear_emergency_stop(void) {
    s_state.is_emergency_stop = false;
    apply_hardware_motor_stop();
    display_set_state(DISPLAY_STATE_IDLE_READY, "E-Stop Cleared: Motors Ready");
    printf("[MotorSafety] Emergency stop cleared.\n");
}

void motor_safety_on_network_loss(void) {
    s_state.is_online = false;
    // Immediately stop motors on network drop
    apply_hardware_motor_stop();
    display_set_state(DISPLAY_STATE_WIFI_DISCONNECTED, "Offline: Motors Stopped");
    printf("[MotorSafety] Network loss detected! Motors immediately halted.\n");
}

void motor_safety_on_network_reconnect(uint32_t current_time_ms) {
    s_state.is_online = true;
    s_state.last_command_time_ms = current_time_ms;
    // Advance sequence watermark so commands issued before reconnect cannot be replayed
    s_state.last_executed_sequence++;
    // Ensure motors remain stopped upon reconnect
    apply_hardware_motor_stop();
    display_set_state(DISPLAY_STATE_IDLE_READY, "Reconnected: Idle");
    printf("[MotorSafety] Network reconnected. Sequence watermark advanced to %u. Pre-disconnect commands invalidated.\n",
           s_state.last_executed_sequence);
}

void motor_safety_set_allow_offline_movement(bool allow) {
    s_state.allow_offline_movement = allow;
}

const motor_safety_state_t* motor_safety_get_state(void) {
    return &s_state;
}

