/**
 * @file ili9341_driver.cpp
 * @brief Implementation of custom SPI display driver for ILI9341 2.8" TFT.
 */

#include "ili9341_driver.h"
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

#if defined(ESP32) || defined(ARDUINO)
#include <Arduino.h>
#include <SPI.h>
#endif

// Driver state variables
static bool s_is_initialized = false;
static bool s_hardware_reset_performed = false;
static uint32_t s_op_count = 0;

// Standard 5x7 ASCII Bitmap Font (Chars 0x20 ' ' through 0x7E '~')
// 5 bytes per character; columns are bit-mapped vertically
static const uint8_t s_font5x7[] = {
    0x00, 0x00, 0x00, 0x00, 0x00, // 0x20 Space
    0x00, 0x00, 0x5F, 0x00, 0x00, // 0x21 !
    0x00, 0x07, 0x00, 0x07, 0x00, // 0x22 "
    0x14, 0x7F, 0x14, 0x7F, 0x14, // 0x23 #
    0x24, 0x2A, 0x7F, 0x2A, 0x12, // 0x24 $
    0x23, 0x13, 0x08, 0x64, 0x62, // 0x25 %
    0x36, 0x49, 0x55, 0x22, 0x50, // 0x26 &
    0x00, 0x05, 0x03, 0x00, 0x00, // 0x27 '
    0x00, 0x1C, 0x22, 0x41, 0x00, // 0x28 (
    0x00, 0x41, 0x22, 0x1C, 0x00, // 0x29 )
    0x08, 0x2A, 0x1C, 0x2A, 0x08, // 0x2A *
    0x08, 0x08, 0x3E, 0x08, 0x08, // 0x2B +
    0x00, 0x50, 0x30, 0x00, 0x00, // 0x2C ,
    0x08, 0x08, 0x08, 0x08, 0x08, // 0x2D -
    0x00, 0x60, 0x60, 0x00, 0x00, // 0x2E .
    0x20, 0x10, 0x08, 0x04, 0x02, // 0x2F /
    0x3E, 0x51, 0x49, 0x45, 0x3E, // 0x30 0
    0x00, 0x42, 0x7F, 0x40, 0x00, // 0x31 1
    0x42, 0x61, 0x51, 0x49, 0x46, // 0x32 2
    0x21, 0x41, 0x45, 0x4B, 0x31, // 0x33 3
    0x18, 0x14, 0x12, 0x7F, 0x10, // 0x34 4
    0x27, 0x45, 0x45, 0x45, 0x39, // 0x35 5
    0x3C, 0x4A, 0x49, 0x49, 0x30, // 0x36 6
    0x01, 0x71, 0x09, 0x05, 0x03, // 0x37 7
    0x36, 0x49, 0x49, 0x49, 0x36, // 0x38 8
    0x06, 0x49, 0x49, 0x29, 0x1E, // 0x39 9
    0x00, 0x36, 0x36, 0x00, 0x00, // 0x3A :
    0x00, 0x56, 0x36, 0x00, 0x00, // 0x3B ;
    0x00, 0x08, 0x14, 0x22, 0x41, // 0x3C <
    0x14, 0x14, 0x14, 0x14, 0x14, // 0x3D =
    0x41, 0x22, 0x14, 0x08, 0x00, // 0x3E >
    0x02, 0x01, 0x51, 0x09, 0x06, // 0x3F ?
    0x32, 0x49, 0x79, 0x41, 0x3E, // 0x40 @
    0x7E, 0x11, 0x11, 0x11, 0x7E, // 0x41 A
    0x7F, 0x49, 0x49, 0x49, 0x36, // 0x42 B
    0x3E, 0x41, 0x41, 0x41, 0x22, // 0x43 C
    0x7F, 0x41, 0x41, 0x22, 0x1C, // 0x44 D
    0x7F, 0x49, 0x49, 0x49, 0x41, // 0x45 E
    0x7F, 0x09, 0x09, 0x01, 0x01, // 0x46 F
    0x3E, 0x41, 0x41, 0x51, 0x32, // 0x47 G
    0x7F, 0x08, 0x08, 0x08, 0x7F, // 0x48 H
    0x00, 0x41, 0x7F, 0x41, 0x00, // 0x49 I
    0x20, 0x40, 0x41, 0x3F, 0x01, // 0x4A J
    0x7F, 0x08, 0x14, 0x22, 0x41, // 0x4B K
    0x7F, 0x40, 0x40, 0x40, 0x40, // 0x4C L
    0x7F, 0x02, 0x04, 0x02, 0x7F, // 0x4D M
    0x7F, 0x04, 0x08, 0x10, 0x7F, // 0x4E N
    0x3E, 0x41, 0x41, 0x41, 0x3E, // 0x4F O
    0x7F, 0x09, 0x09, 0x09, 0x06, // 0x50 P
    0x3E, 0x41, 0x51, 0x21, 0x5E, // 0x51 Q
    0x7F, 0x09, 0x19, 0x29, 0x46, // 0x52 R
    0x46, 0x49, 0x49, 0x49, 0x31, // 0x53 S
    0x01, 0x01, 0x7F, 0x01, 0x01, // 0x54 T
    0x3F, 0x40, 0x40, 0x40, 0x3F, // 0x55 U
    0x1F, 0x20, 0x40, 0x20, 0x1F, // 0x56 V
    0x7F, 0x20, 0x18, 0x20, 0x7F, // 0x57 W
    0x63, 0x14, 0x08, 0x14, 0x63, // 0x58 X
    0x03, 0x04, 0x78, 0x04, 0x03, // 0x59 Y
    0x61, 0x51, 0x49, 0x45, 0x43, // 0x5A Z
    0x00, 0x00, 0x7F, 0x41, 0x41, // 0x5B [
    0x02, 0x04, 0x08, 0x10, 0x20, // 0x5C Backslash
    0x41, 0x41, 0x7F, 0x00, 0x00, // 0x5D ]
    0x04, 0x02, 0x01, 0x02, 0x04, // 0x5E ^
    0x40, 0x40, 0x40, 0x40, 0x40, // 0x5F _
    0x00, 0x01, 0x02, 0x04, 0x00, // 0x60 `
    0x20, 0x54, 0x54, 0x54, 0x78, // 0x61 a
    0x7F, 0x48, 0x44, 0x44, 0x38, // 0x62 b
    0x38, 0x44, 0x44, 0x44, 0x20, // 0x63 c
    0x38, 0x44, 0x44, 0x48, 0x7F, // 0x64 d
    0x38, 0x54, 0x54, 0x54, 0x18, // 0x65 e
    0x08, 0x7E, 0x09, 0x01, 0x02, // 0x66 f
    0x08, 0x14, 0x54, 0x54, 0x3C, // 0x67 g
    0x7F, 0x08, 0x04, 0x04, 0x78, // 0x68 h
    0x00, 0x44, 0x7D, 0x40, 0x00, // 0x69 i
    0x20, 0x40, 0x44, 0x3D, 0x00, // 0x6A j
    0x00, 0x7F, 0x10, 0x28, 0x44, // 0x6B k
    0x00, 0x41, 0x7F, 0x40, 0x00, // 0x6C l
    0x7C, 0x04, 0x18, 0x04, 0x78, // 0x6D m
    0x7C, 0x08, 0x04, 0x04, 0x78, // 0x6E n
    0x38, 0x44, 0x44, 0x44, 0x38, // 0x6F o
    0x7C, 0x14, 0x14, 0x14, 0x08, // 0x70 p
    0x08, 0x14, 0x14, 0x18, 0x7C, // 0x71 q
    0x7C, 0x08, 0x04, 0x04, 0x08, // 0x72 r
    0x48, 0x54, 0x54, 0x54, 0x20, // 0x73 s
    0x04, 0x3F, 0x44, 0x40, 0x20, // 0x74 t
    0x3C, 0x40, 0x40, 0x20, 0x7C, // 0x75 u
    0x1C, 0x20, 0x40, 0x20, 0x1C, // 0x76 v
    0x3C, 0x40, 0x30, 0x40, 0x3C, // 0x77 w
    0x44, 0x28, 0x10, 0x28, 0x44, // 0x78 x
    0x0C, 0x50, 0x50, 0x50, 0x3C, // 0x79 y
    0x44, 0x64, 0x54, 0x4C, 0x44, // 0x7A z
    0x00, 0x08, 0x36, 0x41, 0x00, // 0x7B {
    0x00, 0x00, 0x7F, 0x00, 0x00, // 0x7C |
    0x00, 0x41, 0x36, 0x08, 0x00, // 0x7D }
    0x08, 0x08, 0x2A, 0x1C, 0x08  // 0x7E ~
};

