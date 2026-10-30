---
milestone: DORURU-AI v1.0
version: 1.0.0
updated: 2026-10-30T10:42:00+05:30
---

# ROADMAP.md — DORURU-AI Phase-Wise Implementation Roadmap

> **Current Phase:** 1 - Repository Audit, GSD Baseline and Architecture Plan  
> **Status:** Verification & Approval Ready  

---

## Must-Haves (from SPEC.md)

- [ ] Tri-tier architecture operating synchronously: ESP32-S3 + Local FastAPI + Gemini Cloud
- [ ] Fixed pin map and hardware peripherals preserved exactly with zero pin conflicts
- [ ] UART0 conflict resolved via Native USB CDC serial logging
- [ ] 8MB Octal PSRAM (OPI) verified at boot for audio and camera buffers
- [ ] Safe local motor control with MX1508, hardware timeout, and emergency stop
- [ ] ILI9341 2.8" SPI display rendering expressive DORURU persona and system states
- [ ] Onboard PDM microphone (GPIO41/GPIO42) capturing audio on I2S_NUM_0
- [ ] MAX98357A I2S amplifier playing audio on I2S_NUM_1
- [ ] Local faster-whisper STT and Piper TTS running on host computer with CPU fallback
- [ ] Cloud Gemini API integration with environment-configured model selection (never hardcoded)
- [ ] College RAG knowledge retrieval answering exclusively from verified documents
- [ ] On-demand OV3660 camera capture linked to Gemini multimodal vision
- [ ] Level 1 bounded movement safety lock (no false autonomy claims)
- [ ] Offline fallback ensuring safe motor stop and disconnected UI indicator
- [ ] Zero secrets in tracked files, .env.example documented, automated git commits disabled

---

## Phases

### Phase 1: Repository Audit, GSD Baseline and Architecture Plan
- **Status:** 🔄 In Progress / Review Ready
- **Objective:** Inspect local repository, verify GSD 1.6.0 tools, reconcile architecture decisions, define fixed pin maps and hardware boundaries, document electrical safety and power protocols, and establish GSD planning baseline.
- **Dependencies:** None
- **Key Artifacts:** `.gsd/SPEC.md`, `.gsd/ARCHITECTURE.md`, `.gsd/DECISIONS.md`, `.gsd/ROADMAP.md`, `.gsd/STATE.md`, `.gsd/STACK.md`, `.gitignore`, `.env.example`.

---

### Phase 2: Firmware Foundation and Hardware Abstraction
- **Status:** ⬜ Not Started (Awaiting User Phase 1 Approval)
- **Objective:** Modular ESP32 firmware on Seeed XIAO ESP32-S3 Sense: central pin map, native USB CDC logging, OPI PSRAM validation, custom SPI routing (`SCK=9, MOSI=8, MISO=-1, CS=-1`), dual I2S peripheral coordination (`I2S_NUM_0` PDM RX, `I2S_NUM_1` MAX98357A TX), and safe boot diagnostics.
- **Depends on:** Phase 1

---

### Phase 3: Motor Control and Local Safety Foundation
- **Status:** ✅ Complete
- **Objective:** MX1508 motor driver control (`IN1=D3, IN2=D2, IN3=D1, IN4=D0`), software ramps, maximum duration limits, automatic watchdog stop timeout, and immediate local emergency stop override.
- **Depends on:** Phase 2
- **Key Artifacts:** `firmware/include/board_pins.h`, `firmware/include/motor_controller.h`, `firmware/src/motor_controller.cpp`, `firmware/src/main.cpp`, `firmware/tests/test_motor_controller.cpp`. Verified with 10/10 unit tests passing.

---

### Phase 4: Display States, Expressions and Robot Persona
- **Status:** ⬜ Not Started
- **Objective:** ILI9341 SPI TFT state rendering with custom SPI and hardware reset pulse on D8 (GPIO7), displaying booting, idle, listening, thinking, speaking, vision, movement, offline, and error screens for DORURU persona.
- **Depends on:** Phase 2

---

