/**
 * @file doruru_persona.cpp
 * @brief Implementation of DORURU Robot Persona and State Screens.
 */

#include "doruru_persona.h"
#include "ili9341_driver.h"
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

void doruru_persona_init(void) {
    ili9341_fill_screen(ILI9341_BLACK);
}

void doruru_persona_draw_header(const char* state_title, uint16_t status_color) {
    // Header background banner
    ili9341_fill_rect(0, 0, ILI9341_TFTWIDTH, 26, ILI9341_HEADER_BG);
    ili9341_draw_fast_h_line(0, 26, ILI9341_TFTWIDTH, ILI9341_DARKGREY);

    // Left: Robot Brand Badge
    ili9341_draw_string(8, 7, "[ DORURU ]", ILI9341_CYAN, ILI9341_HEADER_BG, 2);

    // Center: State title
    if (state_title) {
        int title_len = (int)strlen(state_title);
        int16_t title_x = 135;
        if (title_len > 0) {
            title_x = 170 - (title_len * 6);
            if (title_x < 132) title_x = 132;
        }
        ili9341_draw_string(title_x, 9, state_title, ILI9341_WHITE, ILI9341_HEADER_BG, 1);
    }

    // Right: Status indicator dot
    ili9341_fill_circle(305, 13, 5, status_color);
    ili9341_draw_circle(305, 13, 5, ILI9341_WHITE);
}

void doruru_persona_draw_footer(const char* message) {
    // Footer background banner
    ili9341_fill_rect(0, 212, ILI9341_TFTWIDTH, 28, ILI9341_HEADER_BG);
    ili9341_draw_fast_h_line(0, 211, ILI9341_TFTWIDTH, ILI9341_DARKGREY);

    if (message && message[0] != '\0') {
        int len = (int)strlen(message);
        int16_t text_x = 160 - (len * 3);
        if (text_x < 8) text_x = 8;
        ili9341_draw_string(text_x, 221, message, ILI9341_LIGHTGREY, ILI9341_HEADER_BG, 1);
    }
}

void doruru_persona_draw_wifi_icon(int16_t x, int16_t y, bool connected) {
    uint16_t color = connected ? ILI9341_GREEN : ILI9341_ORANGE;
    // Concentric arcs
    ili9341_draw_circle(x, y + 10, 16, color);
    ili9341_draw_circle(x, y + 10, 10, color);
    ili9341_fill_circle(x, y + 10, 3, color);

    // Erase bottom half of arcs for standard Wi-Fi fan shape
    ili9341_fill_rect(x - 18, y + 11, 36, 12, ILI9341_BLACK);

    if (!connected) {
        // Red diagonal strike-through slash
        ili9341_draw_line(x - 14, y + 16, x + 14, y - 6, ILI9341_RED);
        ili9341_draw_line(x - 13, y + 16, x + 15, y - 6, ILI9341_RED);
    }
}

void doruru_persona_draw_stop_sign(int16_t x, int16_t y, int16_t size) {
    // Draw filled red octagon
    int16_t half = size / 2;
    int16_t q = size / 4;

    ili9341_fill_rect(x - half + q, y - half, half, size, ILI9341_RED);
    ili9341_fill_rect(x - half, y - half + q, size, half, ILI9341_RED);

    // Corner triangles to smooth the octagon
    ili9341_draw_line(x - half + q, y - half, x - half, y - half + q, ILI9341_WHITE);
    ili9341_draw_line(x + half - q, y - half, x + half, y - half + q, ILI9341_WHITE);
    ili9341_draw_line(x - half + q, y + half, x - half, y + half - q, ILI9341_WHITE);
    ili9341_draw_line(x + half - q, y + half, x + half, y + half - q, ILI9341_WHITE);

    // White border
    ili9341_draw_rect(x - half + q, y - half, half, size, ILI9341_WHITE);
    ili9341_draw_rect(x - half, y - half + q, size, half, ILI9341_WHITE);

    // Center text "STOP"
    ili9341_draw_string(x - 18, y - 6, "STOP", ILI9341_WHITE, ILI9341_RED, 2);
}

