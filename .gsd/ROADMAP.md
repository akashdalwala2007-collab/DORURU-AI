# DORURU-AI Roadmap

## Phases

- [ ] **Phase 1**: Repository Audit, GSD Baseline and Architecture Plan
- [ ] **Phase 2**: Firmware Foundation and Hardware Abstraction
- [ ] **Phase 3**: Motor Control and Local Safety Foundation
- [ ] **Phase 4**: Display States, Expressions and Robot Persona
- [x] **Phase 5**: Camera Capture and Vision Transport
- [ ] **Phase 6**: FastAPI Backend Foundation and Device API
- [ ] **Phase 7**: Local Speech: Faster-Whisper STT and Piper TTS
- [ ] **Phase 8**: Gemini AI Orchestration and Session-Only Conversation
- [x] **Phase 9**: College Knowledge Base and RAG
- [ ] **Phase 10**: Local Wake-Word and Voice Interaction State Machine
- [x] **Phase 11**: Hybrid Vision with Gemini
- [ ] **Phase 12**: Movement Command Interpretation and Autonomy Readiness
- [x] **Phase 13**: Offline Fallback, Session Lifecycle and Recovery
- [ ] **Phase 14**: Full System Integration and User Experience
- [ ] **Phase 15**: GSD Final Review, Security, Quality and Release Readiness

## Phase 13 Scope & Delivery
- **Hybrid Connectivity**: Online full-featured reasoning & local STT/TTS vs offline fallback with strict disclaimers.
- **Motor Safety Controller**: Watchdog timeout motor halt (500ms), movement duration enforcement [50, 2000]ms, monotonic sequence replay protection, staleness TTL checks, and emergency stop priority.
- **Network Recovery Guarantee**: Immediate motor halt on network loss; pre-disconnect commands rejected via monotonic sequence checks and TTL staleness upon reconnect.
- **Connectivity Manager**: Deterministic exponential reconnect backoff with overflow clamping to max backoff cap; heartbeat watchdog; in-flight request cancellation on disconnect.
- **Session Lifecycle & Privacy**: Ephemeral in-memory multi-turn sessions with configurable TTL (900s), automatic expired memory wipe, and explicit reset endpoints.
- **Verification**: 17 dedicated unit/integration tests with host C++ firmware verification; 60/60 tests passing across the entire repository.

## Phase 5 Scope & Delivery
- **Driver**: OV3660 camera capture configuration with dedicated XIAO ESP32-S3 Sense pinout.
- **Sensor Verification**: Probing and PID verification (0x3660).
- **Memory**: 8MB Octal PSRAM runtime inspection and dynamic buffer sizing.
- **Vision Modes**: Hybrid on-demand (single / burst <= 3) & selected events.
- **Transport**: Authenticated local API with token verification and ephemeral policy.
- **Display**: TFT state coordination.
- **Safety**: Wi-Fi drop fail-fast resilience, buffer leak protection, server-side Gemini credentials only.

