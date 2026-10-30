#ifdef ARDUINO
#include <Arduino.h>
#include "board_pins.h"
#include "esp32_gpio_driver.h"
#include "motor_controller.h"
#include "sensor_interface.h"

// Hardware instances
static doruru::hal::Esp32GpioDriver g_gpioDriver;
static doruru::motor::MotorController g_motorController(
    g_gpioDriver, 
    doruru::sensors::getSensorProvider()
);

void printTelemetry() {
    auto status = g_motorController.getStatus();
    const char* dirStr = "UNKNOWN";
    switch (status.active_direction) {
        case doruru::motor::Direction::STOP:        dirStr = "STOP"; break;
        case doruru::motor::Direction::FORWARD:     dirStr = "FORWARD"; break;
        case doruru::motor::Direction::REVERSE:     dirStr = "REVERSE"; break;
        case doruru::motor::Direction::PIVOT_LEFT:  dirStr = "PIVOT_LEFT"; break;
        case doruru::motor::Direction::PIVOT_RIGHT: dirStr = "PIVOT_RIGHT"; break;
    }

    Serial.printf("[DORURU MOTOR] State: %s | Target PWM: %u | Current PWM: %u | Remaining: %lums | E-Stop: %s | Timeout: %s | HeartbeatLost: %s\n",
                  dirStr,
                  status.target_speed_pwm,
                  status.current_ramped_pwm,
                  status.remaining_duration_ms,
                  status.is_emergency_stopped ? "YES" : "NO",
                  status.is_timed_out ? "YES" : "NO",
                  status.is_heartbeat_lost ? "YES" : "NO");
}

void printHelp() {
    Serial.println("\n=== DORURU MOTOR SAFETY BENCH CONSOLE ===");
    Serial.println("  F <pwm> <ms> : Forward (e.g. F 150 1000)");
    Serial.println("  B <pwm> <ms> : Reverse (e.g. B 150 1000)");
    Serial.println("  L <pwm> <ms> : Pivot Left (e.g. L 140 500)");
    Serial.println("  R <pwm> <ms> : Pivot Right (e.g. R 140 500)");
    Serial.println("  S            : Stop");
    Serial.println("  E            : Emergency Stop (Locks motors)");
    Serial.println("  C            : Clear Emergency Stop");
    Serial.println("  H            : Feed Heartbeat Watchdog");
    Serial.println("  T            : Print Telemetry");
    Serial.println("  ?            : Print Help");
    Serial.println("SAFETY NOTICE: ELEVATE WHEELS OFF BENCH BEFORE COMMANDING MOTION!\n");
}

void setup() {
    // Initialize Native USB CDC Serial
    // (Hardware UART0 is strictly disabled to protect D6/GPIO43 LRC and D7/GPIO44 DC)
    Serial.begin(115200);
    delay(1000);

    Serial.println("==================================================");
    Serial.println("  DORURU ROBOT — MOTOR SAFETY FOUNDATION BOOT     ");
    Serial.println("==================================================");

    // 1. Runtime PSRAM Verification
    if (psramFound()) {
        Serial.printf("[PSRAM] 8MB OPI PSRAM Detected! Total: %u KB, Free: %u KB\n",
                      ESP.getPsramSize() / 1024, ESP.getFreePsram() / 1024);
    } else {
        Serial.println("[PSRAM] WARNING: PSRAM not detected. Check build flags.");
    }

    // 2. Sensor Verification (Odometry & Obstacle Sensors)
    auto& sensors = doruru::sensors::getSensorProvider();
    Serial.printf("[SENSORS] Obstacle Avoidance Supported: %s\n", 
                  sensors.isObstacleAvoidanceSupported() ? "YES" : "NO (Disabled / Unconfirmed)");
    Serial.printf("[SENSORS] Wheel Odometry Supported: %s\n", 
                  sensors.isOdometrySupported() ? "YES" : "NO (Disabled / Unconfirmed)");

    // 3. Initialize Motor Controller (Forces pins LOW and STOP state)
    g_motorController.init();
    Serial.println("[MOTOR] MX1508 Pins initialized: IN1=D3(4), IN2=D2(3), IN3=D1(2), IN4=D0(1)");
    Serial.println("[MOTOR] Startup Default: STOP (all pins LOW, PWM = 0)");
    Serial.println("[SAFETY] Hard Watchdog Timeout: 3000ms max | Heartbeat: 1500ms max");

    printHelp();
}

