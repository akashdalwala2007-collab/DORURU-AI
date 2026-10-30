# DECISIONS.md — DORURU-AI Architecture Decision Records

> **Purpose**: Record all major architectural, embedded hardware, security, and AI system decisions for DORURU.

---

## [DECISION-001] Fixed Pin Mapping, Sense Internal Reservations, and UART0 Conflict Mitigation

**Date**: 2026-10-30  
**Status**: Accepted  

### Context
The robot controller is a Seeed XIAO ESP32-S3 Sense. The board features dense pin multiplexing and shared hardware buses. Furthermore, D6 (GPIO43) and D7 (GPIO44) are the ESP32-S3 default hardware UART0 TX/RX pins. In the confirmed user wiring, D6 is connected to the MAX98357A I2S LRC line, and D7 is connected to the ILI9341 display D/C line. Standard serial logging on UART0 would cause pin toggling that corrupts display commands and speaker audio. In addition, the physical ILI9341 CS pin is hardwired to GND.

### Decision
1. Strictly lock all pin assignments:
   - Microphone: Onboard Sense PDM Mic -> `GPIO41` (DATA), `GPIO42` (CLK) reserved exclusively on `I2S_NUM_0`.
   - Camera: Onboard OV3660 -> Reserved internal camera bus.
   - Display: ILI9341 -> `RESET=D8 (GPIO7)`, `D/C=D7 (GPIO44)`, `MOSI=D9 (GPIO8)`, `SCK=D10 (GPIO9)`, `CS=GND` (software `CS=-1`), `MISO=-1`, `VCC=5V`, `LED=3V3`.
   - Speaker: MAX98357A -> `DIN=D4 (GPIO5)`, `BCLK=D5 (GPIO6)`, `LRC=D6 (GPIO43)` reserved exclusively on `I2S_NUM_1`.
   - Motors: MX1508 -> `IN1=D3 (GPIO4)`, `IN2=D2 (GPIO3)`, `IN3=D1 (GPIO2)`, `IN4=D0 (GPIO1)`.
2. Prohibit hardware UART0 for debug logging. Configure native USB CDC (`ARDUINO_USB_CDC_ON_BOOT=1` and `ARDUINO_USB_MODE=1`).
3. Software display driver must explicitly initialize custom SPI pins (`SCK=9, MOSI=8, MISO=-1, CS=-1`) and execute a hardware reset pulse on D8 (GPIO7) at boot.

### Consequences
- Eliminates bus contention and signal corruption between logging, display, and audio.
- Prevents accidental pin reassignment that would conflict with onboard camera or microphone.

---

## [DECISION-002] Tri-Tier Edge-Server-Cloud System Architecture

**Date**: 2026-10-30  
**Status**: Accepted  

### Context
DORURU requires low-latency voice interaction, real-time motor control, high-quality speech synthesis, and intelligent reasoning. An ESP32-S3 alone cannot run large language models or modern speech synthesis locally, while relying 100% on cloud services introduces high latency, cost, privacy issues, and lack of offline safety.

### Decision
Implement a three-tier architecture:
- **Tier 1 (Edge - ESP32-S3)**: Real-time motor control, display rendering, microphone capture, camera frame acquisition, and hardware safety timeouts.
- **Tier 2 (Local Server - FastAPI on ASUS TUF A15)**: Local STT (faster-whisper), local TTS (Piper), RAG document search, intent validation, and request coordination.
- **Tier 3 (Cloud - Google Gemini API)**: High-level conversational reasoning, college knowledge grounding, and multimodal image inspection.

### Consequences
- Guarantees local safety and immediate emergency stop regardless of network status.
- Retains user voice privacy locally on LAN.
- Keeps cloud costs minimal and controlled.

---

## [DECISION-003] Local Speech Pipeline (faster-whisper & Piper) with CPU Fallback

**Date**: 2026-10-30  
**Status**: Accepted  

### Context
Voice interaction requires transcription of user speech and synthesis of natural robot responses. Managed cloud speech services incur per-request latency, financial costs, and privacy exposure. The host machine is an ASUS TUF A15 equipped with an NVIDIA GeForce RTX 3050 Laptop GPU (4GB VRAM) and multi-core CPU.

### Decision
1. Adopt `faster-whisper` for local Speech-to-Text (STT) and `Piper` for local Text-to-Speech (TTS).
2. STT and TTS models must support runtime device configuration (`cuda` with automatic `cpu int8` fallback).
3. Do not assume GPU acceleration works until driver and CUDA runtimes are verified in Phase 7.
4. Keep model paths and voice IDs environment-driven in `.env`.

### Consequences
- Fast turnaround time without cloud latency or subscription fees.
- Zero audio transmission to cloud.
- Robust portability from development laptop to future mini PC.

---

## [DECISION-004] Local Wake-Word Engine with Push-To-Talk Fallback

**Date**: 2026-10-30  
**Status**: Accepted  

