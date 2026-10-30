/**
 * @file board_pins.h
 * @brief Central Hardware Pin Configuration for DORURU
 * @details Target: Seeed Studio XIAO ESP32-S3 Sense
 *
 * CONFIRMED HARDWARE PIN MAP - DO NOT ALTER EXISTING WIRING:
 * - Camera: Dedicated internal XIAO ESP32-S3 Sense FPC camera connector (OV3660)
 * - Display: 2.8-inch ILI9341 SPI TFT (SCK=D10/GPIO9, MOSI=D9/GPIO8, D/C=D7/GPIO44, RESET=D8/GPIO7, CS=GND/-1)
 * - Speaker: MAX98357A I2S Amplifier on I2S_NUM_1 (DIN=D4/GPIO5, BCLK=D5/GPIO6, LRC=D6/GPIO43)
 * - Microphone: Onboard PDM Microphone on I2S_NUM_0 (PDM_DATA=GPIO41, PDM_CLK=GPIO42)
 * - Motors: MX1508 Dual H-Bridge (IN1=D3/GPIO4, IN2=D2/GPIO3, IN3=D1/GPIO2, IN4=D0/GPIO1)
 */

#pragma once

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ========================================================================== */
/* XIAO ESP32-S3 SENSE D-PIN TO GPIO ALIASES                                 */
/* ========================================================================== */
#define PIN_D0                  1   // GPIO1
#define PIN_D1                  2   // GPIO2
#define PIN_D2                  3   // GPIO3
#define PIN_D3                  4   // GPIO4
#define PIN_D4                  5   // GPIO5
#define PIN_D5                  6   // GPIO6
#define PIN_D6                  43  // GPIO43 (UART0 TX default - avoid UART logging!)
#define PIN_D7                  44  // GPIO44 (UART0 RX default - avoid UART logging!)
#define PIN_D8                  7   // GPIO7
#define PIN_D9                  8   // GPIO8
#define PIN_D10                 9   // GPIO9

/* ========================================================================== */
/* DEDICATED ONBOARD CAMERA PINS (SEEED XIAO ESP32-S3 SENSE / OV3660)        */
/* ========================================================================== */
#define CAMERA_PIN_PWDN         -1  // Power down not broken out
#define CAMERA_PIN_RESET        -1  // Software reset via SCCB
#define CAMERA_PIN_XCLK         10  // Master Clock (XCLK)
#define CAMERA_PIN_SIOD         40  // SCCB Data (SDA)
#define CAMERA_PIN_SIOC         39  // SCCB Clock (SCL)

#define CAMERA_PIN_D7           48  // Y9 (Data bit 7)
#define CAMERA_PIN_D6           11  // Y8 (Data bit 6)
#define CAMERA_PIN_D5           12  // Y7 (Data bit 5)
#define CAMERA_PIN_D4           14  // Y6 (Data bit 4)
#define CAMERA_PIN_D3           16  // Y5 (Data bit 3)
#define CAMERA_PIN_D2           18  // Y4 (Data bit 2)
#define CAMERA_PIN_D1           17  // Y3 (Data bit 1)
#define CAMERA_PIN_D0           15  // Y2 (Data bit 0)

#define CAMERA_PIN_VSYNC        38  // Vertical Sync
#define CAMERA_PIN_HREF         47  // Horizontal Reference
#define CAMERA_PIN_PCLK         13  // Pixel Clock
#define CAMERA_PIN_LED          21  // Optional onboard LED indicator

/* OV3660 Expected Sensor Hardware PID */
#define OV3660_CHIP_PID         0x3660
#define OV3660_SCCB_ADDR        0x3C

/* ========================================================================== */
/* RESERVED ONBOARD PDM MICROPHONE PINS (I2S_NUM_0)                           */
/* ========================================================================== */
#define PDM_MIC_PIN_DATA        41  // GPIO41 - Strictly reserved for PDM RX
#define PDM_MIC_PIN_CLK         42  // GPIO42 - Strictly reserved for PDM CLK

/* ========================================================================== */
/* AUDIO SPEAKER OUTPUT PINS (MAX98357A on I2S_NUM_1)                        */
/* ========================================================================== */
#define I2S_SPK_PIN_DIN         PIN_D4  // GPIO5 (DIN)
#define I2S_SPK_PIN_BCLK        PIN_D5  // GPIO6 (BCLK)
#define I2S_SPK_PIN_LRC         PIN_D6  // GPIO43 (LRC)

/* ========================================================================== */
/* ILI9341 SPI DISPLAY PINS (CUSTOM SPI BUS)                                 */
/* ========================================================================== */
#define TFT_PIN_SCK             PIN_D10 // GPIO9
#define TFT_PIN_MOSI            PIN_D9  // GPIO8
#define TFT_PIN_MISO            -1      // Not connected
#define TFT_PIN_CS              -1      // Hardwired to GND (permanently selected)
#define TFT_PIN_DC              PIN_D7  // GPIO44 (Data / Command)
#define TFT_PIN_RESET           PIN_D8  // GPIO7 (Hardware reset pulse)

/* ========================================================================== */
/* MX1508 DUAL MOTOR CONTROLLER PINS                                          */
/* ========================================================================== */
#define MOTOR_PIN_IN1           PIN_D3  // GPIO4
#define MOTOR_PIN_IN2           PIN_D2  // GPIO3
#define MOTOR_PIN_IN3           PIN_D1  // GPIO2
#define MOTOR_PIN_IN4           PIN_D0  // GPIO1

#ifdef __cplusplus
}
#endif