void doruru_persona_draw_warning_triangle(int16_t x, int16_t y, int16_t size) {
    int16_t half = size / 2;
    // Outer yellow triangle lines
    for (int16_t i = 0; i < 3; i++) {
        ili9341_draw_line(x, y - half + i, x - half + i, y + half - i, ILI9341_YELLOW);
        ili9341_draw_line(x, y - half + i, x + half - i, y + half - i, ILI9341_YELLOW);
        ili9341_draw_line(x - half + i, y + half - i, x + half - i, y + half - i, ILI9341_YELLOW);
    }
    // Exclamation mark in center
    ili9341_draw_fast_v_line(x, y - half + 8, half - 2, ILI9341_RED);
    ili9341_draw_fast_v_line(x - 1, y - half + 8, half - 2, ILI9341_RED);
    ili9341_draw_pixel(x, y + half - 4, ILI9341_RED);
    ili9341_draw_pixel(x - 1, y + half - 4, ILI9341_RED);
}

void doruru_persona_draw_sparkle(int16_t x, int16_t y, int16_t size, uint16_t color) {
    ili9341_draw_fast_h_line(x - size, y, 2 * size + 1, color);
    ili9341_draw_fast_v_line(x, y - size, 2 * size + 1, color);
    ili9341_draw_line(x - size / 2, y - size / 2, x + size / 2, y + size / 2, color);
    ili9341_draw_line(x - size / 2, y + size / 2, x + size / 2, y - size / 2, color);
}

void doruru_persona_draw_equalizer_bars(int16_t x, int16_t y, uint32_t anim_tick) {
    // 5 vertical voice equalizer bars
    const int16_t bar_offsets[] = {-28, -14, 0, 14, 28};
    const int16_t bar_heights[4][5] = {
        {8, 16, 26, 14, 8},
        {14, 24, 12, 22, 10},
        {20, 10, 24, 8, 18},
        {10, 20, 14, 26, 12}
    };
    uint8_t pattern = anim_tick % 4;

    // Clear previous equalizer region
    ili9341_fill_rect(x - 35, y - 28, 70, 32, ILI9341_BLACK);

    for (int i = 0; i < 5; i++) {
        int16_t bx = x + bar_offsets[i];
        int16_t bh = bar_heights[pattern][i];
        ili9341_fill_round_rect(bx - 3, y - bh, 6, bh, 2, ILI9341_CYAN);
    }
}

void doruru_persona_draw_thinking_dots(int16_t x, int16_t y, uint32_t anim_tick) {
    ili9341_fill_rect(x - 30, y - 8, 60, 16, ILI9341_BLACK);
    uint8_t active_dot = anim_tick % 3;

    for (int i = 0; i < 3; i++) {
        int16_t dx = x + (i - 1) * 20;
        uint16_t color = (i == active_dot) ? ILI9341_WHITE : ILI9341_DARKCYAN;
        int16_t radius = (i == active_dot) ? 5 : 4;
        ili9341_fill_circle(dx, y, radius, color);
    }
}

void doruru_persona_draw_mouth_wave(int16_t x, int16_t y, uint32_t anim_tick) {
    ili9341_fill_rect(x - 35, y - 12, 70, 24, ILI9341_BLACK);
    const int16_t mouth_h[] = {6, 14, 20, 12, 18, 8};
    int16_t h = mouth_h[anim_tick % 6];
    int16_t w = 54 + (h / 2);
    ili9341_fill_round_rect(x - w / 2, y - h / 2, w, h, h / 2, ILI9341_GREEN);
    ili9341_draw_round_rect(x - w / 2, y - h / 2, w, h, h / 2, ILI9341_WHITE);
}

