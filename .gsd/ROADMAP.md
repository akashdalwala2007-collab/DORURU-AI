---
milestone: DORURU-AI v1.0
version: 1.0.0
updated: 2026-10-30T15:30:00+05:30
---

# ROADMAP.md — DORURU-AI Phase-Wise Implementation Roadmap

> **Current Milestone:** DORURU-AI v1.0 — Unified Integration  
> **Status:** Multi-Phase Verified (Phases 3, 5, 9, 11, 12, 13 Complete)  

---

## Must-Haves (from SPEC.md)

- [ ] Tri-tier architecture operating synchronously: ESP32-S3 + Local FastAPI/Flask Backend + Gemini Cloud
- [x] Fixed pin map and hardware peripherals preserved exactly with zero pin conflicts
- [x] UART0 conflict resolved via Native USB CDC serial logging
- [x] 8MB Octal PSRAM (OPI) verified at boot for audio and camera buffers
- [x] Safe local motor control with MX1508, hardware timeout, and emergency stop (Phase 3 & Phase 13)
- [ ] ILI9341 2.8" SPI display rendering expressive DORURU persona and system states
- [ ] Onboard PDM microphone (GPIO41/GPIO42) capturing audio on I2S_NUM_0
- [ ] MAX98357A I2S amplifier playing audio on I2S_NUM_1
- [ ] Local faster-whisper STT and Piper TTS running on host computer with CPU fallback
- [x] Cloud Gemini API integration with environment-configured model selection (never hardcoded) (Phase 11)
- [x] College RAG knowledge retrieval answering exclusively from verified documents (Phase 9)
- [x] On-demand OV3660 camera capture linked to Gemini multimodal vision (Phase 5 & Phase 11)
- [x] Level 1 bounded movement safety lock (no false autonomy claims) (Phase 12)
- [x] Offline fallback ensuring safe motor stop and disconnected UI indicator (Phase 13)
- [x] Zero secrets in tracked files, .env.example documented, automated git commits disabled

---

## Phase Status Summary

- [ ] **Phase 1**: Repository Audit, GSD Baseline and Architecture Plan
- [ ] **Phase 2**: Firmware Foundation and Hardware Abstraction
- [x] **Phase 3**: Motor Control and Local Safety Foundation
- [ ] **Phase 4**: Display States, Expressions and Robot Persona
- [x] **Phase 5**: Camera Capture and Vision Transport
- [ ] **Phase 6**: FastAPI Backend Foundation and Device API
- [ ] **Phase 7**: Local Speech: faster-whisper STT and Piper TTS
- [ ] **Phase 8**: Gemini AI Orchestration and Session-Only Conversation
- [x] **Phase 9**: College Knowledge Base and RAG
- [ ] **Phase 10**: Local Wake-Word and Voice Interaction State Machine
- [x] **Phase 11**: Hybrid Vision with Gemini
- [x] **Phase 12**: Movement Command Interpretation and Autonomy Readiness
- [x] **Phase 13**: Offline Fallback, Session Lifecycle and Recovery
- [ ] **Phase 14**: Full System Integration and User Experience
- [ ] **Phase 15**: GSD Final Review, Security, Quality and Release Readiness

---

## Phase Details & Deliverables

### Phase 1: Repository Audit, GSD Baseline and Architecture Plan
- **Status:** 🔄 Baseline Established
- **Objective:** Establish GSD planning baseline, define fixed pin maps and hardware boundaries, document electrical safety and power protocols.
- **Key Artifacts:** `.gsd/SPEC.md`, `.gsd/ARCHITECTURE.md`, `.gsd/DECISIONS.md`, `.gsd/ROADMAP.md`, `.gsd/STATE.md`, `.gsd/STACK.md`, `.gitignore`, `.env.example`.

---

### Phase 2: Firmware Foundation and Hardware Abstraction
- **Status:** ⬜ Ready for System Integration
- **Objective:** Modular ESP32 firmware on Seeed XIAO ESP32-S3 Sense: central pin map, native USB CDC logging, OPI PSRAM validation, custom SPI routing (`SCK=9, MOSI=8, MISO=-1, CS=-1`), dual I2S peripheral coordination (`I2S_NUM_0` PDM RX, `I2S_NUM_1` MAX98357A TX), and safe boot diagnostics.

---

### Phase 3: Motor Control and Local Safety Foundation
- **Status:** ✅ Complete
- **Objective:** MX1508 motor driver control (`IN1=D3, IN2=D2, IN3=D1, IN4=D0`), software ramps, maximum duration limits, automatic watchdog stop timeout, and immediate local emergency stop override.
- **Key Artifacts:** `firmware/include/board_pins.h`, `firmware/include/motor_controller.h`, `firmware/src/motor_controller.cpp`, `firmware/src/main.cpp`, `firmware/tests/test_motor_controller.cpp`. Verified with 10/10 unit tests passing.

