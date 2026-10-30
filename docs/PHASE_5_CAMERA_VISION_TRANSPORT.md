# DORURU — Phase 5: Camera Capture & Vision Transport Documentation

## 1. Executive Summary
Phase 5 implements camera capture and safe image transport for **DORURU** using the **Seeed Studio XIAO ESP32-S3 Sense** and its dedicated **OV3660** camera module.

Key engineering accomplishments:
1. **Preserved OV3660 Identity**: Preserved OV3660 as the documented sensor, configuring the `esp_camera` driver specifically for OV3660 registers and probing its hardware Product ID (`0x3660`).
2. **8MB Octal PSRAM Runtime Validation**: Dynamically sizes framebuffers based on measured free PSRAM and heap, providing a safe DRAM fallback to prevent crashes if PSRAM is unconfigured or exhausted.
3. **Hybrid Vision Policy**: Implements on-demand single shot, controlled bursts (clamped to max 3 frames), and event capture. Strictly prohibits continuous background streaming or unprompted cloud uploading.
4. **Strict Frame Buffer Lifecycle**: Ensures zero memory leaks by returning framebuffers immediately via `esp_camera_fb_return` following transmission.
5. **Authenticated Local API Transport**: Streams JPEG frames over HTTP POST to the local backend using `X-Device-Token` authentication with ephemeral handling (no permanent file storage by default).
6. **Graceful Offline Recovery & TFT Feedback**: Detects Wi-Fi drops immediately, aborting cleanly without freezing the microcontroller, and updates the ILI9341 display state.
7. **Zero Cloud Secrets on Microcontroller**: All Gemini API keys remain strictly on the backend server.

---

## 2. Hardware Pinout & Wiring Audit

### XIAO ESP32-S3 Sense Camera Pinout
The camera connector on the Sense expansion board connects to the ESP32-S3 via the following dedicated pins:

| Signal Name | ESP32-S3 Pin | Function | Conflict Check |
|-------------|--------------|----------|----------------|
| **XCLK** | GPIO 10 | Master Clock (20 MHz) | Dedicated, no conflict |
| **SIOD** | GPIO 40 | SCCB Data (I2C SDA) | Dedicated, no conflict |
| **SIOC** | GPIO 39 | SCCB Clock (I2C SCL) | Dedicated, no conflict |
| **Y9 (D7)** | GPIO 48 | Camera Data Bit 7 | Dedicated, no conflict |
| **Y8 (D6)** | GPIO 11 | Camera Data Bit 6 | Dedicated, no conflict |
| **Y7 (D5)** | GPIO 12 | Camera Data Bit 5 | Dedicated, no conflict |
| **Y6 (D4)** | GPIO 14 | Camera Data Bit 4 | Dedicated, no conflict |
| **Y5 (D3)** | GPIO 16 | Camera Data Bit 3 | Dedicated, no conflict |
| **Y4 (D2)** | GPIO 18 | Camera Data Bit 2 | Dedicated, no conflict |
| **Y3 (D1)** | GPIO 17 | Camera Data Bit 1 | Dedicated, no conflict |
| **Y2 (D0)** | GPIO 15 | Camera Data Bit 0 | Dedicated, no conflict |
| **VSYNC** | GPIO 38 | Vertical Sync | Dedicated, no conflict |
| **HREF** | GPIO 47 | Horizontal Reference | Dedicated, no conflict |
| **PCLK** | GPIO 13 | Pixel Clock | Dedicated, no conflict |
| **PWDN** | -1 | Power Down | Unused (internally tied) |
| **RESET** | -1 | Hardware Reset | Unused (SCCB reset) |

### Peripheral Non-Interference Verification
- **PDM Microphone (strictly reserved)**: GPIO 41 (Data), GPIO 42 (Clock) on `I2S_NUM_0`. No overlap with camera pins.
- **Audio Output (MAX98357A)**: GPIO 5 (DIN), GPIO 6 (BCLK), GPIO 43 (LRC) on `I2S_NUM_1`. No overlap with camera pins.
- **ILI9341 Display (Custom SPI)**: GPIO 9 (SCK), GPIO 8 (MOSI), GPIO 7 (RESET), GPIO 44 (D/C), CS=-1 (CS hardwired to GND). No overlap with camera pins.
- **MX1508 Motors**: GPIO 4 (IN1), GPIO 3 (IN2), GPIO 2 (IN3), GPIO 1 (IN4). No overlap with camera pins.

---

## 3. OV3660 Sensor Probing & Configuration

### Sensor PID Inspection
The OmniVision OV3660 exposes a 16-bit Product ID via SCCB registers:
- High byte: Register `0x300A`
- Low byte: Register `0x300B`
- Expected PID: `0x3660`

