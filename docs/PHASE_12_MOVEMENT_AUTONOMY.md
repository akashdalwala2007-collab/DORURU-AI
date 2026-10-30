# DORURU — Phase 12: Movement Command Interpretation and Autonomy Readiness

## 1. System Architecture & Safety Envelope

Phase 12 establishes the defense-in-depth movement intent layer for DORURU. The system translates spoken or typed natural language into strictly bounded, sequenced, and timed motion commands while enforcing strict autonomy boundaries and electrical/mechanical safety limits.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        User Request / Gemini Voice Dialogue                            │
│                  "DORURU, come here" / "Move forward for 1 second"                     │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                     Layer 1: Natural Language Intent Parsing                           │
│                     (backend/app/services/movement_intent_parser.py)                   │
│                                                                                        │
│   - Absolute STOP Priority: "stop", "halt", "freeze", "emergency stop", "don't move"   │
│   - Forbidden Autonomy Filter: Rejects user-following, tracking, roaming, SLAM         │
│   - Negation Filter: Rejects "do not move forward", "don't turn right"                 │
│   - Safe Phrase Mapping:                                                               │
│       * "come here" -> FORWARD with approximate/no-localization disclaimer             │
│       * "go back"   -> REVERSE with approximate disclaimer                             │
│       * "forward", "turn left", "turn right" -> strictly bounded directions            │
│   - Bound Enforcement: Speed clamped [60..220] PWM, Duration [50..3000]ms              │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                     Layer 2: FastAPI Schema Validation & Dispatch                      │
│                     (backend/app/routers/movement.py)                                  │
│                                                                                        │
│   - Strict Schema: Rejects raw text sent directly to /command (HTTP 422)               │
│   - Level 1 Autonomy Lock: Rejects commands with AutonomyLevel > 1 (HTTP 400)         │
│   - Device Clock Synchronization: Enforces handshake clock sync before dispatch        │
│   - Persistent Monotonic Sequence: Interprocess-locked sequence counter                │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │ MovementCommandPacket (JSON / UART / HTTP)
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                     Layer 3: Independent ESP32 Firmware Validation                     │
│                     (firmware/include/command_validator.h)                             │
│                                                                                        │
│   - Defense-in-Depth: Never blindly executes remote backend or model text              │
│   - Emergency Stop Check: Rejects all commands when e-stop is active                   │
│   - Autonomy Check: Rejects any command with autonomy_level != 1                       │
│   - Replay Protection: Rejects any sequence_id <= last_sequence_id_                    │
│   - Freshness & TTL Check: Rejects packets older than TTL (or future skew > 200ms)     │
│   - Parameter Bounds: Speed [60..220] PWM, Duration [50..3000]ms                       │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │ Validated MotionCommand
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                     Layer 4: Local Motor Safety Controller                             │
│                     (firmware/include/motor_controller.h)                              │
│                                                                                        │
│   - Startup Invariant: All motor pins (IN1..IN4) forced LOW at boot; default STOP      │
│   - Local Emergency Stop: Top priority; immediate motor halt; locks controller         │
│   - Automatic Stop Watchdog: Terminates motion automatically when duration expires     │
│   - Heartbeat Watchdog: Halts motors if backend/Wi-Fi comms drop for > 1500ms          │
│   - PWM Slew-Rate Limiter: Soft-start ramp prevents motor inrush current spikes        │
│   - Physical Isolation: Motors powered strictly from independent supply, NOT 3.3V/5V   │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 4-Level Autonomy Capability Framework

DORURU implements a strict 4-level autonomy capability framework to prevent false autonomy claims and guarantee safe physical operation:

