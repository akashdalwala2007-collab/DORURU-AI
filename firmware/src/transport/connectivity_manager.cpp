/**
 * @file connectivity_manager.cpp
 * @brief Implementation of Hybrid Connectivity Manager.
 */

#include "connectivity_manager.h"
#include "motor_safety.h"
#include "display_interface.h"
#include <stdio.h>
#include <string.h>

static connectivity_config_t s_cfg = {
    .initial_backoff_ms = 1000,
    .max_backoff_ms = 30000,
    .heartbeat_interval_ms = 5000,
    .heartbeat_timeout_ms = 3000
};

static connectivity_status_t s_status = {
    .state = CONN_STATE_ONLINE,
    .current_backoff_ms = 1000,
    .reconnect_attempts = 0,
    .last_heartbeat_rx_ms = 0,
    .next_reconnect_ms = 0,
    .inflight_request_active = false,
    .inflight_request_id = 0
};

void connectivity_manager_init(const connectivity_config_t* config) {
    if (config) {
        memcpy(&s_cfg, config, sizeof(connectivity_config_t));
    }
    s_status.state = CONN_STATE_ONLINE;
    s_status.current_backoff_ms = s_cfg.initial_backoff_ms;
    s_status.reconnect_attempts = 0;
    s_status.last_heartbeat_rx_ms = 0;
    s_status.next_reconnect_ms = 0;
    s_status.inflight_request_active = false;
    s_status.inflight_request_id = 0;
}

void connectivity_manager_on_network_down(uint32_t current_time_ms) {
    s_status.state = CONN_STATE_RECONNECT_BACKOFF;
    s_status.reconnect_attempts++;

    // Calculate next reconnect with exponential backoff (doubles each attempt up to max)
    uint32_t scheduled_delay_ms = s_status.current_backoff_ms;
    s_status.next_reconnect_ms = current_time_ms + scheduled_delay_ms;

    // Compare against max_backoff_ms before doubling to prevent uint32_t overflow
    if (s_status.current_backoff_ms >= s_cfg.max_backoff_ms || s_status.current_backoff_ms > s_cfg.max_backoff_ms / 2) {
        s_status.current_backoff_ms = s_cfg.max_backoff_ms;
    } else {
        s_status.current_backoff_ms *= 2;
    }

    // 1. Cancel in-flight requests immediately
    connectivity_manager_cancel_inflight();

    // 2. Halt motors & update display to offline state
    motor_safety_on_network_loss();

    printf("[ConnManager] Network DOWN! Attempt #%u. Backing off for %ums.\n",
           s_status.reconnect_attempts, scheduled_delay_ms);
}

void connectivity_manager_on_network_up(uint32_t current_time_ms) {
    s_status.state = CONN_STATE_ONLINE;
    s_status.reconnect_attempts = 0;
    s_status.current_backoff_ms = s_cfg.initial_backoff_ms;
    s_status.last_heartbeat_rx_ms = current_time_ms;
    s_status.next_reconnect_ms = 0;

    // Notify motor safety (advances sequence watermark, discards old commands)
    motor_safety_on_network_reconnect(current_time_ms);

    printf("[ConnManager] Network UP! Restored to ONLINE mode. Old commands discarded.\n");
}

void connectivity_manager_tick(uint32_t current_time_ms) {
    // If in reconnect backoff, check if backoff duration has elapsed
    if (s_status.state == CONN_STATE_RECONNECT_BACKOFF) {
        if (current_time_ms >= s_status.next_reconnect_ms) {
            s_status.state = CONN_STATE_CONNECTING;
            printf("[ConnManager] Backoff elapsed. Transitioning to CONNECTING...\n");
        }
    }

    // Heartbeat watchdog in ONLINE state
    if (s_status.state == CONN_STATE_ONLINE && s_status.last_heartbeat_rx_ms > 0) {
        if (current_time_ms - s_status.last_heartbeat_rx_ms > (s_cfg.heartbeat_interval_ms + s_cfg.heartbeat_timeout_ms)) {
            printf("[ConnManager] Heartbeat timed out! Triggering offline fail-safe.\n");
            connectivity_manager_on_network_down(current_time_ms);
        }
    }
}

void connectivity_manager_begin_request(uint32_t request_id) {
    s_status.inflight_request_active = true;
    s_status.inflight_request_id = request_id;
}

void connectivity_manager_end_request(uint32_t request_id) {
    if (s_status.inflight_request_id == request_id) {
        s_status.inflight_request_active = false;
        s_status.inflight_request_id = 0;
    }
}

void connectivity_manager_cancel_inflight(void) {
    if (s_status.inflight_request_active) {
        printf("[ConnManager] In-flight request %u cancelled due to network transition.\n",
               s_status.inflight_request_id);
        s_status.inflight_request_active = false;
        s_status.inflight_request_id = 0;
    }
}

void connectivity_manager_record_heartbeat(uint32_t current_time_ms) {
    s_status.last_heartbeat_rx_ms = current_time_ms;
}

bool connectivity_manager_is_online(void) {
    return (s_status.state == CONN_STATE_ONLINE);
}

const connectivity_status_t* connectivity_manager_get_status(void) {
    return &s_status;
}