void doruru_persona_render_screen(display_state_t state, const char* message, uint32_t anim_tick) {
    const int16_t left_eye_x = 65;
    const int16_t right_eye_x = 187;
    const int16_t eye_y = 60;
    const int16_t eye_w = 68;
    const int16_t eye_h = 65;
    const int16_t eye_r = 18;

    switch (state) {
        case DISPLAY_STATE_BOOTING: {
            doruru_persona_draw_header("BOOTING", ILI9341_YELLOW);
            ili9341_fill_rect(0, 27, ILI9341_TFTWIDTH, 184, ILI9341_BLACK);

            // Thin slit eyes gently opening
            ili9341_fill_round_rect(left_eye_x, eye_y + 26, eye_w, 10, 4, ILI9341_CYAN);
            ili9341_fill_round_rect(right_eye_x, eye_y + 26, eye_w, 10, 4, ILI9341_CYAN);

            // Central Branding Text
            ili9341_draw_string(68, 115, "DORURU AI ASSISTANT", ILI9341_WHITE, ILI9341_BLACK, 2);
            ili9341_draw_string(88, 140, "ESP32-S3 SENSE v1.0", ILI9341_LIGHTGREY, ILI9341_BLACK, 1);

            // Progress bar
            int16_t pb_w = 180;
            int16_t pb_h = 8;
            int16_t pb_x = 70;
            int16_t pb_y = 165;
            ili9341_draw_round_rect(pb_x, pb_y, pb_w, pb_h, 3, ILI9341_DARKGREY);
            int16_t fill_w = (int16_t)((anim_tick % 10 + 1) * 18);
            if (fill_w > pb_w - 4) fill_w = pb_w - 4;
            ili9341_fill_round_rect(pb_x + 2, pb_y + 2, fill_w, pb_h - 4, 2, ILI9341_CYAN);

            doruru_persona_draw_footer(message ? message : "Starting system modules...");
            break;
        }

        case DISPLAY_STATE_IDLE_READY: {
            doruru_persona_draw_header("READY", ILI9341_GREEN);
            ili9341_fill_rect(0, 27, ILI9341_TFTWIDTH, 184, ILI9341_BLACK);

            // Natural Blink Animation (blink every ~50 ticks for 2 ticks)
            bool is_blinking = ((anim_tick % 50) >= 48);
            if (is_blinking) {
                // Closed eyelid slit
                ili9341_fill_round_rect(left_eye_x, eye_y + 28, eye_w, 8, 3, ILI9341_CYAN);
                ili9341_fill_round_rect(right_eye_x, eye_y + 28, eye_w, 8, 3, ILI9341_CYAN);
            } else {
                // Wide friendly glowing eyes
                ili9341_fill_round_rect(left_eye_x, eye_y, eye_w, eye_h, eye_r, ILI9341_CYAN);
                ili9341_fill_round_rect(right_eye_x, eye_y, eye_w, eye_h, eye_r, ILI9341_CYAN);

                // Specular reflection highlight in top-right of both eyes
                ili9341_fill_circle(left_eye_x + 48, eye_y + 16, 5, ILI9341_WHITE);
                ili9341_fill_circle(right_eye_x + 48, eye_y + 16, 5, ILI9341_WHITE);

                // Gentle subtle smile arc below eyes
                ili9341_draw_fast_h_line(135, 155, 50, ILI9341_CYAN);
                ili9341_draw_pixel(134, 154, ILI9341_CYAN);
                ili9341_draw_pixel(185, 154, ILI9341_CYAN);
            }

            ili9341_draw_string(105, 178, "Ready & Attentive", ILI9341_LIGHTGREY, ILI9341_BLACK, 1);
            doruru_persona_draw_footer(message ? message : "Say 'Hey DORURU' or command motion");
            break;
        }

        case DISPLAY_STATE_WAKE_WORD_DETECTED: {
            doruru_persona_draw_header("WAKE CONFIRMED", ILI9341_YELLOW);
            ili9341_fill_rect(0, 27, ILI9341_TFTWIDTH, 184, ILI9341_BLACK);

            // Alert wide yellow eyes
            ili9341_fill_round_rect(left_eye_x - 2, eye_y - 2, eye_w + 4, eye_h + 4, eye_r, ILI9341_YELLOW);
            ili9341_fill_round_rect(right_eye_x - 2, eye_y - 2, eye_w + 4, eye_h + 4, eye_r, ILI9341_YELLOW);
            ili9341_fill_circle(left_eye_x + 48, eye_y + 16, 6, ILI9341_WHITE);
            ili9341_fill_circle(right_eye_x + 48, eye_y + 16, 6, ILI9341_WHITE);

            // Sparkle accents
            doruru_persona_draw_sparkle(32, 90, 8, ILI9341_YELLOW);
            doruru_persona_draw_sparkle(288, 90, 8, ILI9341_YELLOW);

            ili9341_draw_string(75, 155, "Wake Word Detected!", ILI9341_YELLOW, ILI9341_BLACK, 2);
            ili9341_draw_string(120, 180, "Listening...", ILI9341_WHITE, ILI9341_BLACK, 1);
            doruru_persona_draw_footer(message ? message : "DORURU awake and listening");
            break;
        }

        case DISPLAY_STATE_LISTENING: {
            doruru_persona_draw_header("LISTENING", ILI9341_CYAN);
            ili9341_fill_rect(0, 27, ILI9341_TFTWIDTH, 184, ILI9341_BLACK);

            // Attentive eyes
            ili9341_fill_round_rect(left_eye_x, eye_y, eye_w, eye_h, eye_r, ILI9341_CYAN);
            ili9341_fill_round_rect(right_eye_x, eye_y, eye_w, eye_h, eye_r, ILI9341_CYAN);
            ili9341_fill_circle(left_eye_x + 34, eye_y + 44, 5, ILI9341_WHITE); // Eyes looking slightly down
            ili9341_fill_circle(right_eye_x + 34, eye_y + 44, 5, ILI9341_WHITE);

            // Dynamic voice equalizer bars
            doruru_persona_draw_equalizer_bars(160, 160, anim_tick);

            ili9341_draw_string(85, 178, "Capturing voice PCM...", ILI9341_LIGHTGREY, ILI9341_BLACK, 1);
            doruru_persona_draw_footer(message ? message : "Speak your question or instruction");
            break;
        }

        case DISPLAY_STATE_PROCESSING_THINKING: {
            doruru_persona_draw_header("THINKING", ILI9341_CYAN);
            ili9341_fill_rect(0, 27, ILI9341_TFTWIDTH, 184, ILI9341_BLACK);

            // Thoughtful eyes: one eye tilted/raised
            ili9341_fill_round_rect(left_eye_x, eye_y - 6, eye_w, eye_h - 4, eye_r, ILI9341_CYAN);
            ili9341_fill_round_rect(right_eye_x, eye_y + 4, eye_w, eye_h - 4, eye_r, ILI9341_CYAN);
            ili9341_fill_circle(left_eye_x + 48, eye_y + 12, 5, ILI9341_WHITE);
            ili9341_fill_circle(right_eye_x + 48, eye_y + 20, 5, ILI9341_WHITE);

            // Pulsing thinking dots
            doruru_persona_draw_thinking_dots(160, 155, anim_tick);

            ili9341_draw_string(95, 178, "Reasoning with Gemini...", ILI9341_LIGHTGREY, ILI9341_BLACK, 1);
            doruru_persona_draw_footer(message ? message : "Processing speech transcription...");
            break;
        }

        case DISPLAY_STATE_SPEAKING: {
            doruru_persona_draw_header("SPEAKING", ILI9341_GREEN);
            ili9341_fill_rect(0, 27, ILI9341_TFTWIDTH, 184, ILI9341_BLACK);

            // Happy arched eyes (^ ^)
            ili9341_fill_round_rect(left_eye_x, eye_y, eye_w, eye_h / 2 + 6, 12, ILI9341_GREEN);
            ili9341_fill_round_rect(right_eye_x, eye_y, eye_w, eye_h / 2 + 6, 12, ILI9341_GREEN);
            ili9341_fill_circle(left_eye_x + 44, eye_y + 12, 4, ILI9341_WHITE);
            ili9341_fill_circle(right_eye_x + 44, eye_y + 12, 4, ILI9341_WHITE);

            // Animated speaking mouth
            doruru_persona_draw_mouth_wave(160, 145, anim_tick);

            ili9341_draw_string(88, 178, "Playing audio on I2S_1", ILI9341_LIGHTGREY, ILI9341_BLACK, 1);
            doruru_persona_draw_footer(message ? message : "Piper TTS audio output active");
            break;
        }

        case DISPLAY_STATE_CAMERA_CAPTURE: {
            doruru_persona_draw_header("VISION CAPTURE", ILI9341_YELLOW);
            ili9341_fill_rect(0, 27, ILI9341_TFTWIDTH, 184, ILI9341_BLACK);

            // Viewfinder reticle brackets
            const int16_t bl = 16;
            ili9341_draw_fast_h_line(30, 40, bl, ILI9341_YELLOW);
            ili9341_draw_fast_v_line(30, 40, bl, ILI9341_YELLOW);
            ili9341_draw_fast_h_line(290 - bl, 40, bl, ILI9341_YELLOW);
            ili9341_draw_fast_v_line(290, 40, bl, ILI9341_YELLOW);
            ili9341_draw_fast_h_line(30, 190, bl, ILI9341_YELLOW);
            ili9341_draw_fast_v_line(30, 190 - bl, bl, ILI9341_YELLOW);
            ili9341_draw_fast_h_line(290 - bl, 190, bl, ILI9341_YELLOW);
            ili9341_draw_fast_v_line(290, 190 - bl, bl, ILI9341_YELLOW);

            // Camera Shutter Aperture icon in center
            ili9341_draw_circle(160, 105, 30, ILI9341_WHITE);
            ili9341_fill_circle(160, 105, 18, ILI9341_CYAN);
            ili9341_fill_circle(160, 105, 6, ILI9341_BLACK);

            ili9341_draw_string(60, 155, "OV3660 FRAME CAPTURE", ILI9341_YELLOW, ILI9341_BLACK, 2);
            ili9341_draw_string(95, 180, "Allocating 640x480 FB", ILI9341_LIGHTGREY, ILI9341_BLACK, 1);
            doruru_persona_draw_footer(message ? message : "On-demand camera shutter open");
            break;
        }

        case DISPLAY_STATE_VISION_PROCESSING: {
            doruru_persona_draw_header("ANALYZING SCENE", ILI9341_CYAN);
            ili9341_fill_rect(0, 27, ILI9341_TFTWIDTH, 184, ILI9341_BLACK);

            // Viewfinder brackets
            ili9341_draw_rect(30, 40, 260, 140, ILI9341_DARKCYAN);

            // Sweeping laser scan line
            int16_t scan_y = 45 + (int16_t)((anim_tick % 16) * 8);
            if (scan_y > 175) scan_y = 175;
            ili9341_draw_fast_h_line(32, scan_y, 256, ILI9341_CYAN);
            ili9341_draw_fast_h_line(32, scan_y - 1, 256, ILI9341_WHITE);

            ili9341_draw_string(65, 95, "GEMINI MULTIMODAL", ILI9341_WHITE, ILI9341_BLACK, 2);
            ili9341_draw_string(90, 125, "Uploading JPEG payload...", ILI9341_CYAN, ILI9341_BLACK, 1);
            doruru_persona_draw_footer(message ? message : "Transferring image to local backend");
            break;
        }

        case DISPLAY_STATE_VISION_SUCCESS: {
            doruru_persona_draw_header("VISION COMPLETE", ILI9341_GREEN);
            ili9341_fill_rect(0, 27, ILI9341_TFTWIDTH, 184, ILI9341_BLACK);

            // Smiling eyes
            ili9341_fill_round_rect(left_eye_x, eye_y, eye_w, eye_h / 2, 10, ILI9341_GREEN);
            ili9341_fill_round_rect(right_eye_x, eye_y, eye_w, eye_h / 2, 10, ILI9341_GREEN);

            // Green Checkmark badge
            ili9341_fill_circle(160, 135, 20, ILI9341_GREEN);
            ili9341_draw_line(150, 135, 157, 143, ILI9341_WHITE);
            ili9341_draw_line(151, 135, 157, 143, ILI9341_WHITE);
            ili9341_draw_line(157, 143, 172, 127, ILI9341_WHITE);
            ili9341_draw_line(157, 144, 172, 128, ILI9341_WHITE);

            ili9341_draw_string(65, 172, "Image Recognized Successfully", ILI9341_WHITE, ILI9341_BLACK, 1);
            doruru_persona_draw_footer(message ? message : "Vision pipeline complete");
            break;
        }

        case DISPLAY_STATE_WIFI_DISCONNECTED: {
            doruru_persona_draw_header("OFFLINE", ILI9341_ORANGE);
            ili9341_fill_rect(0, 27, ILI9341_TFTWIDTH, 184, ILI9341_BLACK);

            // Sad droopy eyes (downward angled eyebrows)
            ili9341_fill_round_rect(left_eye_x, eye_y + 10, eye_w, eye_h - 10, eye_r, ILI9341_ORANGE);
            ili9341_fill_round_rect(right_eye_x, eye_y + 10, eye_w, eye_h - 10, eye_r, ILI9341_ORANGE);
            // Angled cutout on inner top corners
            for (int16_t i = 0; i < 20; i++) {
                ili9341_draw_fast_h_line(left_eye_x + eye_w - 20 + i, eye_y + 10 + i, 20 - i, ILI9341_BLACK);
                ili9341_draw_fast_h_line(right_eye_x, eye_y + 10 + i, 20 - i, ILI9341_BLACK);
            }

            // Slashed Wi-Fi icon in center
            doruru_persona_draw_wifi_icon(160, 135, false);

            ili9341_draw_string(80, 160, "Wi-Fi Disconnected", ILI9341_ORANGE, ILI9341_BLACK, 2);
            ili9341_draw_string(72, 184, "Offline Local Safety Active", ILI9341_YELLOW, ILI9341_BLACK, 1);
            doruru_persona_draw_footer(message ? message : "Attempting exponential backoff reconnect...");
            break;
        }

        case DISPLAY_STATE_ERROR: {
            doruru_persona_draw_header("SYSTEM ALERT", ILI9341_RED);
            ili9341_fill_rect(0, 27, ILI9341_TFTWIDTH, 184, ILI9341_BLACK);

            // "X" eyes
            int16_t th = 4;
            for (int16_t i = -th/2; i <= th/2; i++) {
                ili9341_draw_line(left_eye_x + 10 + i, eye_y + 10, left_eye_x + eye_w - 10 + i, eye_y + eye_h - 10, ILI9341_RED);
                ili9341_draw_line(left_eye_x + 10 + i, eye_y + eye_h - 10, left_eye_x + eye_w - 10 + i, eye_y + 10, ILI9341_RED);
                ili9341_draw_line(right_eye_x + 10 + i, eye_y + 10, right_eye_x + eye_w - 10 + i, eye_y + eye_h - 10, ILI9341_RED);
                ili9341_draw_line(right_eye_x + 10 + i, eye_y + eye_h - 10, right_eye_x + eye_w - 10 + i, eye_y + 10, ILI9341_RED);
            }

            // Warning badge
            doruru_persona_draw_warning_triangle(160, 125, 34);

            ili9341_draw_string(92, 155, "! SYSTEM ERROR !", ILI9341_RED, ILI9341_BLACK, 2);
            doruru_persona_draw_footer(message ? message : "Check serial console for diagnostic trace");
            break;
        }

        case DISPLAY_STATE_MOTOR_MOVING: {
            doruru_persona_draw_header("MOTION ACTIVE", ILI9341_YELLOW);
            ili9341_fill_rect(0, 27, ILI9341_TFTWIDTH, 184, ILI9341_BLACK);

            // Determined focused eyes
            ili9341_fill_round_rect(left_eye_x, eye_y + 8, eye_w, eye_h - 8, 12, ILI9341_YELLOW);
            ili9341_fill_round_rect(right_eye_x, eye_y + 8, eye_w, eye_h - 8, 12, ILI9341_YELLOW);
            ili9341_fill_circle(left_eye_x + 34, eye_y + 36, 6, ILI9341_BLACK);
            ili9341_fill_circle(right_eye_x + 34, eye_y + 36, 6, ILI9341_BLACK);

            // Motion Chevrons in center: >>>
            ili9341_draw_string(110, 125, ">>> MOVING >>>", ILI9341_YELLOW, ILI9341_BLACK, 2);
            ili9341_draw_string(68, 160, "MX1508 H-Bridge PWM Active", ILI9341_WHITE, ILI9341_BLACK, 1);
            ili9341_draw_string(82, 178, "Watchdog Timeout Enforced", ILI9341_LIGHTGREY, ILI9341_BLACK, 1);
            doruru_persona_draw_footer(message ? message : "Bounded motion in progress - keep clear");
            break;
        }

        case DISPLAY_STATE_EMERGENCY_STOP: {
            doruru_persona_draw_header("! EMERGENCY STOP !", ILI9341_RED);
            ili9341_fill_rect(0, 27, ILI9341_TFTWIDTH, 184, ILI9341_BLACK);

            // Flashing border
            bool flash = (anim_tick % 2 == 0);
            ili9341_draw_rect(6, 32, ILI9341_TFTWIDTH - 12, 174, flash ? ILI9341_RED : ILI9341_YELLOW);
            ili9341_draw_rect(7, 33, ILI9341_TFTWIDTH - 14, 172, flash ? ILI9341_RED : ILI9341_YELLOW);

            // Octagonal STOP sign in center
            doruru_persona_draw_stop_sign(160, 95, 52);

            ili9341_draw_string(45, 140, "EMERGENCY STOP ENGAGED", ILI9341_RED, ILI9341_BLACK, 2);
            ili9341_draw_string(65, 170, "Hardware Watchdog Overridden", ILI9341_WHITE, ILI9341_BLACK, 1);
            ili9341_draw_string(85, 185, "All Motor Pins Driven LOW", ILI9341_LIGHTGREY, ILI9341_BLACK, 1);
            doruru_persona_draw_footer(message ? message : "Motors locked. Send 'C' to clear e-stop.");
            break;
        }

        default: {
            doruru_persona_render_fallback(state, message);
            break;
        }
    }
}