### Context
Always-on cloud streaming of room audio violates user privacy. Local wake-word processing on the ESP32-S3 (such as ESP-SR / WakeNet) requires significant PSRAM and framework compatibility with the onboard PDM microphone.

### Decision
1. Evaluate ESP-SR local wake-word detection on `I2S_NUM_0` in Phase 10.
2. Maintain a mandatory, permanent Push-To-Talk (PTT) / Serial / Manual trigger fallback.
3. Microphone audio is buffered and streamed to backend ONLY after wake confirmation or manual trigger.

### Consequences
- Strictly enforces privacy.
- Development and demonstration are never blocked even if embedded wake-word library tuning requires iteration.

---

## [DECISION-005] Hybrid On-Demand Vision Architecture

**Date**: 2026-10-30  
**Status**: Accepted  

### Context
Continuous camera video streaming would overwhelm ESP32-S3 Wi-Fi bandwidth, deplete PSRAM, generate thermal buildup, and incur heavy Gemini API charges.

### Decision
Vision is strictly **on-demand**:
1. Single frame (or small bounded burst) is captured by OV3660 only when explicitly requested by user voice query or configured event.
2. Frame is transferred via HTTP multipart to local FastAPI, preprocessed, and sent to Gemini API with user prompt.
3. Buffers are released immediately. Continuous streaming is disabled by default.

### Consequences
- Minimal power consumption and network load.
- Predictable and controlled cloud API utilization.

---

## [DECISION-006] Grounded College Knowledge Base (RAG) with Source Attribution

**Date**: 2026-10-30  
**Status**: Accepted  

### Context
DORURU will serve as a college lab assistant. Large language models are prone to hallucinating facts such as campus dates, faculty names, department locations, or admission rules.

### Decision
1. Knowledge base is strictly populated from user-provided official documents (`knowledge_base/documents/`).
2. Implement semantic/lexical chunk retrieval; inject relevant context into Gemini prompt.
3. System prompt strictly constrains answers to retrieved evidence. If facts are absent or conflicting, DORURU states that records are unverified and cites the source metadata.

### Consequences
- Eliminates institutional hallucinations.
- Easy to update campus policies by simply updating markdown/PDF source files.

---

## [DECISION-007] Transient In-Memory Session Lifecycle

**Date**: 2026-10-30  
**Status**: Accepted  

### Context
Personal data privacy and simplicity are vital. Storing perpetual conversation histories on disk requires database overhead and creates privacy compliance burdens.

### Decision
1. All conversation history is maintained exclusively in volatile in-memory session structures.
2. Sessions expire after a configurable inactivity timeout (default 10 minutes) or upon manual reset.
3. No user conversation logs, voice recordings, or camera stills are persisted to disk by default.

### Consequences
- Zero database infrastructure required for baseline system.
- Privacy-safe by design.

---

## [DECISION-008] Bounded Movement Safety Architecture and Level-Based Autonomy Gating

**Date**: 2026-10-30  
**Status**: Accepted  

### Context
DORURU has two DC geared motors driven by an MX1508 H-bridge. Wheel encoders, distance sensors, and LiDAR are currently unconfirmed and not installed. Driving motors based on free-form LLM outputs or without hardware timeouts creates collision and thermal hazards.

### Decision
1. Structure autonomy into four discrete levels; lock DORURU strictly to **Level 1** (bounded timed motion) until hardware is physically installed and validated:
   - Level 1: Supervised open-loop timed motion (Active).
   - Level 2: Obstacle-aware navigation (Disabled).
   - Level 3: Odometry-based positioning (Disabled).
   - Level 4: Autonomous SLAM / person tracking (Disabled).
2. Free-form text from Gemini is never wired directly to motor pins. Intent parser translates commands into strict enums (`STOP`, `FORWARD`, `REVERSE`, `TURN_LEFT`, `TURN_RIGHT`).
3. Local ESP32 firmware independently validates duration (`<= 3.0s`), enforces automatic stop timeout, and provides an immediate local Emergency Stop override.

### Consequences
- Prevents runaway conditions or erratic movements.
- Clearly communicates hardware reality without false autonomy claims.

---

## [DECISION-009] Hardware Power and Electrical Safety Protocols

**Date**: 2026-10-30  
**Status**: Accepted  

### Context
DC motors draw high inductive stall currents and create electrical noise and back-EMF that can reset microcontrollers, damage LDO regulators, or overheat motor drivers.

### Decision
1. Formally document all power specifications (motor stall current, battery capacity/chemistry, regulator specs, brownout risk) as UNRESOLVED pending physical multimeter measurement.
2. Strictly forbid powering DC motors from the ESP32 3.3V pin.
3. Require common ground across battery, motor driver, ESP32, display, and audio amplifier.
4. Require physical datasheet verification and electrical decoupling before running full-load motor tests.

### Consequences
- Protects Seeed XIAO ESP32-S3 Sense from overcurrent and brownout damage.
- Enforces engineering discipline before mechanical stress tests.

---

*Last updated: 2026-10-30*

