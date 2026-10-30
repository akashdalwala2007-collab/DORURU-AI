---
updated: 2026-10-30T12:50:00+05:30
---

# Project State

## Current Position

**Milestone**: Safety, Connectivity & Lifecycle Management
**Phase**: 13 - Offline Fallback, Session Lifecycle and Recovery
**Status**: verified
**Plan**: 13.01 - Hybrid Connectivity, Motor Safety Watchdog, Replay Prevention, and Session Lifecycle

## Last Action

Implemented complete Phase 13 Offline Fallback, Session Lifecycle and Recovery:
- Implemented `backend/app/session/session_manager.py` with in-memory multi-turn sessions, configurable TTL (900s), active expiry purge (`clear_memory()`), and explicit reset API.
- Implemented `backend/app/session/command_safety.py` enforcing monotonic sequence validation, staleness timestamp checks ($T_{current} - T_{cmd} > TTL$), speed/duration clamping, and e-stop enforcement.
- Added session and device safety endpoints to `backend/app/main.py`: `/api/v1/session/new`, `/status`, `/reset`, `/api/v1/device/status`, `/command`, `/emergency_stop`, `/emergency_stop/reset`, `/capabilities`.
- Implemented `firmware/src/safety/motor_safety.h` and `.cpp` with MX1508 motor drive/stop, movement duration tracking, 500ms command timeout watchdog, immediate halt on network drop, sequence replay rejection, and rejection of pre-disconnect commands after reconnect.
- Implemented `firmware/src/transport/connectivity_manager.h` and `.cpp` with deterministic exponential backoff ($1\text{s} \to 30\text{s}$ with overflow protection), heartbeat watchdog, and in-flight request cancellation.
- Built comprehensive test suite `tests/test_session_recovery.py` (17 unit/integration tests) including compiled host C++ execution.
- 60/60 tests passing across the entire repository (100% success rate).

## Next Steps

1. Review Phase 13 test evidence with user.
2. Proceed to Phase 14: Full System Integration and User Experience.

## Active Decisions

| Decision | Choice | Made | Affects |
|----------|--------|------|---------|
| Camera Sensor Model | Preserved OV3660 (PID 0x3660), rejecting silent OV2640 substitution | 2026-10-30 | Firmware, Vision Transport, Phase 11 |
| Frame Buffer Allocation | Dynamically sized based on runtime PSRAM (VGA/Q12 with PSRAM, QVGA/Q20 DRAM fallback) | 2026-10-30 | Camera Manager, Memory Heap |
| Vision Architecture | Hybrid on-demand (single or controlled burst <= 3) and selected events; no continuous streaming | 2026-10-30 | Vision Transport, Backend API, Phase 11 |
| Cloud Credentials | Gemini API keys kept exclusively on backend server; zero credentials on ESP32 | 2026-10-30 | Security, Firmware, Backend |
| Frame Storage Policy | Ephemeral; direct stream over authenticated HTTP and immediate framebuffer release | 2026-10-30 | Privacy, Memory Management |
| College RAG Engine | Local TF-IDF & BM25 retriever with inverted index and metadata preservation | 2026-10-30 | Knowledge Base, RAG, Phase 14 |
| Missing Evidence Policy | Explicit refusal to hallucinate; returns unverified notice and requests authoritative source | 2026-10-30 | Grounding, AI Persona, Accuracy |
| Re-indexing Method | Out-of-band CLI tool + API endpoint; updates on the fly without application code modification | 2026-10-30 | Ops, Maintenance, Knowledge Base |
| Gemini Vision Integration | Official Google GenAI SDK (`google.genai`) with configurable model from env; strict no-tracking disclaimer | 2026-10-30 | AI Orchestration, Persona, Safety |
| Session Memory Privacy | Ephemeral volatile memory only; strict memory wipe on reset or TTL expiry | 2026-10-30 | Privacy, Session Management, Security |
| Motor Safety & Reconnect | Watchdog timeout stop (500ms), movement duration enforcement, monotonic sequence replay protection, rejection of pre-disconnect commands after reconnect | 2026-10-30 | Firmware Safety, Transport, Motor Control |
| Offline Behavior Disclaimer | Strict refusal to simulate or pretend cloud features/Gemini work offline; clear TFT indication | 2026-10-30 | Robot Persona, Reliability, Display |

## Blockers

None.

## Concerns

- Physical hardware verification requires connecting the real Seeed XIAO ESP32-S3 Sense board with camera module attached to verify live SCCB register probing in the lab environment.

