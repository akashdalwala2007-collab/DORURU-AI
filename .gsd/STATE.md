---
updated: 2026-10-30T10:42:30+05:30
---

# STATE.md — Project State

## Current Position

**Milestone:** DORURU-AI v1.0  
**Phase:** 12 - Movement Command Interpretation and Autonomy Readiness  
**Status:** Complete / Verification Passed  
**Plan:** Plan 12.1 Complete (Backend Intent Parser, Level 1 Autonomy Gating, Firmware Independent Command Validator)  

## Last Action

Implemented and verified DORURU Phase 12 (Movement Command Interpretation and Autonomy Readiness):
- Backend Pydantic schemas created in `backend/app/schemas/movement.py`:
  - `MovementDirection` (`STOP`, `FORWARD`, `REVERSE`, `TURN_LEFT`, `TURN_RIGHT`).
  - 4-level autonomy framework with Level 1 Active and Levels 2–4 Disabled.
  - `MovementIntentRequest`, `MovementIntent`, and sequenced `MovementCommandPacket`.
- Natural-language intent parser created in `backend/app/services/movement_intent_parser.py`:
  - Standard commands mapped to strict boundaries.
  - "Come here" and "go back" mapped to bounded motions with mandatory disclaimers and approximate time bounds.
  - Unconfirmed autonomy requests ("follow me", "roam", "patrol") strictly rejected.
- FastAPI movement router created in `backend/app/routers/movement.py` (`/api/v1/movement/capabilities`, `/intent`, `/command`).
- Firmware independent command validator implemented in `firmware/include/command_validator.h` and `firmware/src/command_validator.cpp`:
  - Replay protection with strictly monotonic sequence IDs.
  - Stale packet timestamp expiration (TTL enforcement).
  - Autonomy Level 1 restriction.
- Unit testing:
  - Pytest suite `backend/tests/test_movement_intent.py`: 24/24 passed (covering STOP priority, forbidden autonomy override, "right now" lookahead, negated command rejection, bare-word rejection, duration limits, multi-worker persistent sequence IDs, lock-acquisition error conversion, uint32 bounds, sequence exhaustion protection & recovery, test fixture isolation, and clock synchronization gating).
  - Firmware test suite `firmware/tests/test_command_validator.cpp`: 8/8 passed (including sequence monotonicity, replay rejection, stale packet drops, forward skew tolerance, and UINT32_MAX exhaustion recovery).
  - Firmware motor controller test suite `firmware/tests/test_motor_controller.cpp`: 10/10 passed.

## Next Steps

1. Present Phase 12 & Phase 3 completion report, test evidence, and review resolutions to user.
2. Await user confirmation for next phase selection (e.g. Phase 4: TFT Display & Persona Foundation, or Phase 6: Core FastAPI Backend & Audio Streaming Pipeline).
3. Continue strict compliance with no-commit / no-push policy and hardware pin constraints.

## Active Decisions

| Decision | Choice | Made | Affects |
| :--- | :--- | :--- | :--- |
| **DECISION-001** | Locked Pin Mapping, Sense Pins Reserved, UART0 Bypass | 2026-10-30 | Phases 2, 3, 4, 5, 10 |
| **DECISION-002** | Tri-Tier Edge Architecture (ESP32 + Local FastAPI + Gemini Cloud) | 2026-10-30 | All Phases |
| **DECISION-003** | Local Speech Pipeline (faster-whisper STT + Piper TTS) with CPU Fallback | 2026-10-30 | Phases 6, 7, 10, 14 |
| **DECISION-004** | Local Wake-Word Engine with Mandatory Push-to-Talk Fallback | 2026-10-30 | Phases 2, 10, 14 |
| **DECISION-005** | Hybrid On-Demand Vision Architecture (OV3660 + Local FastAPI + Gemini) | 2026-10-30 | Phases 5, 6, 11 |
| **DECISION-006** | College Knowledge Base (RAG) with Source Attribution | 2026-10-30 | Phases 6, 8, 9 |
| **DECISION-007** | Session-Only In-Memory Ephemeral Conversation Lifecycle | 2026-10-30 | Phases 6, 8, 13 |
| **DECISION-008** | Bounded Movement Safety & Level 1 Autonomy Lock | 2026-10-30 | Phases 3, 6, 12 |
| **DECISION-009** | Hardware Power and Electrical Safety Protocols | 2026-10-30 | Phases 1, 2, 3, 14, 15 |

## Blockers

*None. Phase 1, Phase 3, and Phase 12 are fully verified locally.*

## Concerns

- **Electrical Ratings Unresolved**: Physical motor stall current, battery discharge capability, regulator thermal limits, and decoupling capacitors must be physically confirmed before running loaded motor tests.
- **Embedded Toolchain**: PlatformIO CLI / Arduino-CLI are not on the global PATH. In Phase 2, we will determine whether to use local PlatformIO Core inside a Python virtualenv (`pip install platformio`) or inspect user preference.

## Session Context

- Strict execution rule: NEVER run `git commit`, `git push`, or publish changes automatically.
- All implementations remain strictly local in working directory until explicit user approval.
- Hardware pin mappings (`IN1=4, IN2=3, IN3=2, IN4=1`, PDM mic `41/42`, display SPI) remain strictly locked.

---

*Last updated: 2026-10-30*

