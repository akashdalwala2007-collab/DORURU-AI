/**
 * @file main.cpp
 * @brief DORURU Robot Unified Firmware Entry Point
 * 
 * Unifies:
 * - Phase 3: MX1508 motor controller with ramped PWM, watchdog timeout & interactive bench console.
 * - Phase 5: OV3660 camera initialization, 8MB Octal PSRAM runtime verification, and on-demand vision transport.
 * - Phase 13: TFT display interface state notifications and motor safety integration.
 * - Target: Seeed Studio XIAO ESP32-S3 Sense
 */

#ifdef ARDUINO
#include <Arduino.h>
#include "board_pins.h"
#include "esp32_gpio_driver.h"
#include "motor_controller.h"
#include "sensor_interface.h"
#include "camera_manager.h"
#include "vision_transport.h"
#include "display_interface.h"

// Hardware instances for motor control
static doruru::hal::Esp32GpioDriver g_gpioDriver;
static doruru::motor::MotorController g_motorController(
    g_gpioDriver, 
    doruru::sensors::getSensorProvider()
);

// Display state change logger callback
void handle_display_state_change(display_state_t state, const char* message) {
    Serial.printf("[DORURU UI] State=%d | %s\n", (int)state, message ? message : "");
}

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

void printCameraTelemetry() {
    const camera_telemetry_t* telem = camera_manager_get_telemetry();
    Serial.printf("[CAMERA STATUS] Captures: %u, Failures: %u, Free PSRAM: %u KB, Free Heap: %u KB\n",
                  telem->total_captures, telem->capture_failures,
                  telem->free_psram_bytes / 1024, telem->free_heap_bytes / 1024);
}

void triggerVisionCapture() {
    Serial.println("\n[TRIGGER] Manual on-demand capture command received ('V')");
    char response_buf[256] = {0};
    vision_transport_status_t res = vision_transport_capture_and_send(
        "Describe what is in front of the robot",
        response_buf,
        sizeof(response_buf)
    );

    if (res == TRANSPORT_SUCCESS) {
        Serial.printf("[TRIGGER] Capture & Transport SUCCESS! Response: %s\n", response_buf);
    } else if (res == TRANSPORT_ERR_WIFI_DISCONNECTED) {
        Serial.println("[TRIGGER] Capture & Transport aborted: Wi-Fi Disconnected (graceful fallback).");
    } else {
        Serial.printf("[TRIGGER] Capture & Transport failed with code %d\n", (int)res);
    }
}

void printHelp() {
    Serial.println("\n=== DORURU ROBOT BENCH & SAFETY CONSOLE ===");
    Serial.println("  F <pwm> <ms> : Forward (e.g. F 150 1000)");
    Serial.println("  B <pwm> <ms> : Reverse (e.g. B 150 1000)");
    Serial.println("  L <pwm> <ms> : Pivot Left (e.g. L 140 500)");
    Serial.println("  R <pwm> <ms> : Pivot Right (e.g. R 140 500)");
    Serial.println("  S            : Stop Motors");
    Serial.println("  E            : Emergency Stop (Locks motors)");
    Serial.println("  C            : Clear Emergency Stop");
    Serial.println("  H            : Feed Heartbeat Watchdog");
    Serial.println("  T            : Print Motor Telemetry");
    Serial.println("  D            : Toggle Display Demo Mode (Cycles all screens without motor motion)");
    Serial.println("  V            : Trigger On-Demand Vision Capture & Send");
    Serial.println("  K            : Print Camera Telemetry");
    Serial.println("  ?            : Print Help");
    Serial.println("SAFETY NOTICE: ELEVATE WHEELS OFF BENCH BEFORE COMMANDING MOTION!\n");
}