#if defined(ESP32) || defined(ARDUINO)

static inline void writeCommand(uint8_t cmd) {
    digitalWrite(TFT_PIN_DC, LOW);
    SPI.beginTransaction(SPISettings(40000000, MSBFIRST, SPI_MODE0));
    SPI.transfer(cmd);
    SPI.endTransaction();
}

static inline void writeData(uint8_t data) {
    digitalWrite(TFT_PIN_DC, HIGH);
    SPI.beginTransaction(SPISettings(40000000, MSBFIRST, SPI_MODE0));
    SPI.transfer(data);
    SPI.endTransaction();
}

static inline void setAddrWindow(uint16_t x0, uint16_t y0, uint16_t x1, uint16_t y1) {
    writeCommand(0x2A); // CASET
    writeData(x0 >> 8);
    writeData(x0 & 0xFF);
    writeData(x1 >> 8);
    writeData(x1 & 0xFF);

    writeCommand(0x2B); // PASET
    writeData(y0 >> 8);
    writeData(y0 & 0xFF);
    writeData(y1 >> 8);
    writeData(y1 & 0xFF);

    writeCommand(0x2C); // RAMWR
}

#endif // ESP32 / ARDUINO

void ili9341_driver_hardware_reset(void) {
#if defined(ESP32) || defined(ARDUINO)
    pinMode(TFT_PIN_RESET, OUTPUT);
    digitalWrite(TFT_PIN_RESET, HIGH);
    delay(10);
    digitalWrite(TFT_PIN_RESET, LOW);   // Assert reset pulse
    delay(20);
    digitalWrite(TFT_PIN_RESET, HIGH);  // Release reset
    delay(150);                         // Wait for ILI9341 bootloader
#endif
    s_hardware_reset_performed = true;
}