void doruru_persona_render_fallback(display_state_t state, const char* message) {
    ili9341_fill_screen(ILI9341_BLACK);

    // High-contrast solid double border
    ili9341_draw_rect(10, 10, ILI9341_TFTWIDTH - 20, ILI9341_HEIGHT - 20, ILI9341_WHITE);
    ili9341_draw_rect(12, 12, ILI9341_TFTWIDTH - 24, ILI9341_HEIGHT - 24, ILI9341_WHITE);

    ili9341_draw_string(25, 30, "[ SAFE DISPLAY FALLBACK ]", ILI9341_YELLOW, ILI9341_BLACK, 2);

    char state_buf[48];
    snprintf(state_buf, sizeof(state_buf), "STATE: %d", (int)state);
    ili9341_draw_string(30, 75, state_buf, ILI9341_WHITE, ILI9341_BLACK, 2);

    ili9341_draw_string(30, 120, "ROBOT: DORURU", ILI9341_CYAN, ILI9341_BLACK, 2);

    if (message && message[0] != '\0') {
        ili9341_draw_string(30, 160, "MSG:", ILI9341_LIGHTGREY, ILI9341_BLACK, 1);
        ili9341_draw_string(70, 160, message, ILI9341_WHITE, ILI9341_BLACK, 1);
    }

    ili9341_draw_string(30, 195, "Safe Mode: Motor safety & logic intact.", ILI9341_LIGHTGREY, ILI9341_BLACK, 1);
}