---

### Phase 4: Display States, Expressions and Robot Persona
- **Status:** ⬜ Pending
- **Objective:** ILI9341 SPI TFT state rendering with custom SPI and hardware reset pulse on D8 (GPIO7), displaying booting, idle, listening, thinking, speaking, vision, movement, offline, and error screens for DORURU persona.

---

### Phase 5: Camera Capture and Vision Transport
- **Status:** ✅ Complete
- **Objective:** OV3660 DVP camera driver initialization, 8MB Octal PSRAM runtime verification, JPEG frame capture, buffer lifecycle management, and authenticated HTTP transport to local backend.
- **Key Artifacts:** `firmware/src/camera/camera_manager.h`, `camera_manager.cpp`, `firmware/src/transport/vision_transport.h`, `vision_transport.cpp`. Verified with host tests.

---

### Phase 6: FastAPI Backend Foundation and Device API
- **Status:** 🔄 Integrated Foundation
- **Objective:** Unified FastAPI + Flask backend on host machine with Pydantic request/response schemas, device authentication, vision/session/RAG endpoints, and movement intent contracts.

---

### Phase 7: Local Speech: faster-whisper STT and Piper TTS
- **Status:** ⬜ Pending
- **Objective:** Local STT using faster-whisper and local TTS using Piper on the development host with runtime CPU/CUDA detection and int8 fallback; audio format conversion for ESP32 I2S_NUM_1 playback.

---

### Phase 8: Gemini AI Orchestration and Session-Only Conversation
- **Status:** ⬜ Pending
- **Objective:** Google Gemini API integration using environment-configured model name (`GEMINI_MODEL`), DORURU system persona prompt, transient in-memory conversation context, and rate-limit handling.

---

### Phase 9: College Knowledge Base and RAG
- **Status:** ✅ Complete
- **Objective:** Verified college document ingestion (Markdown/PDF), semantic/lexical chunking, TF-IDF/BM25 retrieval service, and prompt grounding instructing Gemini to answer institutional facts exclusively from retrieved sources.
- **Key Artifacts:** `backend/app/rag/`, `knowledge_base/documents/`, `tests/test_rag.py` (all tests passing).

---

### Phase 10: Local Wake-Word and Voice Interaction State Machine
- **Status:** ⬜ Pending
- **Objective:** Local wake-word evaluation on ESP32-S3 (`I2S_NUM_0` PDM) with mandatory push-to-talk/manual trigger fallback, voice activity detection, and state transitions.

---

### Phase 11: Hybrid Vision with Gemini
- **Status:** ✅ Complete
- **Objective:** On-demand and event-triggered visual inspection linking OV3660 camera capture to Gemini vision via official Google GenAI SDK; smart image resizing and strict no-tracking disclaimer.
- **Key Artifacts:** `backend/app/vision/gemini_vision_service.py`, `backend/app/vision/image_processor.py`, `tests/test_vision_gemini.py`.

---

### Phase 12: Movement Command Interpretation and Autonomy Readiness
- **Status:** ✅ Complete
- **Objective:** Safe natural-language movement intent parsing, bounded command schemas, dual-tier independent validation (FastAPI + ESP32), and strict Level 1 autonomy enforcement with safe disabled states for missing sensors.
- **Key Artifacts:** `backend/app/schemas/movement.py`, `backend/app/services/movement_intent_parser.py`, `backend/app/routers/movement.py`, `firmware/include/command_validator.h`, `firmware/src/command_validator.cpp`. Verified with 24/24 pytest and 8/8 native C++ tests.

---

### Phase 13: Offline Fallback, Session Lifecycle and Recovery
- **Status:** ✅ Complete
- **Objective:** Network loss detection, automatic motor cutoff, offline display indicators, exponential backoff reconnection with overflow clamping, stale command purging, monotonic sequence replay protection, and in-memory session cleanup.
- **Key Artifacts:** `backend/app/session/session_manager.py`, `backend/app/session/command_safety.py`, `firmware/src/safety/motor_safety.cpp`, `firmware/src/transport/connectivity_manager.cpp`, `tests/test_session_recovery.py`.

---

### Phase 14: Full System Integration and User Experience
- **Status:** ⬜ Next Milestone
- **Objective:** Comprehensive integration testing across all completed modules, validating end-to-end voice, vision, movement, and recovery scenarios with manual bench checklists.

---

### Phase 15: GSD Final Review, Security, Quality and Release Readiness
- **Status:** ⬜ Future Milestone
- **Objective:** Independent engineering audit using installed GSD workflows, verifying pin maps, OPI PSRAM, electrical safety adherence, API key protection, test suites, and final delivery documentation.

---

*Last updated: 2026-10-30*