| Level | Capability Name | Hardware Prerequisites | Status in v1.0 | Operational Behavior & Disclaimers |
| :---: | :--- | :--- | :---: | :--- |
| **Level 1** | **Bounded Timed Movement** | MX1508 Dual DC Motor Driver, independent battery supply | **ACTIVE** | Timed open-loop movement only. Speed is capped [60..220] PWM; duration is capped [50..3000]ms. **Distance and turn angles are approximate.** |
| **Level 2** | **Obstacle-Aware Movement** | Compatible distance sensor (Ultrasonic / ToF LiDAR) wired & verified | **DISABLED** | Clean sensor interface (`ISensorProvider`) returns `SensorStatus::UNAVAILABLE` and `-1.0f`. Autonomous roaming and obstacle avoidance are strictly blocked. |
| **Level 3** | **Odometry-Based Movement** | Dual quadrature wheel optical encoders installed & verified | **DISABLED** | Encoder interface returns `SensorStatus::UNAVAILABLE` and `0` ticks. Distance-based or coordinate-based movements are rejected. |
| **Level 4** | **User-Following & Destination SLAM** | Person-tracking vision, indoor localization, or SLAM sensor array | **DISABLED** | Commands requesting user tracking ("follow me") or room navigation ("go to lab") are rejected with HTTP 400. "Come here" maps to approximate forward motion only. |

> [!IMPORTANT]
> **FALSE AUTONOMY PROHIBITION**:
> The system persona, API responses, and firmware state strictly disclaim Levels 2–4. The phrase `"come here"` maps to a conservative 1.0–1.5s bounded forward motion with the mandatory disclaimer:
> *"Command 'come here' mapped to bounded forward movement. Note: distance is approximate and does NOT locate user position (Level 4 tracking unconfirmed)."*

---

## 3. Supported Movement Intents & Phrase Mappings

| Direction Enum | Natural Language Triggers | Default Speed | Default Duration | Safety Limits & Behavior |
| :--- | :--- | :---: | :---: | :--- |
| **`STOP`** | `"stop"`, `"halt"`, `"freeze"`, `"emergency stop"`, `"brake"`, `"don't move"`, `"wait"` | 0 PWM | 0 ms | **Highest priority**. Always executes immediately regardless of syntax or sentence context. |
| **`FORWARD`** | `"forward"`, `"go forward"`, `"move forward"`, `"drive forward"`, `"come here"`, `"come closer"` | 150 PWM | 1000 ms | Clamped to max 3000ms (1500ms cap for "come here"). Distance is approximate. |
| **`REVERSE`** | `"go back"`, `"back up"`, `"reverse"`, `"move back"`, `"step back"`, `"backward"` | 150 PWM | 1000 ms | Clamped to max 1500ms for safety. Open-loop reverse motion. |
| **`TURN_LEFT`** | `"turn left"`, `"pivot left"`, `"spin left"`, `"rotate left"` | 150 PWM | 1000 ms | Differential pivot: Left wheel reverse, Right wheel forward. Clamped to max 1000ms. |
| **`TURN_RIGHT`** | `"turn right"`, `"pivot right"`, `"spin right"`, `"rotate right"` | 150 PWM | 1000 ms | Differential pivot: Left wheel forward, Right wheel reverse. Clamped to max 1000ms. |

### Negated Commands & Rejection Protocol:
- Commands with negation prefixes (`"do not move forward"`, `"don't turn left"`, `"never go forward"`) are **strictly rejected** (`UnknownMovementIntentError`), preventing unintended robot motion.
- Bare ambiguous direction words (`"ahead"`, `"straight"`, `"left"`, `"right"`) are rejected to prevent false triggers from normal conversation.

---

## 4. API Endpoints Reference

### 1. `GET /api/v1/movement/capabilities`
Returns the active autonomy level and sensor capability feature flags.

**Response (200 OK):**
```json
{
  "active_level": 1,
  "level_name": "Level 1: Bounded Timed Movement",
  "obstacle_avoidance_enabled": false,
  "wheel_odometry_enabled": false,
  "user_following_enabled": false,
  "slam_navigation_enabled": false,
  "disclaimer": "Without verified wheel encoders and distance sensors, DORURU movements are approximate and time-bounded only. Autonomous roaming, obstacle avoidance, and user localization are strictly disabled."
}
```

### 2. `POST /api/v1/movement/intent`
Parses spoken or typed natural language into a strictly validated `MovementIntent`.

**Request:**
```json
{
  "text": "DORURU, please come here"
}
```

