---
updated: 2026-10-30T15:30:00+05:30
---

# STATE.md — Project State

## Current Position

**Milestone:** DORURU-AI v1.0 — Unified Integration  
**Phases Completed:** Phase 3, Phase 5, Phase 9, Phase 11, Phase 12, Phase 13  
**Status:** Unified Integration Verified (100% Tests Passing: 62 Unittest + 24 Pytest = 86 Total)  
**Plan:** Integration of Teammate Movement Autonomy & Local Vision/Session/RAG Capabilities  

## Implementation State Summary

The repository unites both parallel development tracks:

1. **Remote Teammate Track (Phases 3 & 12)**:
   - Backend Pydantic schemas in `backend/app/schemas/movement.py` (Autonomy Level 1, Direction enums, MovementCommandPacket).
   - Natural language movement parser in `backend/app/services/movement_intent_parser.py`.
   - FastAPI movement router in `backend/app/routers/movement.py` (`/api/v1/movement/capabilities`, `/intent`, `/command`).
   - MX1508 motor controller firmware in `firmware/include/motor_controller.h`, `firmware/src/motor_controller.cpp`.
   - Independent firmware command validator in `firmware/include/command_validator.h`, `firmware/src/command_validator.cpp`.

2. **Local Work Track (Phases 5, 9, 11 & 13)**:
   - OV3660 camera initialization and transport in `firmware/src/camera/camera_manager.cpp` and `firmware/src/transport/vision_transport.cpp`.
   - College RAG knowledge base in `backend/app/rag/` with document ingestion and TF-IDF/BM25 retrieval.
   - Hybrid Gemini multimodal vision in `backend/app/vision/gemini_vision_service.py` and `image_processor.py`.
   - Offline fallback, session lifecycle, and emergency stop safety in `backend/app/session/` and `firmware/src/safety/motor_safety.cpp`.

3. **Unified Backend & Firmware**:
   - `backend/app/main.py`: Dual-stack ASGI/WSGI architecture serving FastAPI movement router endpoints and Flask vision/RAG/session endpoints simultaneously.
   - `firmware/src/main.cpp`: Combined native USB CDC setup, PSRAM inspection, display callback registration, motor controller initialization, camera manager initialization, and non-blocking bench console.
   - `firmware/include/board_pins.h`: Unified C++ namespace and preprocessor macros preserving confirmed DORURU pin assignments.

## Verification Evidence

- **Unittest Suite (`tests/`)**: 62/62 tests passing.
  - End-to-end camera capture, display states, and network recovery simulation.
  - College RAG query classification, chunking, source attribution, and conflicting document handling.
  - Ephemeral session creation, TTL expiration, memory wipe, and reset.
  - Monotonic sequence verification, bounded movement clamping, and emergency stop priority.
  - Gemini vision mock testing, image resizing, and error handling.
- **Pytest Suite (`backend/tests/`)**: 24/24 tests passing.
  - Stop phrase priority, forward/turn phrase parsing, bare direction rejection, duration bounds.
  - Sequence persistence across restarts, lock acquisition safety, and sequence exhaustion recovery.
- **Total Passing Tests**: 86/86 (100% pass rate).

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

*None. Unified integration is complete and all 86 unit and integration tests are green.*

## Concerns

- **Electrical Ratings Unresolved**: Physical motor stall current, battery discharge capability, regulator thermal limits, and decoupling capacitors must be physically confirmed before running loaded motor tests.
- **Embedded Toolchain**: PlatformIO CLI / Arduino-CLI are not on the global PATH. In Phase 2, we will determine whether to use local PlatformIO Core inside a Python virtualenv (`pip install platformio`) or inspect user preference.

## Session Context

- Strict execution rule: NEVER run `git commit`, `git push`, or publish changes automatically without explicit user review.
- All implementations remain strictly local in working directory until explicit user approval.
- Hardware pin mappings (`IN1=4, IN2=3, IN3=2, IN4=1`, PDM mic `41/42`, display SPI) remain strictly locked.

---

*Last updated: 2026-10-30*
