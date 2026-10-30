---
updated: 2026-10-30T16:30:00+05:30
---

# STATE.md — Project State

## Current Position

**Milestone:** DORURU-AI v1.0 — Unified Integration  
**Phases Completed:** Phase 3, Phase 4, Phase 5, Phase 6, Phase 9, Phase 11, Phase 12, Phase 13  
**Status:** Unified Integration Verified (100% Tests Passing: 90 Unittest + 28 Pytest = 118 Total)  
**Plan:** Integration of Teammate Movement Autonomy & Local Vision/Session/RAG Capabilities  

## Implementation State Summary

The repository unites all parallel development tracks:

1. **FastAPI Backend Foundation & Device API (Phase 6)**:
   - Environment-driven configuration in `backend/app/config.py` supporting dynamic Gemini model selection, local STT/TTS paths, timeouts, and payload limits.
   - Pydantic schemas in `backend/app/schemas/` (`device.py`, `voice.py`, `session.py`, `movement.py`).
   - Standardized structured logging in `backend/app/logging_config.py`.
   - Device registration with constant-time HMAC token validation and device allowlisting in `backend/app/routers/deps.py` and `device.py`.
   - Audio upload and Speech-to-Text transcription (`/api/v1/voice/transcribe`) with payload bounds and MIME validation.
   - Text-to-Speech synthesis (`/api/v1/voice/synthesize`) enforcing the 16kHz 16-bit mono PCM/WAV audio delivery contract for MAX98357A speaker playback.
   - Unified conversational voice query orchestrator (`/api/v1/voice/query`) triaging queries across Movement Intent, College RAG, and Gemini Reasoning with DORURU robot persona.
   - Ephemeral session lifecycle (`/api/v1/session/new`, `/status`, `/reset`) with thread-safe in-memory state and TTL purging.
   - Comprehensive documentation in `docs/PHASE_6_FASTAPI_BACKEND.md` and 16 unit tests in `tests/test_fastapi_backend.py`.

2. **Movement Intent & Autonomy Readiness Track (Phases 3 & 12)**:
   - Backend Pydantic schemas in `backend/app/schemas/movement.py` (Autonomy Level 1, Direction enums, MovementCommandPacket).
   - Natural language movement parser in `backend/app/services/movement_intent_parser.py` (enforcing STOP priority, negation rejection, approximate distance disclaimers, and rejection of unconfirmed Autonomy Levels 2–4).
   - FastAPI movement router in `backend/app/routers/movement.py` (`/api/v1/movement/capabilities`, `/intent`, `/command`, `/handshake`).
   - MX1508 motor controller firmware in `firmware/include/motor_controller.h`, `firmware/src/motor_controller.cpp`.
   - Independent firmware command validator in `firmware/include/command_validator.h`, `firmware/src/command_validator.cpp`.
   - Hardware sensor abstraction in `firmware/include/sensor_interface.h`, `firmware/src/sensor_interface.cpp` (reporting `SensorStatus::UNAVAILABLE` and safe disabled defaults).
   - Architectural documentation in `docs/PHASE_12_MOVEMENT_AUTONOMY.md`.

2. **Vision, RAG, and Session Recovery Track (Phases 5, 9, 11 & 13)**:
   - OV3660 camera initialization and transport in `firmware/src/camera/camera_manager.cpp` and `firmware/src/transport/vision_transport.cpp`.
   - College RAG knowledge base in `backend/app/rag/` with document ingestion and TF-IDF/BM25 retrieval.
   - Hybrid Gemini multimodal vision in `backend/app/vision/gemini_vision_service.py` and `image_processor.py`.
   - Offline fallback, session lifecycle, and emergency stop safety in `backend/app/session/` and `firmware/src/safety/motor_safety.cpp`.

3. **TFT Display & DORURU Robot Persona (Phase 4)**:
   - ILI9341 SPI driver in `firmware/src/display/ili9341_driver.h`, `firmware/src/display/ili9341_driver.cpp` on confirmed custom pins (`SCK=GPIO9, MOSI=GPIO8, MISO=-1, CS=-1, DC=GPIO44, RST=GPIO7`).
   - Hardware reset pulse executed on D8 (GPIO7) at boot; D7 protected from UART0 via Native USB CDC logging.
   - Expressive DORURU robot persona in `firmware/src/display/doruru_persona.h`, `firmware/src/display/doruru_persona.cpp` rendering 13 states with natural blinking, audio equalizer, thinking dots, speech mouth, and vision reticle.
   - Display demo mode (`'D'` on serial bench console) cycling through all screens safely without motor motion.
   - High-contrast fail-safe rendering fallback protecting against animation faults.
   - Documentation in `docs/PHASE_4_DISPLAY_PERSONA.md` and unit tests in `tests/test_display_persona.py`.