void processCommandLine(const char* line) {
    while (*line == ' ' || *line == '\t') {
        line++;
    }
    if (*line == '\0') {
        return;
    }

    char cmdChar = line[0];
    switch (cmdChar) {
        case 'S':
        case 's':
            g_motorController.stop();
            Serial.println("[CMD] STOP executed.");
            break;

        case 'E':
        case 'e':
            g_motorController.emergencyStop();
            Serial.println("[CMD] !!! EMERGENCY STOP ENGAGED !!!");
            break;

        case 'C':
        case 'c':
            g_motorController.clearEmergencyStop();
            Serial.println("[CMD] Emergency Stop CLEARED.");
            break;

        case 'H':
        case 'h':
            g_motorController.feedHeartbeat();
            Serial.println("[CMD] Heartbeat watchdog fed.");
            break;

        case 'T':
        case 't':
            printTelemetry();
            break;

        case '?':
            printHelp();
            break;

        case 'F':
        case 'f':
        case 'B':
        case 'b':
        case 'L':
        case 'l':
        case 'R':
        case 'r': {
            int speed = 0;
            int duration = 0;
            int offset = 0;
            int matched = sscanf(line + 1, "%d %d%n", &speed, &duration, &offset);
            if (matched != 2 || offset == 0) {
                Serial.println("[CMD] Motion REJECTED: missing or invalid speed and duration arguments (format: <CMD> <speed> <duration_ms>).");
                return;
            }

            // Ensure any remaining text on the line contains ONLY whitespace
            const char* remainder = line + 1 + offset;
            while (*remainder == ' ' || *remainder == '\t') {
                remainder++;
            }
            if (*remainder != '\0') {
                Serial.printf("[CMD] Motion REJECTED: unexpected trailing characters '%s'.\n", remainder);
                return;
            }

            // Validate speed against integer bounds before narrowing cast to avoid wrap-around
            if (speed < static_cast<int>(doruru::motor::MotorController::MIN_SPEED_PWM) ||
                speed > static_cast<int>(doruru::motor::MotorController::MAX_SPEED_PWM)) {
                Serial.printf("[CMD] Motion REJECTED: speed %d out of bounds [%u, %u]\n",
                              speed,
                              doruru::motor::MotorController::MIN_SPEED_PWM,
                              doruru::motor::MotorController::MAX_SPEED_PWM);
                return;
            }

            // Validate duration against integer bounds before narrowing cast to avoid wrap-around
            if (duration < static_cast<int>(doruru::motor::MotorController::MIN_DURATION_MS) ||
                duration > static_cast<int>(doruru::motor::MotorController::MAX_DURATION_MS)) {
                Serial.printf("[CMD] Motion REJECTED: duration %d out of bounds [%u, %u ms]\n",
                              duration,
                              doruru::motor::MotorController::MIN_DURATION_MS,
                              doruru::motor::MotorController::MAX_DURATION_MS);
                return;
            }

            doruru::motor::Direction dir = doruru::motor::Direction::STOP;
            if (cmdChar == 'F' || cmdChar == 'f') dir = doruru::motor::Direction::FORWARD;
            else if (cmdChar == 'B' || cmdChar == 'b') dir = doruru::motor::Direction::REVERSE;
            else if (cmdChar == 'L' || cmdChar == 'l') dir = doruru::motor::Direction::PIVOT_LEFT;
            else if (cmdChar == 'R' || cmdChar == 'r') dir = doruru::motor::Direction::PIVOT_RIGHT;

            doruru::motor::MotionCommand cmd{
                dir,
                static_cast<uint8_t>(speed),
                static_cast<uint32_t>(duration)
            };
            auto res = g_motorController.executeCommand(cmd);

            if (res == doruru::motor::CommandResult::ACCEPTED) {
                Serial.printf("[CMD] Motion ACCEPTED: Dir=%c Speed=%d Duration=%dms\n", 
                              cmdChar, speed, duration);
            } else {
                Serial.printf("[CMD] Motion REJECTED (Error Code: %u)\n", static_cast<uint8_t>(res));
            }
            break;
        }

        default:
            Serial.println("[CMD] Unknown command. Press '?' for help.");
            break;
    }
}

void loop() {
    // 1. Update motor safety state machine (evaluates timeouts & ramps)
    g_motorController.update();

    // 2. Non-blocking USB CDC serial input processing
    static char s_lineBuffer[64];
    static size_t s_lineIndex = 0;
    static bool s_discardRemainingLine = false;

    while (Serial.available()) {
        char c = static_cast<char>(Serial.read());

        // Line terminators: handle end of line or reset discard state
        if (c == '\n' || c == '\r') {
            if (s_discardRemainingLine) {
                // Line was marked discarded (e.g. due to E-stop or buffer overflow)
                s_discardRemainingLine = false;
                s_lineIndex = 0;
            } else if (s_lineIndex > 0) {
                s_lineBuffer[s_lineIndex] = '\0';
                processCommandLine(s_lineBuffer);
                s_lineIndex = 0;
            }
            continue;
        }

        // Immediately handle Emergency Stop on E or e even during overflow recovery
        if (c == 'E' || c == 'e') {
            g_motorController.emergencyStop();
            Serial.println("[CMD] !!! EMERGENCY STOP ENGAGED !!!");
            s_lineIndex = 0;
            s_discardRemainingLine = true;
            continue;
        }

        // If currently discarding bytes until line terminator, ignore byte
        if (s_discardRemainingLine) {
            continue;
        }

        // Append to line buffer if space available
        if (s_lineIndex < sizeof(s_lineBuffer) - 1) {
            s_lineBuffer[s_lineIndex++] = c;
        } else {
            // Buffer overflow protection: mark line invalid and discard all remaining bytes
            Serial.println("[CMD] Line buffer overflow: command discarded.");
            s_lineIndex = 0;
            s_discardRemainingLine = true;
        }
    }

    // Small loop cadence
    delay(5);
}
#endif