During `camera_manager_init()`, the firmware queries `esp_camera_sensor_get()`:
```cpp
sensor_t *s = esp_camera_sensor_get();
if (s->id.PID == OV3660_CHIP_PID) { // 0x3660
    s_telemetry.is_ov3660_verified = true;
    s->set_vflip(s, 1);       // Adjust for physical XIAO mounting orientation
    s->set_hmirror(s, 0);
    s->set_brightness(s, 1);
    s->set_saturation(s, 0);
} else {
    // Flag warning: PID mismatch. Never silently disguise another sensor as OV3660.
}
```

---

## 4. PSRAM Verification & Dynamic Sizing Strategy

The Seeed Studio XIAO ESP32-S3 Sense features **8MB Octal (OPI) PSRAM**.
The firmware validates PSRAM presence at runtime before allocating high-resolution framebuffers:

```
[Boot] psramFound() ?
   │
   ├─► YES (Free PSRAM >= 1MB):
   │     • Buffer Location: CAMERA_FB_IN_PSRAM
   │     • Frame Size: FRAMESIZE_VGA (640x480)
   │     • JPEG Quality: 12 (Crisp high-definition capture)
   │     • fb_count: 1 (Avoids stale buffer latency on on-demand capture)
   │
   ├─► NO / Constrained (Free Heap >= 64KB):
   │     • Buffer Location: CAMERA_FB_IN_DRAM
   │     • Frame Size: FRAMESIZE_QVGA (320x240)
   │     • JPEG Quality: 20
   │     • fb_count: 1
   │
   └─► CRITICAL (Free Heap < 64KB):
         • Abort initialization with CAMERA_ERR_NO_PSRAM_HEAP
         • Update TFT Display: "CAM ERR: NO MEM"
```

---

## 5. Vision Transport & Authenticated Local API

### Endpoint Specification
- **Method**: `POST`
- **Path**: `/api/v1/vision/upload`
- **Headers**:
  - `Content-Type: image/jpeg`
  - `X-Device-ID: DORURU-SENSE-01`
  - `X-Device-Token: <local_secret_token>`
  - `X-Trigger-Reason: 0` (0 = On-demand, 2 = Event)
  - `X-Context-Prompt: <optional_user_question>`
- **Body**: Raw binary JPEG byte stream (`\xFF\xD8 ... \xFF\xD9`).

### Response Contract
```json
{
  "status": "success",
  "device_id": "DORURU-SENSE-01",
  "bytes_received": 32768,
  "trigger_reason": "on_demand",
  "timestamp": 1793345890.12,
  "ephemeral": true,
  "vision_result": {
    "processed": true,
    "summary": "Image received and verified (32768 bytes JPEG). Ready for Gemini processing.",
    "prompt": "What is in front of the robot?"
  }
}
```

---

## 6. TFT Display State Coordination

The camera and transport modules coordinate with DORURU's display state machine:
1. **Trigger Initiated**: Display switches to `DISPLAY_STATE_CAMERA_CAPTURE` ("Looking...").
2. **Transferring to Backend**: Display transitions to `DISPLAY_STATE_VISION_PROCESSING` ("Sending image...").
3. **Analysis Complete**: Display signals `DISPLAY_STATE_VISION_SUCCESS` ("Vision Analyzed").
4. **Network Dropped**: Display signals `DISPLAY_STATE_WIFI_DISCONNECTED` ("Wi-Fi Disconnected").
5. **Hardware/Memory Error**: Display signals `DISPLAY_STATE_ERROR` ("CAM ERR: ...").

---

## 7. Test Evidence

### Automated Unit & E2E Test Suite Execution
Tests executed using Python `unittest`:

```powershell
python -m unittest tests/test_vision_transport.py tests/test_e2e_simulation.py -v
```

**Results:**
```
test_authenticated_upload_success ... ok
test_bounded_burst_control ... ok
test_corrupt_non_jpeg_payload_rejected ... ok
test_ephemeral_storage_policy ... ok
test_framebuffer_lifecycle_simulation ... ok
test_health_endpoint ... ok
test_invalid_auth_token_rejected ... ok
test_missing_auth_token_rejected ... ok
test_network_loss_graceful_recovery ... ok
test_oversized_payload_rejected ... ok
test_e2e_camera_flow_and_display_states ... ok
test_e2e_network_loss_graceful_recovery ... ok

----------------------------------------------------------------------
Ran 12 tests in 0.649s

OK
```

### Real Camera Hardware Test Procedure
When flashing to physical hardware:
1. Connect XIAO ESP32-S3 Sense via USB-C.
2. Open Serial Monitor at 115200 baud.
3. Observe boot log:
   - Check `Free PSRAM: 8388608 bytes (8 MB)`
   - Check `Sensor PID: 0x3660 (OV3660 Verified)`
4. Type `c` in Serial Monitor:
   - Check TFT displays "Looking..."
   - Check frame captured with valid SOI marker `0xFFD8`
   - Check HTTP POST to backend returns status 200
   - Check TFT updates to "Vision Analyzed"
   - Check framebuffer is freed immediately.

