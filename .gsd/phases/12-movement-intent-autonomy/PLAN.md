---
phase: 12
plan: 1
wave: 1
gap_closure: false
---

# Plan 12.1: Movement Command Interpretation and Autonomy Readiness

## Objective
Implement the safe movement-intent layer for DORURU. Support strictly bounded commands (`STOP`, `FORWARD`, `REVERSE`, `TURN_LEFT`, `TURN_RIGHT`), map natural-language phrases ("come here", "go back") with mandatory disclaimers and approximate time bounds, and strictly enforce the 4-level autonomy gating model with Level 1 active and Levels 2–4 disabled. Implement dual-tier validation (backend Pydantic validation + ESP32 C++ independent validation) to guarantee that movement commands never execute directly from arbitrary model text or stale/replayed packets.

## Context
- `.gsd/SPEC.md`
- `.gsd/ARCHITECTURE.md`
- `.gsd/DECISIONS.md`
- `doruru_phase.txt`

## Tasks

<task type="auto">
  <name>Task 1: Implement Backend Movement Intent Schemas, Intent Parser, and Autonomy Router</name>
  <files>
    backend/app/schemas/movement.py
    backend/app/services/movement_intent_parser.py
    backend/app/routers/movement.py
    backend/app/main.py
  </files>
  <action>
    - Define Pydantic schemas for MovementDirection, AutonomyLevel (Level 1 Active, Levels 2-4 Disabled), MovementIntent, MovementCommandPacket (with sequence ID and TTL).
    - Implement MovementIntentParser:
      - Translate "stop", "halt", "freeze", "emergency stop" -> STOP.
      - Translate "forward", "drive forward", "ahead", "straight" -> FORWARD.
      - Translate "come here", "come closer" -> FORWARD with approximate timed bounds and explicit disclaimer that user localization is disabled.
      - Translate "go back", "reverse", "step back" -> REVERSE with approximate timed disclaimer.
      - Translate "turn left", "pivot left" -> TURN_LEFT.
      - Translate "turn right", "pivot right" -> TURN_RIGHT.
      - Explicitly reject autonomous roaming ("roam", "patrol", "explore", "go to room X") and user-following ("follow me") as disabled autonomy features.
      - Enforce speed (60-220 PWM) and duration (50-3000ms) bounds.
    - Implement FastAPI router providing /api/v1/movement/intent, /api/v1/movement/command, and /api/v1/movement/capabilities.
    - Create minimal FastAPI application entrypoint in backend/app/main.py.
  </action>
  <verify>
    Import schemas and router, ensure clean Pydantic model validation.
  </verify>
  <done>
    Movement schemas, parser, and router fully functional with Level 1 autonomy lock.
  </done>
</task>

<task type="auto">
  <name>Task 2: Implement Firmware Independent Command Validator</name>
  <files>
    firmware/include/command_validator.h
    firmware/src/command_validator.cpp
  </files>
  <action>
    - Implement C++ CommandValidator for the ESP32 firmware:
      - Validates command envelope independently of the backend.
      - Strictly verifies sequence number monotonicity to prevent replay attacks.
      - Enforces packet freshness (rejects stale packets older than 1000ms TTL).
      - Re-verifies speed bounds (MIN_SPEED_PWM=60 to MAX_SPEED_PWM=220) and duration bounds (50ms to 3000ms).
      - Re-verifies autonomy level: rejects commands requesting unconfirmed Level > 1.
  </action>
  <verify>
    Verify C++ headers and implementation compile cleanly without syntax errors.
  </verify>
  <done>
    ESP32 independent validation layer prevents stale/replayed or unvalidated commands from reaching MotorController.
  </done>
</task>

<task type="auto">
  <name>Task 3: Implement and Execute Automated Test Suites (Pytest & Native C++)</name>
  <files>
    backend/tests/test_movement_intent.py
    firmware/tests/test_command_validator.cpp
  </files>
  <action>
    - Create Pytest test suite covering:
      - Intent parsing for standard directions and natural-language phrases ("come here", "go back").
      - Rejection of autonomous requests ("follow me", "explore", "patrol").
      - Parameter validation (speed and duration bounds clamping/rejection).
      - Capabilities endpoint verifying Level 1 Active and Levels 2-4 Disabled.
    - Create Native C++ test suite covering:
      - Valid packet acceptance.
      - Replay attack rejection (stale/duplicate sequence numbers).
      - Stale packet timestamp expiration.
      - Out-of-bounds speed/duration rejection.
    - Execute both test suites and capture full output.
  </action>
  <verify>
    Run py -3.14 -m pytest backend/tests/test_movement_intent.py -v
    g++ -std=c++11 -Wall -Wextra firmware/tests/test_command_validator.cpp firmware/src/command_validator.cpp firmware/src/motor_controller.cpp firmware/src/sensor_interface.cpp -I firmware/include -I firmware/tests -o firmware/tests/test_command_validator.exe && .\firmware\tests\test_command_validator.exe
  </verify>
  <done>
    100% of tests pass across both backend and firmware validation layers.
  </done>
</task>

## Must-Haves
- [ ] Strict bounded commands: STOP, FORWARD, REVERSE, TURN_LEFT, TURN_RIGHT
- [ ] "Come here" and "go back" mapped to bounded motions with explicit approximate/no-localization disclaimers
- [ ] Autonomy Levels 2-4 (obstacle avoidance, odometry, user-following) strictly disabled
- [ ] Dual-tier validation: Backend Pydantic validation + ESP32 independent validation
- [ ] Stale commands and replay attacks rejected
- [ ] Both pytest and native C++ unit tests passing with empirical proof
- [ ] No git commit or push performed

