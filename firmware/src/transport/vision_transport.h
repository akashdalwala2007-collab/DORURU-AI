/**
 * @file vision_transport.h
 * @brief Safe Vision Transport Interface for DORURU.
 * Transfers captured camera frames to the local FastAPI backend via an authenticated API.
 *
 * Requirements:
 * - Authenticated local API (device token & device ID).
 * - Graceful Wi-Fi loss handling (fail-fast, no endless blocking).
 * - Ephemeral frame transport (no local persistent storage).
 * - Coordinates TFT display states (vision processing / success / error).
 * - Zero cloud credentials on ESP32 (Gemini API keys stay on backend).
 */

#pragma once

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include "camera_manager.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    TRANSPORT_SUCCESS = 0,
    TRANSPORT_ERR_WIFI_DISCONNECTED,
    TRANSPORT_ERR_INVALID_FRAME,
    TRANSPORT_ERR_HTTP_CONNECT_FAILED,
    TRANSPORT_ERR_AUTH_REJECTED,
    TRANSPORT_ERR_SERVER_ERROR,
    TRANSPORT_ERR_TIMEOUT,
    TRANSPORT_ERR_CLIENT_UNINITIALIZED
} vision_transport_status_t;

typedef struct {
    char backend_endpoint[128]; // e.g. "http://192.168.1.100:8000/api/v1/vision/upload"
    char device_id[32];          // e.g. "DORURU-SENSE-01"
    char device_token[64];       // Local authenticated token (never an external cloud secret)
    uint32_t http_timeout_ms;    // Request timeout in milliseconds (e.g. 5000)
} vision_transport_config_t;

/**
 * @brief Initialize the vision transport client with backend credentials.
 */
bool vision_transport_init(const vision_transport_config_t* config);

/**
 * @brief Check if Wi-Fi network connection is currently active.
 */
bool vision_transport_is_network_ready(void);

/**
 * @brief Test hook to configure mock network status on host builds.
 */
void vision_transport_set_network_ready_for_testing(bool is_ready);


/**
 * @brief Send a captured frame to the authenticated backend endpoint.
 *
 * @param frame The captured camera frame (must have valid JPEG data).
 * @param context_prompt Optional context / user question ("What is in front of me?").
 * @param response_buffer Optional output buffer to receive JSON/text backend reply.
 * @param response_buffer_size Size of response_buffer.
 * @return vision_transport_status_t
 */
vision_transport_status_t vision_transport_send_frame(doruru_frame_t* frame,
                                                      const char* context_prompt,
                                                      char* response_buffer,
                                                      size_t response_buffer_size);

/**
 * @brief Execute a complete safe on-demand capture and transport flow:
 * 1. Checks network connectivity.
 * 2. Captures single frame via camera manager (or safe fallback).
 * 3. Transports image to backend.
 * 4. STRICTLY releases frame buffer immediately (even on error).
 * 5. Updates TFT display state.
 *
 * @param context_prompt User question or trigger prompt.
 * @param response_buffer Output buffer for server response.
 * @param response_buffer_size Output buffer capacity.
 * @return vision_transport_status_t
 */
vision_transport_status_t vision_transport_capture_and_send(const char* context_prompt,
                                                            char* response_buffer,
                                                            size_t response_buffer_size);

#ifdef __cplusplus
}
#endif