bool ili9341_driver_init(void) {
    // 1. Perform Mandatory Hardware Reset Pulse on D8 (GPIO7)
    ili9341_driver_hardware_reset();

#if defined(ESP32) || defined(ARDUINO)
    // 2. Configure D/C Pin on D7 (GPIO44)
    // UART0 is avoided; Native USB CDC is used to prevent bus conflicts
    pinMode(TFT_PIN_DC, OUTPUT);
    digitalWrite(TFT_PIN_DC, HIGH);

    // 3. Configure Custom SPI Bus (SCK=9, MOSI=8, MISO=-1, CS=-1)
    // CS is hardwired to GND; passing -1 prevents driver SS assertion conflicts
    SPI.begin(TFT_PIN_SCK, TFT_PIN_MISO, TFT_PIN_MOSI, -1);

    // 4. Send ILI9341 Canonical Initialization Sequence
    writeCommand(0x01); // Software Reset
    delay(10);
    writeCommand(0x28); // Display OFF

    writeCommand(0xCF);
    writeData(0x00); writeData(0xC1); writeData(0x30);

    writeCommand(0xED);
    writeData(0x64); writeData(0x03); writeData(0x12); writeData(0x81);

    writeCommand(0xE8);
    writeData(0x85); writeData(0x00); writeData(0x78);

    writeCommand(0xCB);
    writeData(0x39); writeData(0x2C); writeData(0x00); writeData(0x34); writeData(0x02);

    writeCommand(0xF7);
    writeData(0x20);

    writeCommand(0xEA);
    writeData(0x00); writeData(0x00);

    writeCommand(0xC0); // Power Control 1
    writeData(0x23);

    writeCommand(0xC1); // Power Control 2
    writeData(0x10);

    writeCommand(0xC5); // VCOM Control 1
    writeData(0x3E); writeData(0x28);

    writeCommand(0xC7); // VCOM Control 2
    writeData(0x86);

    writeCommand(0x36); // MADCTL: Landscape 320x240 orientation
    writeData(0xE8);

    writeCommand(0x3A); // COLMOD: 16-bit RGB 565
    writeData(0x55);

    writeCommand(0xB1); // Frame Rate Control (70 Hz)
    writeData(0x00); writeData(0x1B);

    writeCommand(0xB6); // Display Function Control
    writeData(0x08); writeData(0x82); writeData(0x27);

    writeCommand(0x11); // Sleep Out
    delay(120);

    writeCommand(0x29); // Display ON
    delay(20);
#endif

    s_is_initialized = true;
    ili9341_fill_screen(ILI9341_BLACK);
    return true;
}

