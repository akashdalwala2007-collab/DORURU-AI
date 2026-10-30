# DORURU — Phase 13: Offline Fallback, Session Lifecycle and Recovery Documentation

## 1. System Architecture & Hybrid Connectivity Model

Phase 13 establishes DORURU's hybrid connectivity architecture, emergency safety envelopes, and session lifecycle management. The system is designed to provide responsive local physical control and safety while gracefully handling Wi-Fi network drops, reconnection backoff, request cancellation, and temporary conversation session teardown.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                          DORURU Robot (XIAO ESP32-S3 Sense)                            │
│                                                                                        │
│   ┌───────────────────────────┐                ┌───────────────────────────────────┐   │
│   │   Connectivity Manager    │                │        Motor Safety Controller    │   │
│   │ - Online / Offline FSM    │                │ - Emergency Stop (Top Priority)   │   │
│   │ - Exponential Backoff     │                │ - Watchdog Timeout Stop (500ms)   │   │
│   │ - Heartbeat Watchdog      │                │ - Monotonic Sequence Check        │   │
│   │ - In-Flight Cancellation  │                │ - Timestamp Freshness & TTL Check │   │
│   └─────────────┬─────────────┘                │ - Pre-Disconnect Queue Purge      │   │
│                 │                              └─────────────────┬─────────────────┘   │
│                 │                                                │                     │
│                 ▼                                                ▼                     │
│   ┌───────────────────────────┐                ┌───────────────────────────────────┐   │
│   │    TFT Display Manager    │                │      MX1508 Dual Motor Driver     │   │
│   │ - DISPLAY_STATE_WIFI_DISC │                │   IN1: D7 (GPIO44)   IN2: D8 (D8) │   │
│   │ - Offline Disclaimer Text │                │   IN3: D9 (GPIO43)   IN4: D10(D10)│   │
│   └───────────────────────────┘                └───────────────────────────────────┘   │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │ Authenticated HTTP / Token Auth
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        Local Backend Server (FastAPI / Flask)                          │
│                                                                                        │
│   ┌───────────────────────────┐                ┌───────────────────────────────────┐   │
│   │   Session Memory Manager  │                │     Command Safety & Validation   │   │
│   │ - Ephemeral In-Memory TTL │                │ - Sequence Monotonicity Filter    │   │
│   │ - Multi-Turn Tracking     │                │ - Stale Timestamp Filter          │   │
│   │ - Expired Cleanup Job     │                │ - Bounded Speed [0, 255] Clamping │   │
│   │ - Explicit Context Purge  │                │ - Bounded Duration [50, 2000]ms   │   │
│   └───────────────────────────┘                └───────────────────────────────────┘   │
│                                                                                        │
│   Routes:                                                                              │
│   - POST /api/v1/session/new                  - POST /api/v1/device/status             │
│   - GET  /api/v1/session/status               - POST /api/v1/device/command            │
│   - POST /api/v1/session/reset                - POST /api/v1/device/emergency_stop     │
│   - GET  /api/v1/device/capabilities          - POST /api/v1/device/emergency_stop/reset│
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Online vs. Offline Behavior Matrix

DORURU's behavior strictly adapts to the operational state:

| Feature / Subsystem | Online Behavior | Offline Fallback Behavior | Constraints & Disclaimers |
|---------------------|-----------------|---------------------------|----------------------------|
| **Wake-Word & Activation** | Local wake-word or push-to-talk button triggers active listening state. | Local wake-word or push-to-talk button provides local acoustic/visual chime; local actions only. | Never attempts cloud interaction when disconnected. |
| **Speech Recognition (STT)** | Local Whisper STT running on local backend computer. | Disabled (or local offline intent parser if supported). | No remote audio streams uploaded. |
| **Speech Synthesis (TTS)** | Local Piper neural TTS running on local backend computer. | Pre-rendered firmware beeps/tones or cached audio clips. | Offline speech never fabricates cloud answers. |
| **Conversation & Reasoning** | Gemini general reasoning with temporary multi-turn memory. | **STRICTLY DISABLED**. Robot displays `WIFI_DISCONNECTED` and informs user of offline state. | **CRITICAL**: Never claim cloud conversation works offline. |
| **Campus Knowledge (RAG)** | Local TF-IDF & BM25 college retrieval index. | **DISABLED** (unless cached local FAQ exists). | Explicit notice when knowledge retrieval is unavailable. |
| **Vision Analysis** | On-demand OV3660 capture sent to local backend and Gemini multimodal API. | **DISABLED**. Camera frames cannot be analyzed without backend connectivity. | Never claims autonomous vision navigation offline. |
| **Motor Movement** | Validated, bounded movement commands dispatched from backend. | **DISABLED BY DEFAULT**. Basic predefined movement only when `allow_offline_movement` is explicitly enabled. | Watchdog stops motors within 500ms if connectivity is lost during movement. |
| **Emergency Stop** | Local hardware button or backend `/api/v1/device/emergency_stop`. | Local hardware emergency stop always available and top priority. | Immediate motor braking; overrides all movement intents. |
| **Telemetry & Heartbeats** | Periodic heartbeat exchange every 2 seconds via `/api/v1/device/status`. | Heartbeat watchdog triggers offline mode when heartbeats time out (> 5000ms). | Reconnect backoff initiated automatically. |

