/**
 * @file display_interface.cpp
 * @brief Implementation of display state coordinator and TFT persona manager.
 */

#include "display_interface.h"
#include "ili9341_driver.h"
#include "doruru_persona.h"
#include <string.h>
#include <stdio.h>

#if defined(ESP32) || defined(ARDUINO)
#include <Arduino.h>
#endif

static display_state_callback_t s_state_cb = nullptr;
static display_state_t s_current_state = DISPLAY_STATE_BOOTING;
static char s_last_message[128] = "Booting DORURU...";

static bool s_is_initialized = false;
static bool s_demo_mode_active = false;
static uint32_t s_demo_step_interval_ms = 1500;
static uint32_t s_demo_last_step_ms = 0;
static uint8_t s_demo_step_index = 0;

static uint32_t s_anim_tick = 0;
static uint32_t s_last_anim_update_ms = 0;
static uint32_t s_frame_count = 0;

static bool s_simulate_render_error = false;
static bool s_fallback_active = false;

static const struct {
    display_state_t state;
    const char* message;
} s_demo_sequence[] = {
    {DISPLAY_STATE_BOOTING, "Booting DORURU System..."},
    {DISPLAY_STATE_IDLE_READY, "DORURU Ready & Attentive"},
    {DISPLAY_STATE_WAKE_WORD_DETECTED, "Wake Word: Hey DORURU!"},
    {DISPLAY_STATE_LISTENING, "Listening to Speech PCM..."},
    {DISPLAY_STATE_PROCESSING_THINKING, "Reasoning with Gemini Cloud..."},
    {DISPLAY_STATE_SPEAKING, "Synthesizing Voice Output..."},
    {DISPLAY_STATE_CAMERA_CAPTURE, "OV3660 Frame Captured"},
    {DISPLAY_STATE_VISION_PROCESSING, "Analyzing Visual Scene..."},
    {DISPLAY_STATE_VISION_SUCCESS, "Visual Object Recognized!"},
    {DISPLAY_STATE_MOTOR_MOVING, "Demo Motion (Motors Safe / Off)"},
    {DISPLAY_STATE_WIFI_DISCONNECTED, "Simulated Network Drop"},
    {DISPLAY_STATE_ERROR, "Simulated System Error Alert"},
    {DISPLAY_STATE_EMERGENCY_STOP, "Demo Emergency Stop Engaged"}
};
static const size_t s_demo_sequence_len = sizeof(s_demo_sequence) / sizeof(s_demo_sequence[0]);

bool display_init(void) {
    bool ok = ili9341_driver_init();
    if (!ok) {
        return false;
    }
    doruru_persona_init();
    s_is_initialized = true;

    // Render initial booting state
    display_render_current_state();
    return true;
}

void display_register_state_callback(display_state_callback_t cb) {
    s_state_cb = cb;
}

void display_set_state(display_state_t state, const char* message) {
    s_current_state = state;
    if (message) {
        strncpy(s_last_message, message, sizeof(s_last_message) - 1);
        s_last_message[sizeof(s_last_message) - 1] = '\0';
    } else {
        s_last_message[0] = '\0';
    }

    if (s_state_cb) {
        s_state_cb(state, message);
    }

    if (s_is_initialized) {
        display_render_current_state();
    }
}

display_state_t display_get_current_state(void) {
    return s_current_state;
}

void display_render_current_state(void) {
    s_frame_count++;

    if (s_simulate_render_error) {
        doruru_persona_render_fallback(s_current_state, s_last_message);
        s_fallback_active = true;
        return;
    }

    s_fallback_active = false;
    doruru_persona_render_screen(s_current_state, s_last_message, s_anim_tick);
}