bool ili9341_driver_is_initialized(void) {
    return s_is_initialized;
}

bool ili9341_driver_is_reset_performed(void) {
    return s_hardware_reset_performed;
}

uint32_t ili9341_get_op_count(void) {
    return s_op_count;
}

void ili9341_reset_op_count(void) {
    s_op_count = 0;
}

void ili9341_draw_pixel(int16_t x, int16_t y, uint16_t color) {
    if (x < 0 || x >= ILI9341_TFTWIDTH || y < 0 || y >= ILI9341_TFTHEIGHT) {
        return;
    }
    s_op_count++;

#if defined(ESP32) || defined(ARDUINO)
    setAddrWindow(x, y, x, y);
    digitalWrite(TFT_PIN_DC, HIGH);
    SPI.beginTransaction(SPISettings(40000000, MSBFIRST, SPI_MODE0));
    SPI.transfer16(color);
    SPI.endTransaction();
#else
    (void)color;
#endif
}

void ili9341_draw_fast_h_line(int16_t x, int16_t y, int16_t w, uint16_t color) {
    if (y < 0 || y >= ILI9341_TFTHEIGHT || w <= 0) return;
    if (x < 0) { w += x; x = 0; }
    if (x + w > ILI9341_TFTWIDTH) { w = ILI9341_TFTWIDTH - x; }
    if (w <= 0) return;
    s_op_count++;

#if defined(ESP32) || defined(ARDUINO)
    setAddrWindow(x, y, x + w - 1, y);
    digitalWrite(TFT_PIN_DC, HIGH);
    SPI.beginTransaction(SPISettings(40000000, MSBFIRST, SPI_MODE0));
    for (int16_t i = 0; i < w; i++) {
        SPI.transfer16(color);
    }
    SPI.endTransaction();
#else
    (void)color;
#endif
}

void ili9341_draw_fast_v_line(int16_t x, int16_t y, int16_t h, uint16_t color) {
    if (x < 0 || x >= ILI9341_TFTWIDTH || h <= 0) return;
    if (y < 0) { h += y; y = 0; }
    if (y + h > ILI9341_TFTHEIGHT) { h = ILI9341_TFTHEIGHT - y; }
    if (h <= 0) return;
    s_op_count++;

#if defined(ESP32) || defined(ARDUINO)
    setAddrWindow(x, y, x, y + h - 1);
    digitalWrite(TFT_PIN_DC, HIGH);
    SPI.beginTransaction(SPISettings(40000000, MSBFIRST, SPI_MODE0));
    for (int16_t i = 0; i < h; i++) {
        SPI.transfer16(color);
    }
    SPI.endTransaction();
#else
    (void)color;
#endif
}

void ili9341_fill_rect(int16_t x, int16_t y, int16_t w, int16_t h, uint16_t color) {
    if (w <= 0 || h <= 0 || x >= ILI9341_TFTWIDTH || y >= ILI9341_TFTHEIGHT) return;
    if (x < 0) { w += x; x = 0; }
    if (y < 0) { h += y; y = 0; }
    if (x + w > ILI9341_TFTWIDTH) w = ILI9341_TFTWIDTH - x;
    if (y + h > ILI9341_TFTHEIGHT) h = ILI9341_TFTHEIGHT - y;
    if (w <= 0 || h <= 0) return;
    s_op_count++;

#if defined(ESP32) || defined(ARDUINO)
    setAddrWindow(x, y, x + w - 1, y + h - 1);
    digitalWrite(TFT_PIN_DC, HIGH);
    SPI.beginTransaction(SPISettings(40000000, MSBFIRST, SPI_MODE0));
    uint32_t total = (uint32_t)w * h;
    for (uint32_t i = 0; i < total; i++) {
        SPI.transfer16(color);
    }
    SPI.endTransaction();
#else
    (void)color;
#endif
}

