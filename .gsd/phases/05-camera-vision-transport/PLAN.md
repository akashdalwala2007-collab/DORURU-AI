---
phase: 5
plan: 1
wave: 1
gap_closure: false
---

# Plan 5.1: OV3660 Camera Capture and Vision Transport

## Objective
Implement OV3660 camera capture and a safe image-transfer interface for DORURU on the Seeed Studio XIAO ESP32-S3 Sense without altering confirmed wiring or assuming extra hardware. Provide runtime 8MB Octal PSRAM verification, dynamic buffer sizing, hybrid vision modes (on-demand and selected events), strict framebuffer release, authenticated local HTTP transport, and TFT state coordination.

## Context
- `doruru_phase.txt` (Phase 5 Master Prompt and System Architecture)
- `firmware/include/board_pins.h` (Hardware Pin Map)
- `backend/app/config.py` (Local Backend Configuration)

## Tasks

<task type="auto" effort="high">
  <name>Configure Board Pins and Hardware Definitions</name>
  <files>firmware/include/board_pins.h</files>
  <action>
    Define dedicated XIAO ESP32-S3 Sense camera pin map (D0..D7, XCLK=10, PCLK=13, VSYNC=38, HREF=47, SIOD=40, SIOC=39).
    Reserve PDM Mic pins (GPIO41/42) and Speaker pins (GPIO5/6/43) without conflict.
    Define OV3660 chip PID (0x3660) and SCCB address (0x3C).
  </action>
  <verify>Check header syntax and pin uniqueness</verify>
  <done>Clean pinout header with all peripherals documented and no overlapping GPIOs</done>
</task>

<task type="auto" effort="high">
  <name>Implement OV3660 Camera Driver Wrapper and Buffer Lifecycle</name>
  <files>firmware/src/camera/camera_manager.h, firmware/src/camera/camera_manager.cpp</files>
  <action>
    Verify 8MB Octal PSRAM availability at runtime using psramFound().
    Size framebuffers dynamically: VGA 640x480 / Q12 if PSRAM present; QVGA 320x240 / Q20 DRAM fallback.
    Probe and verify OV3660 sensor PID (0x3660).
    Implement hybrid capture: on-demand single shot, controlled burst (max 3), and event trigger.
    Strictly release frame buffers via esp_camera_fb_return.
  </action>
  <verify>Host mock and test compilation</verify>
  <done>Zero memory leaks, verified PID checking, and burst limit enforced</done>
</task>

<task type="auto" effort="medium">
  <name>Implement Authenticated Vision Transport and TFT Coordination</name>
  <files>firmware/src/transport/vision_transport.h, firmware/src/transport/vision_transport.cpp, firmware/src/display/display_interface.h, firmware/src/display/display_interface.cpp</files>
  <action>
    Build authenticated HTTP client sending X-Device-ID and X-Device-Token.
    Handle Wi-Fi loss gracefully with fail-fast check and TFT notification.
    Implement display state transitions (CAPTURE -> PROCESSING -> SUCCESS / ERROR).
    Stream frames directly without permanent storage.
  </action>
  <verify>Mock transport test execution</verify>
  <done>Authenticated transport and TFT states verified</done>
</task>

<task type="auto" effort="medium">
  <name>Create Local Backend Endpoint and Comprehensive Test Suite</name>
  <files>backend/app/main.py, backend/app/config.py, tests/test_vision_transport.py, tests/test_e2e_simulation.py</files>
  <action>
    Implement POST /api/v1/vision/upload with token auth, JPEG header verification, payload bounds, and ephemeral handling.
    Write unit tests for auth rejection, corrupt payloads, burst bounds, and memory lifecycle.
  </action>
  <verify>python -m unittest discover -s tests -v</verify>
  <done>100% test pass rate across all transport, auth, and error tests</done>
</task>

