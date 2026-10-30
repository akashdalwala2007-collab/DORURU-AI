---
status: FINALIZED
created: 2026-10-30T10:40:00+05:30
finalized: 2026-10-30T15:30:00+05:30
---

# SPEC.md — DORURU-AI Project Specification

## Vision

DORURU is an interactive, voice-first AI educational and laboratory assistant robot built for a college robotics environment. Operating on a hybrid tri-tier edge architecture, DORURU combines real-time embedded hardware control on a Seeed XIAO ESP32-S3 Sense, high-throughput local speech and orchestration processing on a local backend computer (FastAPI and Flask running on the user's development host), and cloud intelligence via the Google Gemini API for general conversation, college-specific RAG knowledge grounding, and on-demand computer vision. DORURU maintains privacy-first local audio capture, strict electrical and mechanical safety boundaries, and an engaging expressive persona rendered on a 2.8-inch SPI TFT display.

---

## Goals

1. **Privacy-First Voice Interaction Pipeline**:
   Provide responsive speech interaction without continuous cloud streaming: onboard PDM microphone (GPIO41/GPIO42 on I2S_NUM_0) captures speech -> local faster-whisper STT on backend -> Gemini orchestration / College RAG -> local Piper TTS -> streaming audio return to MAX98357A I2S amplifier (I2S_NUM_1).
2. **Deterministic Embedded Control & Safety**:
   Real-time execution on Seeed XIAO ESP32-S3 Sense managing motor actuation via MX1508, hardware fail-safes, automatic command timeouts (500ms max), and independent local emergency stop overriding all remote inputs.
3. **Institutional College Knowledge Grounding (RAG)**:
   Provide an evidence-grounded college knowledge retrieval system where institutional inquiries are strictly answered from user-verified college documents with clear source attribution, without hallucination.
4. **On-Demand Hybrid Vision**:
   Enable event-triggered and user-requested visual inspection using the onboard OV3660 camera and Gemini vision capabilities, avoiding continuous cloud video upload.
5. **Expressive Robot Persona**:
   Render dynamic system states, animations, and facial expressions on a 2.8" ILI9341 TFT display (240x320) using an optimized SPI interface without disrupting motor safety or audio streaming.

---

## Non-Goals (Out of Scope)

- **No "WALL-E" Naming or Branding**: The robot is named **DORURU**. WALL-E branding, names, sound bites, and assets are strictly forbidden.
- **No Continuous Cloud Streaming**: No always-on streaming of raw microphone audio or camera feeds to cloud providers. Microphone audio is processed locally or sent only upon active utterance detection.
- **No Unverified Autonomous Navigation**: Without wheel encoders and validated obstacle distance sensors, autonomous roaming, localization, user-following, and SLAM are explicitly out of scope. Movement is restricted to Level 1: bounded, timed, supervised motions.
- **No Persistent Personal Memory**: Session memory is transient and in-memory only. No long-term storage of user conversations, transcripts, or personal profiles by default.
- **No Motor Power from ESP32 Rails**: DC motors must never be powered from the ESP32 3.3V or 5V rails.
- **No Automatic Git Commits or Pushes**: All git versioning, staging, committing, and pushing must be initiated manually by the user.

---

## Users

- **Primary User**: College students, laboratory visitors, faculty, and guests interacting with DORURU through voice queries, demonstration commands, and campus Q&A.
- **Secondary User / Developer**: Robotics lab student engineers maintaining firmware, expanding skills, updating the college knowledge base, and supervising physical demonstrations.

---

## Constraints

### 1. Embedded Hardware & Fixed Pin Map (Preserve Exactly)
- **Microcontroller**: Seeed XIAO ESP32-S3 Sense (ESP32-S3 with 8MB Octal PSRAM / OPI).
- **Reserved Internal PDM Microphone**:
  - `PDM_DATA = GPIO41`, `PDM_CLK = GPIO42`.
  - Allocated exclusively to `I2S_NUM_0`. Never reassign.
- **Reserved Internal Camera Pins**:
  - Dedicated onboard camera bus for OV3660. Never reassign.
- **Display (2.8-inch ILI9341 SPI TFT, 240x320)**:
  - `VCC = 5V / VBUS` (requires breakout with 3.3V LDO & logic compatibility)
  - `GND = GND`
  - `CS = GND` (permanently grounded; software configured with `CS = -1`, hardware reset pulse on boot)
  - `RESET = D8 (GPIO7)`
  - `D/C = D7 (GPIO44)`
  - `MOSI / SDI = D9 (GPIO8)`
  - `SCK = D10 (GPIO9)`
  - `MISO = Not Connected (-1)`
  - `LED = 3V3`
- **Audio Output (MAX98357A I2S Amplifier + Speaker)**:
  - Allocated exclusively to `I2S_NUM_1`.
  - `DIN = D4 (GPIO5)`
  - `BCLK = D5 (GPIO6)`
  - `LRC = D6 (GPIO43)`
  - `GND = GND`
  - `VIN = 3V3`
- **Motor Driver (MX1508 H-Bridge)**:
  - `IN1 = D3 (GPIO4)`
  - `IN2 = D2 (GPIO3)`
  - `IN3 = D1 (GPIO2)`
  - `IN4 = D0 (GPIO1)`
- **Peripheral & Architecture Constraints**:
  - **UART0 Pin Conflict**: D6 (GPIO43, MAX98357A LRC) and D7 (GPIO44, ILI9341 D/C) overlap default UART0. UART0 serial logging is prohibited. Native USB CDC (`ARDUINO_USB_CDC_ON_BOOT=1`) must be used for debug logging.
  - **Custom SPI Bus**: XIAO default SPI pins do not match confirmed wiring; explicit software initialization of custom SPI (SCK=9, MOSI=8, MISO=-1) is mandatory.
  - **8MB Octal PSRAM (OPI)**: Required for camera framebuffers and audio buffers; runtime verification is mandatory.
  - **Unconfirmed Hardware**: Wheel encoders, obstacle sensors, and microSD are unconfirmed and marked disabled in software.

### 2. Hardware Power and Electrical Safety (UNRESOLVED Verification Items)
The following power and electrical parameters are documented as **UNRESOLVED**, requiring physical datasheet and multimeter verification before autonomous or high-load operation:
1. **Motor Rated Voltage & Stall Current**: Verification required as to whether installed motors match the 3V N20 16 RPM reference screenshot or differ, and measurement of no-load vs stall current.
2. **MX1508 Driver Ratings**: Operating voltage range (typically 2V–10V) and continuous/peak current limits (800mA continuous, 1.5A–2A peak per bridge) relative to motor stall current.
3. **Battery Chemistry & Ratings**: Battery chemistry (e.g. 1S LiPo 3.7V nominal, 2S 7.4V, or NiMH), nominal voltage, cutoff voltage, and continuous/peak C-rating discharge capability.
4. **Voltage Regulator & Distribution Topology**: Ratings, thermal headroom, and separation between digital logic rail (ESP32, sensors) and inductive motor rail.
5. **Common Ground**: Low-impedance common ground reference across battery, motor driver, ESP32, display, and audio amplifier to avoid ground bounce.
6. **Supply Stability & Brownout Mitigation**: ESP32 3.3V/5V rail stability during motor stall and direction reversal to prevent brownout detector resets.
7. **Rail Voltage Compatibility**: VCC on 5V/VBUS for ILI9341 display, 3.3V SPI signals, 3.3V LED backlight, and 3.3V MAX98357A VIN.

**Mandatory Electrical Rules:**
- Never power motors directly from the ESP32 3.3V pin.
- Do not invent battery ratings, regulator specs, or motor current values.
- Do not declare the power distribution system electrically safe until physical component datasheets and measurements are verified.
- Preserve existing physical wiring unless a demonstrated electrical flaw is approved by the user.
- Never substitute software assumptions for physical electrical verification.

---

## Phase Requirements Matrix

### Phase 3 & 12: Motor Safety & Movement Intent
- Dual-tier sequence validation with monotonic sequence IDs and TTL staleness checks.
- Autonomy Level 1 restriction (bounded duration [50, 2000]ms, bounded PWM [0, 255]).
- Immediate emergency stop priority locking all motion.

### Phase 5 & 11: Camera Capture & Hybrid Gemini Vision
- Preserved OV3660 as documented camera sensor with PID (0x3660) SCCB register verification.
- Runtime 8MB Octal PSRAM inspection and dynamic buffer sizing (VGA/Q12 with PSRAM, QVGA/Q20 DRAM fallback).
- Hybrid vision policy: on-demand (single or controlled burst $\le 3$) and selected events; strictly no continuous streaming.
- Immediate framebuffer return (`esp_camera_fb_return`) and ephemeral storage policy.
- Official Google GenAI SDK (`google.genai`) with configurable model from env; strict no-tracking disclaimer.

### Phase 9: College Knowledge Base (RAG)
- Verified college document ingestion (Markdown/PDF) with section-aware paragraph chunking.
- Local TF-IDF & BM25 retrieval with source attribution and discrepancy flagging.
- Strict anti-hallucination protocol: refuses to answer without verified evidence.

### Phase 13: Offline Fallback & Session Lifecycle
- Ephemeral in-memory multi-turn sessions with configurable TTL (default 900s) and automatic purge.
- Immediate motor halt on network loss; rejection of pre-disconnect commands upon reconnect.
- Deterministic exponential reconnect backoff with overflow clamping and in-flight cancellation.
- Strict disclaimers: no cloud reasoning, vision, or RAG claims while offline.

---

## Success Criteria

- [x] Phase 1: Repository audited, GSD 1.6.0 baseline established, complete architectural specifications and power safety protocols approved.
- [ ] Phase 2: Modular firmware foundation running on Seeed XIAO ESP32-S3 Sense with USB CDC, OPI PSRAM validation, custom SPI routing, and dual I2S peripheral coordination.
- [x] Phase 3: MX1508 motor control with deterministic timeout, emergency stop, and software ramp protection.
- [ ] Phase 4: Expressive TFT state machine and persona display on ILI9341.
- [x] Phase 5: OV3660 camera initialization and on-demand image transport.
- [ ] Phase 6: FastAPI backend with modular service contracts, device authentication, and schema validation.
- [ ] Phase 7: Local faster-whisper STT and Piper TTS integrated on the local machine with CPU fallback.
- [ ] Phase 8: Google Gemini API integration with environment-configured model selection and session-only memory.
- [x] Phase 9: Verified college document RAG pipeline with source attribution.
- [ ] Phase 10: Local wake-word state machine with push-to-talk development fallback.
- [x] Phase 11: Hybrid vision flow linking OV3660 to Gemini vision.
- [x] Phase 12: Bounded movement intent interpretation with Level 1 autonomy lock.
- [x] Phase 13: Offline fallback, network loss recovery, and clean session lifecycle.
- [ ] Phase 14: Full end-to-end system integration and manual validation.
- [ ] Phase 15: GSD security, code quality, and release audit.

---

*Last updated: 2026-10-30*
