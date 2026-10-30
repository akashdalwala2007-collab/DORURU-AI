/**
 * @file doruru_persona.h
 * @brief Robot Persona, Expressions, and UI Renderer for DORURU.
 *
 * Provides expressive, lightweight screens for all robot states:
 * - Booting
 * - Ready / Idle (with natural eye blinking)
 * - Wake-word detected (with sparkle accents)
 * - Listening (with dynamic voice equalizer bars)
 * - Processing / Thinking (thoughtful eyes + neural pulse)
 * - Speaking (happy eyes + animated speech mouth)
 * - Camera Capture & Vision Processing (viewfinder + shutter + scan line)
 * - Wi-Fi Disconnected / Offline (droopy eyes + slashed Wi-Fi)
 * - Error (X eyes + warning badge)
 * - Motor Movement (focused eyes + motion chevrons)
 * - Emergency Stop (high-visibility red alert + octagonal STOP sign)
 * - Safe high-contrast fallback screen
 */

#pragma once

#include <stdint.h>
#include <stdbool.h>
#include "display_interface.h"

#ifdef __cplusplus
extern "C" {
#endif

// Persona Lifecycle & Rendering
void doruru_persona_init(void);
void doruru_persona_render_screen(display_state_t state, const char* message, uint32_t anim_tick);
void doruru_persona_render_fallback(display_state_t state, const char* message);

// Custom UI Components & Icons
void doruru_persona_draw_header(const char* state_title, uint16_t status_color);
void doruru_persona_draw_footer(const char* message);
void doruru_persona_draw_wifi_icon(int16_t x, int16_t y, bool connected);
void doruru_persona_draw_camera_icon(int16_t x, int16_t y, bool capturing);
void doruru_persona_draw_stop_sign(int16_t x, int16_t y, int16_t size);
void doruru_persona_draw_warning_triangle(int16_t x, int16_t y, int16_t size);
void doruru_persona_draw_sparkle(int16_t x, int16_t y, int16_t size, uint16_t color);
void doruru_persona_draw_equalizer_bars(int16_t x, int16_t y, uint32_t anim_tick);
void doruru_persona_draw_thinking_dots(int16_t x, int16_t y, uint32_t anim_tick);
void doruru_persona_draw_mouth_wave(int16_t x, int16_t y, uint32_t anim_tick);

#ifdef __cplusplus
}
#endif