4. **Unified Backend & Host Test Harness**:
   - `backend/app/main.py`: Dual-stack ASGI/WSGI architecture serving FastAPI movement router endpoints and Flask vision/RAG/session endpoints simultaneously.
   - `tests/host_test_helper.py`: Compiler locator and build helper invoking `clang++` to rebuild `host_firmware_test.exe` whenever C++ source/header files change, with automated code integrity fallback for Windows SAC environments.

## Verification Evidence

- **Unittest Suite (`tests/`)**: 90/90 tests passing (including Phase 6 FastAPI backend, Phase 4 display states & persona).
  - FastAPI device registration, health checks, audio transcription, Piper TTS audio delivery contract, and voice query routing.
  - End-to-end camera capture, display states, and network recovery simulation.
  - College RAG query classification, chunking, source attribution, and conflicting document handling.
  - Ephemeral session creation, TTL expiration, memory wipe, and reset.
  - Monotonic sequence verification, bounded movement clamping, and emergency stop priority.
  - Gemini vision mock testing, image resizing, and error handling.
- **Pytest Suite (`backend/tests/`)**: 28/28 tests passing.
  - Stop phrase priority (12 variants), forward/turn phrase parsing, bare direction rejection, duration bounds.
  - Arbitrary model text execution rejection (HTTP 422).
  - Higher autonomy levels rejection (HTTP 400).
  - Natural language phrase ("come here") mapping to approximate forward motion without user localization.
  - Sequence persistence across restarts, lock acquisition safety, and sequence exhaustion recovery.
  - Autonomy capability report verifying Level 1 active and Levels 2-4 disabled.
- **Host C++ Test Suites**:
  - `tests/host_firmware_test.cpp`: 9/9 assertions passing (including display subsystem, hardware reset, demo mode & fallback).
  - `firmware/tests/test_command_validator.cpp`: 8/8 tests passing.
  - `firmware/tests/test_motor_controller.cpp`: 10/10 tests passing.
- **Total Passing Tests**: 118 / 118 (100% pass rate).

## Active Decisions

| Decision | Choice | Made | Affects |
| :--- | :--- | :--- | :--- |
| **DECISION-001** | Locked Pin Mapping, Sense Pins Reserved, UART0 Bypass | 2026-10-30 | Phases 2, 3, 4, 5, 10 |
| **DECISION-002** | Tri-Tier Edge Architecture (ESP32 + Local Backend + Gemini Cloud) | 2026-10-30 | All Phases |
| **DECISION-003** | Local Speech Pipeline (faster-whisper STT + Piper TTS) with CPU Fallback | 2026-10-30 | Phases 6, 7, 10, 14 |
| **DECISION-004** | Local Wake-Word Engine with Mandatory Push-to-Talk Fallback | 2026-10-30 | Phases 2, 10, 14 |
| **DECISION-005** | Hybrid On-Demand Vision Architecture (OV3660 + Local Backend + Gemini) | 2026-10-30 | Phases 5, 6, 11 |
| **DECISION-006** | College Knowledge Base (RAG) with Source Attribution & Anti-Hallucination | 2026-10-30 | Phases 6, 8, 9 |
| **DECISION-007** | Session-Only In-Memory Ephemeral Conversation Lifecycle | 2026-10-30 | Phases 6, 8, 13 |
| **DECISION-008** | Bounded Movement Safety & Level 1 Autonomy Lock | 2026-10-30 | Phases 3, 6, 12, 13 |
| **DECISION-009** | Hardware Power and Electrical Safety Protocols | 2026-10-30 | Phases 1, 2, 3, 14, 15 |
| **DECISION-010** | Dual ASGI/WSGI Backend Architecture (FastAPI + Flask WSGIMiddleware) | 2026-10-30 | Backend, Testing, Integration |

## Blockers

*None. Unified integration is complete and all 90 unit and integration tests are green.*

## Concerns

- **Electrical Ratings Unresolved**: Physical motor stall current, battery discharge capability, regulator thermal limits, and decoupling capacitors must be physically confirmed before running loaded motor tests.

## Session Context

- Strict execution rule: NEVER run `git commit`, `git push`, or publish changes automatically without explicit user review.
- All implementations remain strictly local in working directory until explicit user approval.
- Hardware pin mappings (`IN1=4, IN2=3, IN3=2, IN4=1`, PDM mic `41/42`, display SPI) remain strictly locked.

---

*Last updated: 2026-10-30*
