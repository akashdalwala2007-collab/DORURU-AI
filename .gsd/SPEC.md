# DORURU-AI Specification

Status: FINALIZED
Updated: 2026-10-30

## 1. System Identity
- **Robot Name**: DORURU (strictly DORURU, never WALL-E)
- **Controller**: Seeed Studio XIAO ESP32-S3 Sense
- **Camera Sensor**: OV3660 (Product ID 0x3660) via dedicated internal FPC camera connector
- **Memory**: 8MB Octal PSRAM (OPI) + 512KB SRAM
- **Display**: 2.8-inch ILI9341 SPI TFT (240x320)
- **Audio Output**: MAX98357A I2S Class D Amplifier on I2S_NUM_1
- **Microphone**: Onboard PDM Microphone on I2S_NUM_0 (GPIO41/GPIO42)
- **Motor Driver**: MX1508 Dual H-Bridge

## 2. Phase 5 Requirements (Camera Capture & Vision Transport)
1. **Camera Sensor & PSRAM**:
   - Preserve OV3660 as documented camera sensor.
   - Verify sensor PID (0x3660) via SCCB registers (0x300A/0x300B).
   - Inspect runtime 8MB Octal PSRAM (OPI) availability before buffer allocation.
   - Dynamic buffer sizing: 640x480 (VGA) / JPEG Q12 with PSRAM; 320x240 (QVGA) / JPEG Q20 DRAM fallback.
2. **Hybrid Vision Policy**:
   - On-demand: capture 1 frame or controlled burst (max 3 frames).
   - Selected events: capture only on explicitly defined event triggers.
   - Strictly no continuous image streaming or continuous cloud uploading.
3. **Buffer Management & Safety**:
   - Strict buffer release (`esp_camera_fb_return`) immediately after use.
   - Ephemeral image policy: No permanent image storage by default.
4. **Transport & Network**:
   - Authenticated local API (`X-Device-Token` / `X-Device-ID`).
   - Graceful Wi-Fi loss handling (fail-fast without crashing).
   - Server-side Gemini API credentials only (never stored on ESP32).
5. **UI / Persona**:
   - TFT notifications during capture and processing.
   - No person tracking or autonomous visual navigation without verified sensors.