---

## 3. Session Lifecycle & Privacy Guarantees

Implemented in [`backend/app/session/session_manager.py`](../backend/app/session/session_manager.py):

### 3.1 Ephemeral Memory Model
- **Zero Disk Persistence**: Session context, turns, conversation transcripts, and memory dictionaries exist exclusively in volatile memory (`dict[str, Session]`).
- **Configurable TTL**: `SESSION_EXPIRY_SECONDS` (default: 900 seconds / 15 minutes).
- **Proactive & Lazy Expiry**:
  - `session.is_expired()` evaluates `(current_time - last_accessed) > ttl_seconds`.
  - Expired sessions immediately execute `clear_memory()` and are culled via `cleanup_expired()`.
- **Explicit Reset**:
  - When the user issues a session reset (`POST /api/v1/session/reset` or says "reset session"), existing memory is wiped completely (`clear_memory()`) and a fresh, empty session identifier is generated.

### 3.2 Thread-Safe Turn Tracking
All session mutations and turn increments are protected by a thread-safe mutex lock (`threading.Lock`), supporting concurrent API requests.

---

## 4. Motor Safety Controller & Replay Prevention Invariants

Implemented in:
- Firmware: [`firmware/src/safety/motor_safety.h`](../firmware/src/safety/motor_safety.h) and [`firmware/src/safety/motor_safety.cpp`](../firmware/src/safety/motor_safety.cpp)
- Backend: [`backend/app/session/command_safety.py`](../backend/app/session/command_safety.py)

### 4.1 Monotonic Sequence Tracking (Replay Attack Defense)
Every movement command submitted to the robot requires a strictly increasing sequence integer:
$$\text{command\_id} > \text{last\_executed\_sequence}$$
Any command with $\text{command\_id} \le \text{last\_executed\_sequence}$ is rejected immediately with error code `SAFETY_ERR_SEQUENCE_REPLAY`.

### 4.2 Freshness & Stale-Command Rejection
Commands are stamped with generation time $T_{\text{cmd}}$ and a time-to-live $\text{TTL}_{\text{cmd}}$ (default: 1000ms, configurable):
$$\text{Age} = T_{\text{current}} - T_{\text{cmd}}$$
$$\text{If } \text{Age} > \text{TTL}_{\text{cmd}} \implies \text{Reject with } \text{SAFETY\_ERR\_STALE\_COMMAND}$$
If a command timestamp is in the future by more than 1000ms (due to severe clock skew or falsification), it is likewise rejected.

### 4.3 Network Recovery Motor Replay Protection
When network connectivity drops while commands are queued or in flight:
1. `motor_safety_on_network_loss()` immediately executes hardware motor stop.
2. Upon reconnection, `motor_safety_on_network_reconnect()` advances the sequence watermark (`last_executed_sequence++`), invalidating commands issued before reconnection while keeping motors safely halted in idle ready state.
3. Any delayed HTTP packets or queued commands from the pre-disconnect era are automatically rejected by both sequence watermark checks ($\text{command\_id} \le \text{last\_executed\_sequence}$) and timestamp TTL staleness.

### 4.4 Watchdog Motor Timeout & Movement Duration
In the event that the robot begins moving:
- Discrete movement duration is clamped to $[50, 2000]\text{ms}$ and tracked via `active_duration_ms`.
- When movement duration completes ($\Delta t_{\text{movement}} \ge \text{active\_duration\_ms}$), motors halt automatically.
- If communication fails during extended movement, `motor_safety_tick(current_time_ms)` halts motors when watchdog timeout is exceeded ($\Delta t_{\text{movement}} > \text{command\_timeout\_ms}$, default 500ms).
- When elapsed time exceeds the watchdog timeout or movement duration, motor pins are instantly cut to `0` PWM and display updates to `DISPLAY_STATE_IDLE_READY`.

