/**
 * @file connectivity_manager.h
 * @brief Hybrid Connectivity Manager with Exponential Backoff and Request Cancellation.
 *
 * Responsibilities:
 * - State management: Online, Offline, Connecting, Reconnecting (Backoff).
 * - Exponential backoff algorithm for safe reconnection without overwhelming the network.
 * - In-flight request cancellation on network loss.
 * - Coordinates health check heartbeats with local backend.
 * - Coordinates display and motor safety state transitions.
 */

#pragma once

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    CONN_STATE_OFFLINE = 0,
    CONN_STATE_CONNECTING,
    CONN_STATE_ONLINE,
    CONN_STATE_RECONNECT_BACKOFF
} connectivity_state_t;

typedef struct {
    uint32_t initial_backoff_ms;    // e.g. 1000ms
    uint32_t max_backoff_ms;        // e.g. 30000ms
    uint32_t heartbeat_interval_ms; // e.g. 5000ms
    uint32_t heartbeat_timeout_ms;  // e.g. 3000ms
} connectivity_config_t;

typedef struct {
    connectivity_state_t state;
    uint32_t current_backoff_ms;
    uint32_t reconnect_attempts;
    uint32_t last_heartbeat_rx_ms;
    uint32_t next_reconnect_ms;
    bool inflight_request_active;
    uint32_t inflight_request_id;
} connectivity_status_t;

/**
 * @brief Initialize connectivity manager.
 */
void connectivity_manager_init(const connectivity_config_t* config);

/**
 * @brief Notify manager that network link went down.
 * Immediately cancels in-flight requests, stops motors, and enters backoff.
 */
void connectivity_manager_on_network_down(uint32_t current_time_ms);

/**
 * @brief Notify manager that network link was restored.
 */
void connectivity_manager_on_network_up(uint32_t current_time_ms);

/**
 * @brief Periodic tick to manage backoff timers and heartbeat timeouts.
 */
void connectivity_manager_tick(uint32_t current_time_ms);

/**
 * @brief Record start of an in-flight request.
 */
void connectivity_manager_begin_request(uint32_t request_id);

/**
 * @brief Record successful completion of an in-flight request.
 */
void connectivity_manager_end_request(uint32_t request_id);

/**
 * @brief Explicitly cancel in-flight request (e.g. timeout or abort).
 */
void connectivity_manager_cancel_inflight(void);

/**
 * @brief Record receipt of valid heartbeat/health-check response from backend.
 */
void connectivity_manager_record_heartbeat(uint32_t current_time_ms);

/**
 * @brief Check if connectivity is currently online.
 */
bool connectivity_manager_is_online(void);

/**
 * @brief Get read-only pointer to connectivity telemetry.
 */
const connectivity_status_t* connectivity_manager_get_status(void);

#ifdef __cplusplus
}
#endif