**Response (200 OK):**
```json
{
  "direction": "FORWARD",
  "speed_pwm": 150,
  "duration_ms": 1000,
  "autonomy_level": 1,
  "is_approximate_timed": true,
  "user_localization_used": false,
  "safety_disclaimer": "Command 'come here' mapped to bounded forward movement. Note: distance is approximate and does NOT locate user position (Level 4 tracking unconfirmed).",
  "original_text": "DORURU, please come here"
}
```

### 3. `POST /api/v1/movement/command`
Transforms a validated `MovementIntent` into a sequenced `MovementCommandPacket`.
- **Precondition**: Device clock must be synchronized via `/handshake`.
- **Invariant**: Raw text payloads or intents with `autonomy_level > 1` are rejected.

**Response (200 OK):**
```json
{
  "sequence_id": 42,
  "direction": "FORWARD",
  "speed_pwm": 150,
  "duration_ms": 1000,
  "timestamp_ms": 14250,
  "ttl_ms": 3000,
  "autonomy_level": 1
}
```

### 4. `POST /api/v1/movement/handshake`
Synchronizes the backend sequence counter with the firmware's last accepted ID and calibrates the device timestamp reference. Supports sequence reset recovery on 32-bit counter rollover (`reset_sequence = true`).

---

## 5. Firmware C++ Hardware Abstraction

### Sensor Hardware Abstraction (`firmware/include/sensor_interface.h`):
```cpp
class ISensorProvider {
public:
    virtual bool isDistanceSensorAvailable() const = 0;
    virtual SensorStatus getDistanceSensorStatus() const = 0;
    virtual float getDistanceCm() const = 0;
    virtual bool isWheelEncoderAvailable() const = 0;
    virtual SensorStatus getEncoderStatus() const = 0;
    virtual int32_t getLeftEncoderTicks() const = 0;
    virtual int32_t getRightEncoderTicks() const = 0;
    virtual bool isObstacleAvoidanceSupported() const = 0;
    virtual bool isOdometrySupported() const = 0;
};
```
- In default configuration, `getSensorProvider()` returns `DisabledSensorProvider`, safely reporting `false` and `UNAVAILABLE` for all sensor queries.

### Independent Command Validator (`firmware/include/command_validator.h`):
```cpp
ValidationResult CommandValidator::validate(
    const InboundCommandPacket& packet,
    uint32_t current_device_time_ms,
    const motor::MotorController& controller,
    motor::MotionCommand& out_cmd
);
```
- Enforces defense-in-depth: Rejects stale packets (`age > ttl`), replay attacks (`seq <= last_seq`), out-of-bounds speed/duration, higher autonomy levels, and active emergency stop.

---

## 6. Verification Results

All unit and integration tests across both backend and firmware layers have passed:

1. **FastAPI & Pytest Suite (`backend/tests/test_movement_intent.py`)**:
   - `test_stop_phrases`: Immediate STOP priority for 12 variations.
   - `test_forward_phrases`: Bounded forward movement.
   - `test_bare_direction_words_rejected`: Ambiguous words rejected with 422.
   - `test_negated_movement_commands_rejected`: Negated commands safely rejected.
   - `test_come_here_disclaimer_and_no_localization`: Enforces approximate disclaimer & `user_localization_used=False`.
   - `test_go_back_disclaimer`: Approximate reverse movement disclaimer.
   - `test_rejection_of_unsupported_autonomy`: Follow-me, track-person, and SLAM requests rejected with HTTP 400.
   - `test_arbitrary_model_text_cannot_execute_directly`: Raw text to `/command` rejected with HTTP 422.
   - `test_higher_autonomy_levels_rejected_by_command_endpoint`: Autonomy levels 2, 3, 4 rejected with HTTP 400.
   - `test_gemini_interpreted_language_to_strict_structured_intent`: End-to-end intent-to-packet pipeline.
   - `test_disabled_sensor_provider_feature_flags`: Clean capabilities feature flags verification.
   - **Total Pytest Tests**: 28 / 28 Passed (100%).

2. **Native C++ Firmware Test Suites**:
   - `firmware/tests/test_command_validator.cpp`: 8 / 8 Passed (100%).
   - `firmware/tests/test_motor_controller.cpp`: 10 / 10 Passed (100%).

3. **Complete Python Unittest Suite (`tests/`)**: 68 / 68 Passed (100%).