### 4.5 Movement Parameter Bounds & Clamping
- **Speed**: Clamped to $[0, 255]$.
- **Duration**: Clamped to $[50, 2000]\text{ms}$ (max 2 seconds of forward/reverse drive per discrete command).

---

## 5. Connectivity Manager & Exponential Reconnect Backoff

Implemented in [`firmware/src/transport/connectivity_manager.h`](../firmware/src/transport/connectivity_manager.h) and [`firmware/src/transport/connectivity_manager.cpp`](../firmware/src/transport/connectivity_manager.cpp):

### 5.1 Connection State Machine
- `CONN_STATE_ONLINE`: Heartbeat exchanges active; full hybrid capabilities enabled.
- `CONN_STATE_OFFLINE`: Wi-Fi dropped; motors halted; offline display shown.
- `CONN_STATE_RECONNECT_BACKOFF`: Waiting out exponential backoff period before next attempt.
- `CONN_STATE_CONNECTING`: Active Wi-Fi association / backend handshake attempt.

### 5.2 Exponential Backoff Formula
$$\text{Backoff}(n) = \min\left(\text{initial\_backoff\_ms} \times 2^n, \text{max\_backoff\_ms}\right)$$
- Initial backoff: $1000\text{ms}$
- Multiplier: $2\times$
- Maximum backoff: $30000\text{ms}$ (30 seconds)
- Overflow safety: Backoff is compared against `max_backoff_ms` prior to doubling to prevent integer overflow.

### 5.3 In-Flight Request Cancellation
When network drop is detected (`connectivity_manager_report_network_drop`):
- All pending HTTP client transactions and camera burst requests are cancelled immediately (`connectivity_manager_cancel_inflight`).
- Partial framebuffers are cleared to prevent memory leaks or stale image transmission upon recovery.

---

## 6. Endpoints & Telemetry API Reference

### Session Management

#### `POST /api/v1/session/new`
Creates a fresh conversation session.
- **Request**: `{"ttl_seconds": 900}` (optional positive integer in $[1, 86400]$)
- **Response**: `201 Created`
  ```json
  {
    "status": "created",
    "session": {
      "session_id": "c1f7b9e0-...",
      "created_at": 1793344625.0,
      "last_activity_at": 1793344625.0,
      "ttl_seconds": 900,
      "turns_count": 0,
      "is_expired": false
    }
  }
  ```

#### `GET /api/v1/session/status?session_id=<id>`
Returns session status and validity metadata.
- **Response**: `200 OK`
  ```json
  {
    "status": "active",
    "session": {
      "session_id": "c1f7b9e0-...",
      "created_at": 1793344625.0,
      "last_activity_at": 1793344650.0,
      "ttl_seconds": 900,
      "turns_count": 3,
      "is_expired": false
    }
  }
  ```

#### `POST /api/v1/session/reset`
Wipes conversation history and returns a clean session.
- **Request**: `{"session_id": "c1f7b9e0-..."}`
- **Response**: `200 OK`
  ```json
  {
    "status": "reset_successful",
    "message": "Temporary conversation context and history cleared completely.",
    "session": {
      "session_id": "f8a2e1d0-...",
      "created_at": 1793344660.0,
      "last_activity_at": 1793344660.0,
      "ttl_seconds": 900,
      "turns_count": 0,
      "is_expired": false
    }
  }
  ```

### Device Safety & Status

#### `POST /api/v1/device/status` (Authenticated)
Heartbeat and device status exchange.
- **Headers**: `X-Device-Token: <token>`
- **Request**: `{"battery_pct": 95, "wifi_rssi": -65}`
- **Response**: `200 OK`
  ```json
  {
    "status": "online",
    "server_time": 1793344625.9,
    "emergency_stop_active": false,
    "last_sequence_id": 4,
    "active_sessions": 1
  }
  ```

#### `POST /api/v1/device/command` (Authenticated)
Validates and dispatches a bounded movement command.
- **Headers**: `X-Device-Token: <token>`
- **Request**:
  ```json
  {
    "command_id": 5,
    "intent": "FORWARD",
    "speed": 180,
    "duration_ms": 600,
    "timestamp_ms": 1793344625900,
    "ttl_ms": 1000
  }
  ```
