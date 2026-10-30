/**
 * @file vision_transport.cpp
 * @brief Implementation of Vision Transport client.
 */

#include "vision_transport.h"
#include "display_interface.h"
#include <string.h>
#include <stdio.h>

#if defined(ESP32) || defined(ARDUINO)
#include <WiFi.h>
#include <HTTPClient.h>
#else
// Host mock stubs
static bool s_mock_wifi_connected = true;
#endif

static vision_transport_config_t s_config = {0};
static bool s_is_configured = false;

bool vision_transport_init(const vision_transport_config_t* config) {
    if (!config || strlen(config->backend_endpoint) == 0) {
        return false;
    }
    memcpy(&s_config, config, sizeof(vision_transport_config_t));
    if (s_config.http_timeout_ms == 0) {
        s_config.http_timeout_ms = 5000; // Default 5 seconds
    }
    s_is_configured = true;
    return true;
}

bool vision_transport_is_network_ready(void) {
#if defined(ESP32) || defined(ARDUINO)
    return (WiFi.status() == WL_CONNECTED);
#else
    return s_mock_wifi_connected;
#endif
}

void vision_transport_set_network_ready_for_testing(bool is_ready) {
#if !defined(ESP32) && !defined(ARDUINO)
    s_mock_wifi_connected = is_ready;
#else
    (void)is_ready;
#endif
}


vision_transport_status_t vision_transport_send_frame(doruru_frame_t* frame,
                                                      const char* context_prompt,
                                                      char* response_buffer,
                                                      size_t response_buffer_size) {
    if (!s_is_configured) {
        return TRANSPORT_ERR_CLIENT_UNINITIALIZED;
    }

    if (!frame || !frame->data || frame->length == 0) {
        return TRANSPORT_ERR_INVALID_FRAME;
    }

    // 1. Graceful Wi-Fi Check
    if (!vision_transport_is_network_ready()) {
        printf("[VisionTransport] Network offline. Cannot transmit frame.\n");
        display_set_state(DISPLAY_STATE_WIFI_DISCONNECTED, "Wi-Fi Disconnected");
        return TRANSPORT_ERR_WIFI_DISCONNECTED;
    }

    // 2. Notify Display: Vision Processing State
    display_set_state(DISPLAY_STATE_VISION_PROCESSING, "Sending image...");

#if defined(ESP32) || defined(ARDUINO)
    HTTPClient http;
    http.setTimeout(s_config.http_timeout_ms);

    if (!http.begin(s_config.backend_endpoint)) {
        printf("[VisionTransport] Failed to begin HTTP connection\n");
        display_set_state(DISPLAY_STATE_ERROR, "HTTP Connect Fail");
        return TRANSPORT_ERR_HTTP_CONNECT_FAILED;
    }

    // Set authenticated local API headers
    http.addHeader("Content-Type", "image/jpeg");
    http.addHeader("X-Device-ID", s_config.device_id);
    http.addHeader("X-Device-Token", s_config.device_token);
    
    char reason_str[24];
    snprintf(reason_str, sizeof(reason_str), "%d", frame->trigger_mode);
    http.addHeader("X-Trigger-Reason", reason_str);

    if (context_prompt && strlen(context_prompt) > 0) {
        http.addHeader("X-Context-Prompt", context_prompt);
    }

    // Direct binary POST of JPEG buffer (ephemeral: streams buffer, does not store)
    int http_code = http.POST(frame->data, frame->length);

    if (http_code > 0) {
        if (http_code == 200 || http_code == 201) {
            String payload = http.getString();
            if (response_buffer && response_buffer_size > 0) {
                strncpy(response_buffer, payload.c_str(), response_buffer_size - 1);
                response_buffer[response_buffer_size - 1] = '\0';
            }
            http.end();
            display_set_state(DISPLAY_STATE_VISION_SUCCESS, "Vision Analyzed");
            return TRANSPORT_SUCCESS;
        } else if (http_code == 401 || http_code == 403) {
            http.end();
            display_set_state(DISPLAY_STATE_ERROR, "Auth Rejected");
            return TRANSPORT_ERR_AUTH_REJECTED;
        } else {
            http.end();
            display_set_state(DISPLAY_STATE_ERROR, "Server Error");
            return TRANSPORT_ERR_SERVER_ERROR;
        }
    } else {
        printf("[VisionTransport] HTTP POST failed, error: %s\n", http.errorToString(http_code).c_str());
        http.end();
        display_set_state(DISPLAY_STATE_ERROR, "Transport Timeout");
        return TRANSPORT_ERR_TIMEOUT;
    }
#else
    // Host mock simulation: simulate successful transport
    if (strcmp(s_config.device_token, "test_valid_token") == 0 ||
        strlen(s_config.device_token) > 0) {
        if (response_buffer && response_buffer_size > 0) {
            snprintf(response_buffer, response_buffer_size,
                     "{\"status\":\"success\",\"bytes_received\":%zu,\"analysis\":\"Mock vision analysis complete\"}",
                     frame->length);
        }
        display_set_state(DISPLAY_STATE_VISION_SUCCESS, "Vision Analyzed");
        return TRANSPORT_SUCCESS;
    } else {
        display_set_state(DISPLAY_STATE_ERROR, "Auth Rejected");
        return TRANSPORT_ERR_AUTH_REJECTED;
    }
#endif
}

vision_transport_status_t vision_transport_capture_and_send(const char* context_prompt,
                                                            char* response_buffer,
                                                            size_t response_buffer_size) {
    // 1. Fail-fast if network is down before wasting time capturing
    if (!vision_transport_is_network_ready()) {
        display_set_state(DISPLAY_STATE_WIFI_DISCONNECTED, "Wi-Fi Disconnected");
        return TRANSPORT_ERR_WIFI_DISCONNECTED;
    }

    // 2. Capture fresh on-demand frame
    doruru_frame_t* frame = camera_manager_capture_single(TRIGGER_ON_DEMAND_SINGLE);
    if (!frame) {
        // Display state already set by camera manager
        return TRANSPORT_ERR_INVALID_FRAME;
    }

    // 3. Transmit frame to backend
    vision_transport_status_t status = vision_transport_send_frame(
        frame, context_prompt, response_buffer, response_buffer_size
    );

    // 4. GUARANTEE STRICT IMMEDIATE BUFFER RELEASE
    camera_manager_release_frame(frame);

    return status;
}