void ili9341_fill_screen(uint16_t color) {
    ili9341_fill_rect(0, 0, ILI9341_TFTWIDTH, ILI9341_TFTHEIGHT, color);
}

void ili9341_draw_rect(int16_t x, int16_t y, int16_t w, int16_t h, uint16_t color) {
    if (w <= 0 || h <= 0) return;
    ili9341_draw_fast_h_line(x, y, w, color);
    ili9341_draw_fast_h_line(x, y + h - 1, w, color);
    ili9341_draw_fast_v_line(x, y, h, color);
    ili9341_draw_fast_v_line(x + w - 1, y, h, color);
}

void ili9341_draw_circle(int16_t x0, int16_t y0, int16_t r, uint16_t color) {
    int16_t f = 1 - r;
    int16_t ddF_x = 1;
    int16_t ddF_y = -2 * r;
    int16_t x = 0;
    int16_t y = r;

    ili9341_draw_pixel(x0, y0 + r, color);
    ili9341_draw_pixel(x0, y0 - r, color);
    ili9341_draw_pixel(x0 + r, y0, color);
    ili9341_draw_pixel(x0 - r, y0, color);

    while (x < y) {
        if (f >= 0) {
            y--;
            ddF_y += 2;
            f += ddF_y;
        }
        x++;
        ddF_x += 2;
        f += ddF_x;

        ili9341_draw_pixel(x0 + x, y0 + y, color);
        ili9341_draw_pixel(x0 - x, y0 + y, color);
        ili9341_draw_pixel(x0 + x, y0 - y, color);
        ili9341_draw_pixel(x0 - x, y0 - y, color);
        ili9341_draw_pixel(x0 + y, y0 + x, color);
        ili9341_draw_pixel(x0 - y, y0 + x, color);
        ili9341_draw_pixel(x0 + y, y0 - x, color);
        ili9341_draw_pixel(x0 - y, y0 - x, color);
    }
}

void ili9341_fill_circle(int16_t x0, int16_t y0, int16_t r, uint16_t color) {
    ili9341_draw_fast_v_line(x0, y0 - r, 2 * r + 1, color);
    int16_t f = 1 - r;
    int16_t ddF_x = 1;
    int16_t ddF_y = -2 * r;
    int16_t x = 0;
    int16_t y = r;

    while (x < y) {
        if (f >= 0) {
            y--;
            ddF_y += 2;
            f += ddF_y;
        }
        x++;
        ddF_x += 2;
        f += ddF_x;

        ili9341_draw_fast_v_line(x0 + x, y0 - y, 2 * y + 1, color);
        ili9341_draw_fast_v_line(x0 - x, y0 - y, 2 * y + 1, color);
        ili9341_draw_fast_v_line(x0 + y, y0 - x, 2 * x + 1, color);
        ili9341_draw_fast_v_line(x0 - y, y0 - x, 2 * x + 1, color);
    }
}

void ili9341_draw_round_rect(int16_t x, int16_t y, int16_t w, int16_t h, int16_t r, uint16_t color) {
    if (r <= 0) {
        ili9341_draw_rect(x, y, w, h, color);
        return;
    }
    ili9341_draw_fast_h_line(x + r, y, w - 2 * r, color);
    ili9341_draw_fast_h_line(x + r, y + h - 1, w - 2 * r, color);
    ili9341_draw_fast_v_line(x, y + r, h - 2 * r, color);
    ili9341_draw_fast_v_line(x + w - 1, y + r, h - 2 * r, color);

    // Quarter circles
    int16_t f = 1 - r;
    int16_t ddF_x = 1;
    int16_t ddF_y = -2 * r;
    int16_t px = 0;
    int16_t py = r;

    while (px < py) {
        if (f >= 0) {
            py--;
            ddF_y += 2;
            f += ddF_y;
        }
        px++;
        ddF_x += 2;
        f += ddF_x;

        ili9341_draw_pixel(x + w - r - 1 + px, y + r - py, color);
        ili9341_draw_pixel(x + r - px,         y + r - py, color);
        ili9341_draw_pixel(x + w - r - 1 + px, y + h - r - 1 + py, color);
        ili9341_draw_pixel(x + r - px,         y + h - r - 1 + py, color);

        ili9341_draw_pixel(x + w - r - 1 + py, y + r - px, color);
        ili9341_draw_pixel(x + r - py,         y + r - px, color);
        ili9341_draw_pixel(x + w - r - 1 + py, y + h - r - 1 + px, color);
        ili9341_draw_pixel(x + r - py,         y + h - r - 1 + px, color);
    }
}