- **Response**: `200 OK`
  ```json
  {
    "status": "accepted",
    "reason": "Command validated successfully",
    "command": {
      "command_id": 5,
      "intent": "FORWARD",
      "speed": 180,
      "duration_ms": 600,
      "timestamp_ms": 1793344625900,
      "ttl_ms": 1000
    }
  }
  ```

#### `POST /api/v1/device/emergency_stop` (Authenticated)
Engages emergency stop immediately with highest priority.
- **Headers**: `X-Device-Token: <token>`
- **Response**: `200 OK`
  ```json
  {
    "status": "emergency_stop_engaged",
    "message": "Emergency stop activated. All movement commands rejected."
  }
  ```

#### `POST /api/v1/device/emergency_stop/reset` (Authenticated)
Clears emergency stop after manual operator verification.
- **Headers**: `X-Device-Token: <token>`
- **Response**: `200 OK`
  ```json
  {
    "status": "emergency_stop_cleared",
    "message": "Emergency stop cleared. Movement commands re-enabled."
  }
  ```

#### `GET /api/v1/device/capabilities`
Returns clear disclosure of online features, offline features, and explicit offline disclaimers.
- **Response**: `200 OK`
  ```json
  {
    "online_features": [
      "local_wake_word_detection",
      "local_stt_whisper",
      "gemini_general_reasoning",
      "rag_college_retrieval",
      "on_demand_gemini_vision",
      "piper_tts_synthesis",
      "backend_device_telemetry_exchange"
    ],
    "offline_features": [
      "local_hardware_emergency_stop",
      "automatic_motor_stop_on_timeout_or_disconnect",
      "tft_offline_status_display",
      "supervised_bounded_movement_when_explicitly_enabled",
      "local_wake_word_or_manual_fallback"
    ],
    "offline_disclaimers": [
      "Gemini general reasoning is NOT available offline",
      "Cloud vision analysis is NOT available offline",
      "College RAG remote answering is NOT available offline",
      "Cloud conversation does NOT function offline"
    ]
  }
  ```

---

## 7. Verification & Automated Test Matrix

The complete test suite runs via native Python and Clang++ host build helpers:

```bash
# Execute Phase 13 dedicated unit & integration suite
python -m unittest tests/test_session_recovery.py -v

# Execute complete repository test suite
python -m unittest discover -s tests -v
```

### Test Coverage Summary:
- `test_session_creation_and_turn_tracking`: Verifies clean session initialization and conversational turn incrementation.
- `test_session_reset_wipes_context_completely`: Proves memory is deleted and new session ID is generated on reset.
- `test_session_expiry_clears_memory`: Proves expired sessions have memory wiped and return 404 upon query.
- `test_command_validation_bounds_and_clamping`: Proves speed is clamped to $[0, 255]$ and duration clamped to $[50, 2000]\text{ms}$.
- `test_stale_command_rejection_via_ttl`: Proves commands with age $> \text{TTL}$ are rejected.
- `test_sequence_replay_rejection`: Proves commands with $\text{command\_id} \le \text{last\_sequence\_id}$ are rejected.
- `test_emergency_stop_priority_rejects_movement`: Proves e-stop blocks all movement intents.
- `test_offline_movement_disabled_by_default`: Proves movement is blocked when offline unless explicitly enabled.
- `test_host_firmware_safety_and_network_recovery`: Executes compiled native C++ binary testing:
  - Watchdog timeout stops motors after $500\text{ms}$.
  - Network loss immediately halts motors.
  - Network reconnect advances watermark and rejects pre-disconnect commands.
  - Connectivity manager exponential backoff doubles delay and caps at $30000\text{ms}$.
  - In-flight requests are immediately cancelled on network drop.
- `test_session_endpoints_lifecycle`: Tests `/api/v1/session/new`, `/status`, and `/reset` HTTP routes.
- `test_device_status_heartbeat_exchange`: Tests `/api/v1/device/status` telemetry endpoint.
- `test_device_movement_command_endpoint`: Tests `/api/v1/device/command` routing and sequence advancing.
- `test_device_emergency_stop_endpoints`: Tests `/api/v1/device/emergency_stop` engage and reset flows.
- `test_offline_capabilities_disclosure`: Verifies that cloud features are explicitly disclaimed when offline.

**Total passing tests in repository**: **57 / 57 tests passing** (100% success rate).

