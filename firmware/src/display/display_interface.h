/**
 * @file display_interface.h
 * @brief Lightweight display state interface for DORURU UI notifications.
 * Connects vision, network, audio, and motor modules to the ILI9341 display.
 */

#pragma once

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    DISPLAY_STATE_BOOTING = 0,
    DISPLAY_STATE_IDLE_READY,
    DISPLAY_STATE_WAKE_WORD_DETECTED,
    DISPLAY_STATE_LISTENING,
    DISPLAY_STATE_PROCESSING_THINKING,
    DISPLAY_STATE_SPEAKING,
    DISPLAY_STATE_CAMERA_CAPTURE,       // Shown when camera shutter opens / captures
    DISPLAY_STATE_VISION_PROCESSING,    // Shown when transferring / analyzing image
    DISPLAY_STATE_VISION_SUCCESS,       // Brief success icon/expression
    DISPLAY_STATE_WIFI_DISCONNECTED,    // Wi-Fi offline warning
    DISPLAY_STATE_ERROR,                // General or camera error code
    DISPLAY_STATE_MOTOR_MOVING,
    DISPLAY_STATE_EMERGENCY_STOP
} display_state_t;

typedef void (*display_state_callback_t)(display_state_t state, const char* message);

/**
 * @brief Register callback for display state transitions.
 */
void display_register_state_callback(display_state_callback_t cb);

/**
 * @brief Set current display state with an optional descriptive message.
 */
void display_set_state(display_state_t state, const char* message);

/**
 * @brief Retrieve currently active display state.
 */
display_state_t display_get_current_state(void);

#ifdef __cplusplus
}
#endif