void ili9341_fill_round_rect(int16_t x, int16_t y, int16_t w, int16_t h, int16_t r, uint16_t color) {
    if (r <= 0) {
        ili9341_fill_rect(x, y, w, h, color);
        return;
    }
    ili9341_fill_rect(x + r, y, w - 2 * r, h, color);

    // Fill corner sections
    int16_t f = 1 - r;
    int16_t ddF_x = 1;
    int16_t ddF_y = -2 * r;
    int16_t px = 0;
    int16_t py = r;

    while (px < py) {
        if (f >= 0) {
            py--;
            ddF_y += 2;
            f += ddF_y;
        }
        px++;
        ddF_x += 2;
        f += ddF_x;

        ili9341_draw_fast_v_line(x + r - px,         y + r - py,         h - 2 * r + 2 * py, color);
        ili9341_draw_fast_v_line(x + w - r - 1 + px, y + r - py,         h - 2 * r + 2 * py, color);
        ili9341_draw_fast_v_line(x + r - py,         y + r - px,         h - 2 * r + 2 * px, color);
        ili9341_draw_fast_v_line(x + w - r - 1 + py, y + r - px,         h - 2 * r + 2 * px, color);
    }
}

void ili9341_draw_line(int16_t x0, int16_t y0, int16_t x1, int16_t y1, uint16_t color) {
    int16_t steep = abs(y1 - y0) > abs(x1 - x0);
    if (steep) {
        int16_t tmp = x0; x0 = y0; y0 = tmp;
        tmp = x1; x1 = y1; y1 = tmp;
    }
    if (x0 > x1) {
        int16_t tmp = x0; x0 = x1; x1 = tmp;
        tmp = y0; y0 = y1; y1 = tmp;
    }
    int16_t dx = x1 - x0;
    int16_t dy = abs(y1 - y0);
    int16_t err = dx / 2;
    int16_t ystep = (y0 < y1) ? 1 : -1;

    for (; x0 <= x1; x0++) {
        if (steep) {
            ili9341_draw_pixel(y0, x0, color);
        } else {
            ili9341_draw_pixel(x0, y0, color);
        }
        err -= dy;
        if (err < 0) {
            y0 += ystep;
            err += dx;
        }
    }
}

void ili9341_draw_char(int16_t x, int16_t y, char c, uint16_t color, uint16_t bg, uint8_t size) {
    if (c < 0x20 || c > 0x7E) {
        c = '?';
    }
    uint16_t offset = (c - 0x20) * 5;

    for (int8_t i = 0; i < 5; i++) {
        uint8_t line = s_font5x7[offset + i];
        for (int8_t j = 0; j < 8; j++, line >>= 1) {
            if (line & 1) {
                if (size == 1) {
                    ili9341_draw_pixel(x + i, y + j, color);
                } else {
                    ili9341_fill_rect(x + i * size, y + j * size, size, size, color);
                }
            } else if (bg != color) {
                if (size == 1) {
                    ili9341_draw_pixel(x + i, y + j, bg);
                } else {
                    ili9341_fill_rect(x + i * size, y + j * size, size, size, bg);
                }
            }
        }
    }
    // Trailing 1-pixel gap between characters
    if (bg != color) {
        if (size == 1) {
            ili9341_draw_fast_v_line(x + 5, y, 8, bg);
        } else {
            ili9341_fill_rect(x + 5 * size, y, size, 8 * size, bg);
        }
    }
}

void ili9341_draw_string(int16_t x, int16_t y, const char* str, uint16_t color, uint16_t bg, uint8_t size) {
    if (!str) return;
    int16_t cur_x = x;
    int16_t cur_y = y;
    while (*str) {
        if (*str == '\n') {
            cur_x = x;
            cur_y += 8 * size + 2;
        } else {
            ili9341_draw_char(cur_x, cur_y, *str, color, bg, size);
            cur_x += 6 * size;
        }
        str++;
    }
}

