/**
 * @file ili9341_driver.h
 * @brief Low-level SPI display driver for ILI9341 2.8" TFT on Seeed XIAO ESP32-S3 Sense.
 *
 * Hardware & SPI Configuration:
 * - Controller: Seeed Studio XIAO ESP32-S3 Sense
 * - Display: 2.8-inch ILI9341 SPI TFT (240x320, Landscape 320x240)
 * - Confirmed Pin Mapping (Preserve Exactly):
 *   - SCK   = GPIO9  (D10)
 *   - MOSI  = GPIO8  (D9)
 *   - MISO  = -1 (Not connected)
 *   - CS    = -1 (Physical CS pin hardwired to GND; permanently selected)
 *   - D/C   = GPIO44 (D7) - Protected from UART0 serial activity via USB CDC logging
 *   - RESET = GPIO7  (D8) - Hardware reset pulse executed during driver init
 *   - VCC   = VBUS/5V (breakout integrates onboard 3.3V LDO regulator; 3.3V SPI logic)
 *   - LED   = 3.3V (backlight power)
 *
 * NOTE: If hardware display desynchronization occurs on this specific ILI9341 module,
 * report it rather than suggesting unapproved rewiring.
 */

#pragma once

#include <stdint.h>
#include <stdbool.h>
#include "board_pins.h"

#ifdef __cplusplus
extern "C" {
#endif

// Display Dimensions in Landscape Orientation
#define ILI9341_TFTWIDTH   320
#define ILI9341_TFTHEIGHT  240
#define ILI9341_WIDTH      ILI9341_TFTWIDTH
#define ILI9341_HEIGHT     ILI9341_TFTHEIGHT

// 16-bit RGB565 Color Definitions
#define ILI9341_BLACK       0x0000
#define ILI9341_NAVY        0x000F
#define ILI9341_DARKGREEN   0x03E0
#define ILI9341_DARKCYAN    0x03EF
#define ILI9341_MAROON      0x7800
#define ILI9341_PURPLE      0x780F
#define ILI9341_OLIVE       0x7BE0
#define ILI9341_LIGHTGREY   0xC618
#define ILI9341_DARKGREY    0x39E7
#define ILI9341_BLUE        0x001F
#define ILI9341_GREEN       0x07E0
#define ILI9341_CYAN        0x07FF
#define ILI9341_RED         0xF800
#define ILI9341_MAGENTA     0xF81F
#define ILI9341_YELLOW      0xFFE0
#define ILI9341_WHITE       0xFFFF
#define ILI9341_ORANGE      0xFD20
#define ILI9341_GREENYELLOW 0xAFE5
#define ILI9341_HEADER_BG   0x10A4  // Slate gray header
#define ILI9341_BG_DARK     0x0000  // Deep sleek black

// Driver Lifecycle
bool ili9341_driver_init(void);
void ili9341_driver_hardware_reset(void);
bool ili9341_driver_is_initialized(void);
bool ili9341_driver_is_reset_performed(void);

// 2D Rasterization Primitives
void ili9341_fill_screen(uint16_t color);
void ili9341_draw_pixel(int16_t x, int16_t y, uint16_t color);
void ili9341_draw_fast_h_line(int16_t x, int16_t y, int16_t w, uint16_t color);
void ili9341_draw_fast_v_line(int16_t x, int16_t y, int16_t h, uint16_t color);
void ili9341_fill_rect(int16_t x, int16_t y, int16_t w, int16_t h, uint16_t color);
void ili9341_draw_rect(int16_t x, int16_t y, int16_t w, int16_t h, uint16_t color);
void ili9341_fill_circle(int16_t x0, int16_t y0, int16_t r, uint16_t color);
void ili9341_draw_circle(int16_t x0, int16_t y0, int16_t r, uint16_t color);
void ili9341_fill_round_rect(int16_t x, int16_t y, int16_t w, int16_t h, int16_t r, uint16_t color);
void ili9341_draw_round_rect(int16_t x, int16_t y, int16_t w, int16_t h, int16_t r, uint16_t color);
void ili9341_draw_line(int16_t x0, int16_t y0, int16_t x1, int16_t y1, uint16_t color);
void ili9341_draw_char(int16_t x, int16_t y, char c, uint16_t color, uint16_t bg, uint8_t size);
void ili9341_draw_string(int16_t x, int16_t y, const char* str, uint16_t color, uint16_t bg, uint8_t size);

// Test & Mock Inspection API
uint32_t ili9341_get_op_count(void);
void ili9341_reset_op_count(void);

#ifdef __cplusplus
}
#endif
