/**
 * @file display_interface.h
 * @brief Display state coordinator and TFT persona interface for DORURU robot.
 *
 * Coordinates display states across vision, motor, network, and audio modules.
 * Connects the ILI9341 SPI driver and the DORURU robot persona.
 */

#pragma once

#include <stdint.h>
#include <stdbool.h>

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
    DISPLAY_STATE_EMERGENCY_STOP,
    DISPLAY_STATE_COUNT
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

/**
 * @brief Initialize TFT display driver and render initial booting screen.
 */
bool display_init(void);

/**
 * @brief Non-blocking animation and demo mode update tick. Call in loop().
 */
void display_update(void);

/**
 * @brief Force a redraw of the active display screen.
 */
void display_render_current_state(void);

/**
 * @brief Convert display state enum to human-readable string.
 */
const char* display_state_to_string(display_state_t state);

/**
 * @brief Retrieve last message string passed to display.
 */
const char* display_get_last_message(void);

/**
 * @brief Enable or disable automated Display Demo Mode.
 * Cycles through all screens without commanding motor motion.
 */
void display_set_demo_mode(bool enabled, uint32_t step_interval_ms);

/**
 * @brief Query if Display Demo Mode is currently active.
 */
bool display_is_demo_mode(void);

/**
 * @brief Step to the next screen in the demo mode sequence.
 */
void display_step_demo(void);

/**
 * @brief Retrieve configured demo step interval in milliseconds.
 */
uint32_t display_get_demo_step_interval(void);

/**
 * @brief Query whether the hardware reset pulse on D8 (GPIO7) was performed.
 */
bool display_is_hardware_reset_performed(void);

/**
 * @brief Trigger or clear simulated render failure to exercise safe fallback screen.
 */
void display_set_render_error_simulation(bool simulate_error);

/**
 * @brief Query if the safe fallback screen is currently active.
 */
bool display_is_fallback_active(void);

/**
 * @brief Get total number of screen/frame renders performed.
 */
uint32_t display_get_frame_count(void);

/**
 * @brief Reset frame render counter.
 */
void display_reset_frame_count(void);

#ifdef __cplusplus
}
#endif
