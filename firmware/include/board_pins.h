#pragma once

#include <stdint.h>

/**
 * ============================================================================
 * DORURU-AI — Central Board Pin Configuration & Peripheral Allocation
 * Target: Seeed Studio XIAO ESP32-S3 Sense
 * ============================================================================
 * 
 * STRICT HARDWARE RULES:
 * 1. Confirmed wiring must be preserved exactly. Do not reassign or redesign.
 * 2. D6 (GPIO43) and D7 (GPIO44) are default UART0 pins; UART0 logging is
 *    strictly forbidden. Native USB CDC must be used for debug output.
 * 3. I2S_NUM_0 is dedicated to the onboard PDM microphone (GPIO41/42).
 * 4. I2S_NUM_1 is dedicated to the MAX98357A audio amplifier.
 * 5. Display CS is physically tied to GND; software uses CS = -1.
 * 6. DC Motors must NEVER be powered from ESP32 3.3V or 5V rails.
 * 7. OV3660 camera is attached to internal FPC DVP connector.
 */

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

#ifdef __cplusplus
namespace doruru {
namespace pins {

// MX1508 Dual DC Motor Driver Pins
constexpr int8_t MOTOR_IN1 = 4; // D3 / GPIO4 -> Motor A (Left) IN1
constexpr int8_t MOTOR_IN2 = 3; // D2 / GPIO3 -> Motor A (Left) IN2
constexpr int8_t MOTOR_IN3 = 2; // D1 / GPIO2 -> Motor B (Right) IN3
constexpr int8_t MOTOR_IN4 = 1; // D0 / GPIO1 -> Motor B (Right) IN4

// MAX98357A I2S Audio Amplifier Pins (Dedicated to I2S_NUM_1)
constexpr int8_t AUDIO_DIN  = 5;  // D4 / GPIO5  -> Serial Data
constexpr int8_t AUDIO_BCLK = 6;  // D5 / GPIO6  -> Bit Clock
constexpr int8_t AUDIO_LRC  = 43; // D6 / GPIO43 -> Left/Right Word Select

// 2.8" ILI9341 SPI TFT Display Pins (Custom SPI)
constexpr int8_t TFT_RESET = 7;  // D8 / GPIO7  -> Hardware Reset Pulse
constexpr int8_t TFT_DC    = 44; // D7 / GPIO44 -> Data / Command Select
constexpr int8_t TFT_MOSI  = 8;  // D9 / GPIO8  -> Custom SPI Data Out (SDI)
constexpr int8_t TFT_SCK   = 9;  // D10 / GPIO9 -> Custom SPI Clock (SCK)
constexpr int8_t TFT_CS    = -1; // Physically tied to GND; software CS = -1
constexpr int8_t TFT_MISO  = -1; // Not connected

// Reserved Internal XIAO ESP32-S3 Sense Pins (DO NOT REUSE)
constexpr int8_t MIC_PDM_DATA = 41; // GPIO41 -> PDM Data
constexpr int8_t MIC_PDM_CLK  = 42; // GPIO42 -> PDM Clock

// Dedicated Onboard OV3660 Camera Pins (Internal DVP bus)
constexpr int8_t CAM_XCLK  = 10;
constexpr int8_t CAM_PCLK  = 13; // GPIO13 (Sense Camera PCLK)
constexpr int8_t CAM_VSYNC = 38;
constexpr int8_t CAM_HREF  = 47;
constexpr int8_t CAM_SIOD  = 40; // I2C SDA
constexpr int8_t CAM_SIOC  = 39; // I2C SCL
constexpr int8_t CAM_D0    = 15;
constexpr int8_t CAM_D1    = 17;
constexpr int8_t CAM_D2    = 18;
constexpr int8_t CAM_D3    = 16;
constexpr int8_t CAM_D4    = 14;
constexpr int8_t CAM_D5    = 12; // GPIO12 (Sense Camera Y7/D5)
constexpr int8_t CAM_D6    = 11; // GPIO11 (Sense Camera Y8/D6)
constexpr int8_t CAM_D7    = 48; // GPIO48 (Sense Camera Y9/D7)
constexpr int8_t CAM_PWR   = -1;
constexpr int8_t CAM_RESET = -1;

// Unconfirmed Hardware Peripherals (Marked Unavailable)
constexpr int8_t ENCODER_LEFT_A   = -1; // Wheel encoders NOT installed
constexpr int8_t ENCODER_LEFT_B   = -1;
constexpr int8_t ENCODER_RIGHT_A  = -1;
constexpr int8_t ENCODER_RIGHT_B  = -1;
constexpr int8_t SENSOR_DISTANCE  = -1; // Distance sensor NOT installed
constexpr int8_t SDCARD_CS        = -1; // microSD NOT confirmed

} // namespace pins
} // namespace doruru
#endif