void setup() {
    // 1. Initialize USB CDC Serial (Native USB)
    // Hardware UART0 is strictly disabled to protect D6/GPIO43 LRC and D7/GPIO44 DC
    Serial.begin(115200);
    uint32_t start_ms = millis();
    while (!Serial && (millis() - start_ms < 2000)) {
        delay(10);
    }

    Serial.println("\n==================================================");
    Serial.println("  DORURU ROBOT — UNIFIED FIRMWARE & MOTOR BENCH   ");
    Serial.println("  Target: Seeed Studio XIAO ESP32-S3 Sense        ");
    Serial.println("==================================================");

    // 2. Register TFT Display Callback & Initialize Display Hardware
    display_register_state_callback(handle_display_state_change);
    display_init();
    display_set_state(DISPLAY_STATE_BOOTING, "Booting DORURU...");

    // 3. Inspect Runtime Octal PSRAM & Heap
    Serial.printf("[SYSTEM] Free Heap:  %u bytes (%u KB)\n", ESP.getFreeHeap(), ESP.getFreeHeap() / 1024);
    if (psramFound()) {
        Serial.printf("[SYSTEM] PSRAM Size: %u bytes (%u MB)\n", ESP.getPsramSize(), ESP.getPsramSize() / (1024 * 1024));
        Serial.printf("[SYSTEM] Free PSRAM: %u bytes (%u KB)\n", ESP.getFreePsram(), ESP.getFreePsram() / 1024);
    } else {
        Serial.println("[SYSTEM] WARNING: PSRAM NOT FOUND! Camera will operate in DRAM fallback mode.");
    }

    // 4. Sensor Verification (Odometry & Obstacle Sensors)
    auto& sensors = doruru::sensors::getSensorProvider();
    Serial.printf("[SENSORS] Obstacle Avoidance Supported: %s\n", 
                  sensors.isObstacleAvoidanceSupported() ? "YES" : "NO (Disabled / Unconfirmed)");
    Serial.printf("[SENSORS] Wheel Odometry Supported: %s\n", 
                  sensors.isOdometrySupported() ? "YES" : "NO (Disabled / Unconfirmed)");

    // 5. Initialize Motor Controller (Forces pins LOW and STOP state)
    g_motorController.init();
    Serial.println("[MOTOR] MX1508 Pins initialized: IN1=D3(4), IN2=D2(3), IN3=D1(2), IN4=D0(1)");
    Serial.println("[MOTOR] Startup Default: STOP (all pins LOW, PWM = 0)");
    Serial.println("[SAFETY] Hard Watchdog Timeout: 3000ms max | Heartbeat: 1500ms max");

    // 6. Initialize OV3660 Camera
    Serial.println("[CAMERA] Initializing OV3660 Camera module...");
    camera_init_status_t cam_status = camera_manager_init();
    if (cam_status == CAMERA_OK) {
        const camera_telemetry_t* telem = camera_manager_get_telemetry();
        Serial.println("[CAMERA] Camera initialized successfully!");
        Serial.printf("[CAMERA] Sensor PID: 0x%04X (%s)\n",
                      telem->detected_sensor_pid,
                      telem->is_ov3660_verified ? "OV3660 Verified" : "PID Mismatch / Other Sensor");
        Serial.printf("[CAMERA] Configured Frame Size: %ux%u, JPEG Quality: %d\n",
                      telem->frame_width, telem->frame_height, telem->jpeg_quality);
    } else {
        Serial.printf("[CAMERA] Camera initialization FAILED (error code %d)\n", (int)cam_status);
    }

    // 7. Configure Vision Transport (Local Backend Endpoint)
    vision_transport_config_t transport_cfg;
    strncpy(transport_cfg.backend_endpoint, "http://192.168.1.100:8000/api/v1/vision/upload", sizeof(transport_cfg.backend_endpoint));
    strncpy(transport_cfg.device_id, "DORURU-SENSE-01", sizeof(transport_cfg.device_id));
    strncpy(transport_cfg.device_token, "doruru_local_secret_token", sizeof(transport_cfg.device_token));
    transport_cfg.http_timeout_ms = 5000;
    vision_transport_init(&transport_cfg);

    // 8. Ready State
    display_set_state(DISPLAY_STATE_IDLE_READY, "DORURU Ready");
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

        case 'D':
        case 'd': {
            bool now_active = !display_is_demo_mode();
            display_set_demo_mode(now_active, 1500);
            Serial.printf("[CMD] Display Demo Mode: %s (cycles all screens without motor motion)\n",
                          now_active ? "ENABLED" : "DISABLED");
            break;
        }

        case 'V':
        case 'v':
            triggerVisionCapture();
            break;

        case 'K':
        case 'k':
            printCameraTelemetry();
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

    // 2. Non-blocking display animation and demo tick
    display_update();

    // 3. Non-blocking USB CDC serial input processing
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
