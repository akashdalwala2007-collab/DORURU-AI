---
phase: 3
plan: 1
wave: 1
gap_closure: false
---

# Plan 3.1: Motor Control and Local Safety Foundation

## Objective
Implement controlled, bounded motor operation for DORURU using the confirmed MX1508 H-bridge wiring (`IN1=D3/GPIO4`, `IN2=D2/GPIO3`, `IN3=D1/GPIO2`, `IN4=D0/GPIO1`). Enforce strict local embedded safety: startup default STOP, hard command duration limits, non-blocking automatic stop watchdog timeouts, highest-priority emergency stop, heartbeat communication-loss safety, software PWM current-spike ramp limiting, input validation, and safe disabled sensor abstractions.

## Context
Load these files for context:
- `.gsd/SPEC.md`
- `.gsd/ARCHITECTURE.md`
- `.gsd/DECISIONS.md`
- `doruru_phase.txt`

## Tasks

<task type="auto">
  <name>Task 1: Define Central Pin Map, Firmware Architecture, and Disabled Sensor Interfaces</name>
  <files>
    firmware/include/board_pins.h
    firmware/include/sensor_interface.h
    firmware/src/sensor_interface.cpp
    firmware/platformio.ini
  </files>
  <action>
    Create central pin configuration preserving confirmed wiring:
    - Motor pins: IN1=GPIO4 (D3), IN2=GPIO3 (D2), IN3=GPIO2 (D1), IN4=GPIO1 (D0).
    - Sense reserved pins: GPIO41/GPIO42 (PDM mic), camera pins.
    - Custom SPI & Audio pins reserved: GPIO5/6/43 (MAX98357A), GPIO7/8/9/44 (ILI9341).
    - Create ISensorProvider / SensorInterface with explicit DISABLED / UNAVAILABLE status for wheel encoders and distance sensors.
    - Create platformio.ini configured for Seeed XIAO ESP32-S3 Sense with native USB CDC and 8MB OPI PSRAM settings.
    AVOID: Altering any pin assignment or inventing sensor pins.
    USE: Explicit constants and compile-time pin validation.
  </action>
  <verify>
    Verify files exist and headers parse cleanly without circular dependencies.
  </verify>
  <done>
    Pin definitions match confirmed wiring and sensor interface returns explicit disabled states.
  </done>
</task>

<task type="auto">
  <name>Task 2: Implement Motor Controller with Local Watchdog, PWM Ramp, and Emergency Stop</name>
  <files>
    firmware/include/motor_controller.h
    firmware/src/motor_controller.cpp
    firmware/src/main.cpp
    firmware/README.md
  </files>
  <action>
    Implement MotorController class providing:
    - Direction enums: STOP, FORWARD, REVERSE, PIVOT_LEFT, PIVOT_RIGHT.
    - Motion bounds: min PWM, max PWM, max duration (3000ms), default duration (1000ms).
    - Methods: init(), set_motion(), stop(), emergency_stop(), clear_emergency_stop(), update(), feed_heartbeat().
    - Non-blocking update() loop evaluating command duration timeout and heartbeat loss.
    - Software ramp limiter to mitigate inductive current inrush spikes.
    - Input validation rejecting unknown commands, negative durations, or out-of-bound speeds.
    - Electrical safety notes emphasizing independent motor power supply and common ground.
    AVOID: Blocking delays (delay()), direct GPIO exposure to remote callers, or automatic motor movements.
    USE: Non-blocking millis() time delta checks and deterministic state transitions.
  </action>
  <verify>
    Code review and structural check of public API and safety state machine.
  </verify>
  <done>
    Full motor controller implementation with all 11 required safety and control features.
  </done>
</task>

<task type="auto">
  <name>Task 3: Implement and Execute Native Test Suite for Motor Safety and Logic</name>
  <files>
    firmware/tests/test_motor_controller.cpp
  </files>
  <action>
    Create host-executable native test suite with hardware mock:
    - Test 1: Startup default state is STOP and all pins driven LOW.
    - Test 2: Input validation accepts valid commands and rejects invalid direction/speed/duration.
    - Test 3: Duration timeout automatically transitions active motion to STOP when duration expires.
    - Test 4: Heartbeat watchdog stops motors if communication is lost.
    - Test 5: Emergency stop immediately halts motors and locks out new commands until cleared.
    - Test 6: Slew rate / PWM ramp limiter smoothly steps duty cycle rather than instant step.
    - Test 7: Sensor interface confirms distance sensors and wheel encoders are safely disabled.
    Compile with g++ and run test suite, capturing full output.
  </action>
  <verify>
    g++ -std=c++11 -Wall -Wextra firmware/tests/test_motor_controller.cpp firmware/src/motor_controller.cpp firmware/src/sensor_interface.cpp -I firmware/include -I firmware/tests -o firmware/tests/test_motor_controller.exe && ./firmware/tests/test_motor_controller.exe
  </verify>
  <done>
    All unit test cases pass with 100% success and captured terminal proof.
  </done>
</task>

## Must-Haves
After all tasks complete, verify:
- [ ] Confirmed wiring preserved: IN1=GPIO4, IN2=GPIO3, IN3=GPIO2, IN4=GPIO1
- [ ] Startup default is strictly STOP with pins LOW
- [ ] Emergency stop has highest priority and requires explicit clear
- [ ] Automatic duration timeout and heartbeat loss safety verified
- [ ] Distance sensors and wheel encoders strictly reported as disabled
- [ ] Host mock test suite compiles and runs with 100% pass rate
- [ ] No git commit or push performed