### Phase 5: Camera Capture and Vision Transport
- **Status:** ⬜ Not Started
- **Objective:** OV3660 DVP camera driver initialization, PSRAM framebuffer allocation, JPEG frame capture, buffer lifecycle management, and HTTP multipart transport to local backend.
- **Depends on:** Phase 2

---

### Phase 6: FastAPI Backend Foundation and Device API
- **Status:** ⬜ Not Started
- **Objective:** Python FastAPI backend on host machine with Pydantic request/response schemas, device authentication, audio/image upload endpoints, movement intent contracts, and in-memory session manager.
- **Depends on:** Phase 2

---

### Phase 7: Local Speech: faster-whisper STT and Piper TTS
- **Status:** ⬜ Not Started
- **Objective:** Local STT using faster-whisper and local TTS using Piper on the ASUS TUF A15 host with runtime CPU/CUDA detection and int8 fallback; audio format conversion for ESP32 I2S_NUM_1 playback.
- **Depends on:** Phase 6

---

### Phase 8: Gemini AI Orchestration and Session-Only Conversation
- **Status:** ⬜ Not Started
- **Objective:** Google Gemini API integration using environment-configured model name (`GEMINI_MODEL_NAME`), DORURU system persona prompt, transient in-memory conversation context, and rate-limit handling.
- **Depends on:** Phase 6

---

### Phase 9: College Knowledge Base and RAG
- **Status:** ⬜ Not Started
- **Objective:** Verified college document ingestion (Markdown/PDF), semantic/lexical chunking, retrieval service, and prompt grounding instructing Gemini to answer institutional facts exclusively from retrieved sources.
- **Depends on:** Phase 6, Phase 8

---

### Phase 10: Local Wake-Word and Voice Interaction State Machine
- **Status:** ⬜ Not Started
- **Objective:** Local wake-word evaluation on ESP32-S3 (`I2S_NUM_0` PDM) with mandatory push-to-talk/manual trigger fallback, voice activity detection, and state transitions (idle -> listening -> thinking -> speaking).
- **Depends on:** Phase 2, Phase 6, Phase 7, Phase 8

---

### Phase 11: Hybrid Vision with Gemini
- **Status:** ⬜ Not Started
- **Objective:** End-to-end event-triggered and user-requested vision flow: OV3660 capture -> FastAPI staging -> Gemini multimodal interpretation -> spoken response.
- **Depends on:** Phase 5, Phase 6, Phase 8

---

### Phase 12: Movement Command Interpretation and Autonomy Readiness
- **Status:** ✅ Complete
- **Objective:** Safe natural-language movement intent parsing, bounded command schemas, dual-tier independent validation (FastAPI + ESP32), and strict Level 1 autonomy enforcement with safe disabled states for missing sensors.
- **Depends on:** Phase 3, Phase 6, Phase 8
- **Key Artifacts:** `backend/app/schemas/movement.py`, `backend/app/services/movement_intent_parser.py`, `backend/app/routers/movement.py`, `firmware/include/command_validator.h`, `firmware/src/command_validator.cpp`. Verified with 24/24 pytest and 8/8 native C++ tests.

---

### Phase 13: Offline Fallback, Session Lifecycle and Recovery
- **Status:** ⬜ Not Started
- **Objective:** Network loss detection, automatic motor cutoff, offline display indicators, exponential backoff reconnection, stale command purging, and clean session cleanup.
- **Depends on:** Phases 2, 3, 4, 6, 7, 8, 10, 12

---

### Phase 14: Full System Integration and User Experience
- **Status:** ⬜ Not Started
- **Objective:** Comprehensive integration testing across all 13 prior modules, validating end-to-end voice, vision, movement, and recovery scenarios with manual bench checklists.
- **Depends on:** Phases 2–13

---

### Phase 15: GSD Final Review, Security, Quality and Release Readiness
- **Status:** ⬜ Not Started
- **Objective:** Independent engineering audit using installed GSD workflows, verifying pin maps, OPI PSRAM, electrical safety adherence, API key protection, test suites, and final delivery documentation.
- **Depends on:** Phase 14

---

*Last updated: 2026-10-30*