const char* display_state_to_string(display_state_t state) {
    switch (state) {
        case DISPLAY_STATE_BOOTING:             return "BOOTING";
        case DISPLAY_STATE_IDLE_READY:          return "IDLE_READY";
        case DISPLAY_STATE_WAKE_WORD_DETECTED:  return "WAKE_WORD_DETECTED";
        case DISPLAY_STATE_LISTENING:           return "LISTENING";
        case DISPLAY_STATE_PROCESSING_THINKING: return "PROCESSING_THINKING";
        case DISPLAY_STATE_SPEAKING:            return "SPEAKING";
        case DISPLAY_STATE_CAMERA_CAPTURE:      return "CAMERA_CAPTURE";
        case DISPLAY_STATE_VISION_PROCESSING:   return "VISION_PROCESSING";
        case DISPLAY_STATE_VISION_SUCCESS:      return "VISION_SUCCESS";
        case DISPLAY_STATE_WIFI_DISCONNECTED:   return "WIFI_DISCONNECTED";
        case DISPLAY_STATE_ERROR:               return "ERROR";
        case DISPLAY_STATE_MOTOR_MOVING:        return "MOTOR_MOVING";
        case DISPLAY_STATE_EMERGENCY_STOP:      return "EMERGENCY_STOP";
        default:                                return "UNKNOWN";
    }
}

const char* display_get_last_message(void) {
    return s_last_message;
}

void display_set_demo_mode(bool enabled, uint32_t step_interval_ms) {
    s_demo_mode_active = enabled;
    if (step_interval_ms > 0) {
        s_demo_step_interval_ms = step_interval_ms;
    }
    if (enabled) {
        s_demo_step_index = 0;
#if defined(ESP32) || defined(ARDUINO)
        s_demo_last_step_ms = millis();
#else
        s_demo_last_step_ms = 0;
#endif
        display_set_state(s_demo_sequence[0].state, s_demo_sequence[0].message);
    } else {
        display_set_state(DISPLAY_STATE_IDLE_READY, "DORURU Ready");
    }
}

bool display_is_demo_mode(void) {
    return s_demo_mode_active;
}

void display_step_demo(void) {
    s_demo_step_index = (s_demo_step_index + 1) % s_demo_sequence_len;
    display_set_state(s_demo_sequence[s_demo_step_index].state,
                      s_demo_sequence[s_demo_step_index].message);
}

uint32_t display_get_demo_step_interval(void) {
    return s_demo_step_interval_ms;
}

bool display_is_hardware_reset_performed(void) {
    return ili9341_driver_is_reset_performed();
}

void display_set_render_error_simulation(bool simulate_error) {
    s_simulate_render_error = simulate_error;
    if (s_is_initialized) {
        display_render_current_state();
    }
}

bool display_is_fallback_active(void) {
    return s_fallback_active;
}

uint32_t display_get_frame_count(void) {
    return s_frame_count;
}

void display_reset_frame_count(void) {
    s_frame_count = 0;
}

void display_update(void) {
    if (!s_is_initialized) {
        return;
    }

#if defined(ESP32) || defined(ARDUINO)
    uint32_t now = millis();
#else
    static uint32_t s_mock_time = 0;
    s_mock_time += 50;
    uint32_t now = s_mock_time;
#endif

    // 1. Advance Demo Mode if active
    if (s_demo_mode_active) {
        if (now - s_demo_last_step_ms >= s_demo_step_interval_ms) {
            s_demo_last_step_ms = now;
            display_step_demo();
            return;
        }
    }

    // 2. Non-blocking Animation Tick (~20 FPS)
    if (now - s_last_anim_update_ms >= 50) {
        s_last_anim_update_ms = now;
        s_anim_tick++;

        // Only redraw dynamic animated elements
        if (s_current_state == DISPLAY_STATE_BOOTING ||
            s_current_state == DISPLAY_STATE_IDLE_READY ||
            s_current_state == DISPLAY_STATE_LISTENING ||
            s_current_state == DISPLAY_STATE_PROCESSING_THINKING ||
            s_current_state == DISPLAY_STATE_SPEAKING ||
            s_current_state == DISPLAY_STATE_VISION_PROCESSING ||
            s_current_state == DISPLAY_STATE_EMERGENCY_STOP) {
            display_render_current_state();
        }
    }
}
