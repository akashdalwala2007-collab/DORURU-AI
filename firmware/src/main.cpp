/**
 * @file main.cpp
 * @brief DORURU Phase 5 Firmware Entry Point
 * Demonstrates OV3660 camera initialization, 8MB PSRAM runtime verification,
 * TFT state notifications, and on-demand vision transport.
 */

#include <Arduino.h>
#include "board_pins.h"
#include "camera_manager.h"
#include "vision_transport.h"
#include "display_interface.h"

// Display state change logger
void handle_display_state_change(display_state_t state, const char* message) {
    Serial.printf("[DORURU UI] State=%d | %s\n", (int)state, message ? message : "");
}

void setup() {
    // 1. Initialize USB CDC Serial (Native USB)
    Serial.begin(115200);
    uint32_t start_ms = millis();
    while (!Serial && (millis() - start_ms < 3000)) {
        delay(10);
    }
    Serial.println("\n==========================================");
    Serial.println("  DORURU ROBOT — PHASE 5 VISION FIRMWARE  ");
    Serial.println("  Target: Seeed Studio XIAO ESP32-S3 Sense");
    Serial.println("==========================================");

    // 2. Register TFT Display Callback
    display_register_state_callback(handle_display_state_change);
    display_set_state(DISPLAY_STATE_BOOTING, "Booting DORURU...");

    // 3. Inspect Runtime Octal PSRAM & Heap
    Serial.printf("[SYSTEM] Free Heap:  %u bytes (%u KB)\n", ESP.getFreeHeap(), ESP.getFreeHeap() / 1024);
    if (psramFound()) {
        Serial.printf("[SYSTEM] PSRAM Size: %u bytes (%u MB)\n", ESP.getPsramSize(), ESP.getPsramSize() / (1024 * 1024));
        Serial.printf("[SYSTEM] Free PSRAM: %u bytes (%u KB)\n", ESP.getFreePsram(), ESP.getFreePsram() / 1024);
    } else {
        Serial.println("[SYSTEM] WARNING: PSRAM NOT FOUND! Camera will operate in DRAM fallback mode.");
    }

    // 4. Initialize OV3660 Camera
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

    // 5. Configure Vision Transport (Local Backend Endpoint)
    vision_transport_config_t transport_cfg;
    strncpy(transport_cfg.backend_endpoint, "http://192.168.1.100:8000/api/v1/vision/upload", sizeof(transport_cfg.backend_endpoint));
    strncpy(transport_cfg.device_id, "DORURU-SENSE-01", sizeof(transport_cfg.device_id));
    strncpy(transport_cfg.device_token, "doruru_local_secret_token", sizeof(transport_cfg.device_token));
    transport_cfg.http_timeout_ms = 5000;
    vision_transport_init(&transport_cfg);

    Serial.println("[DORURU] Ready for On-Demand Vision requests. Send 'c' via Serial to capture.");
}

void loop() {
    // On-Demand Serial Trigger for Manual Verification
    if (Serial.available()) {
        char cmd = (char)Serial.read();
        if (cmd == 'c' || cmd == 'C') {
            Serial.println("\n[TRIGGER] Manual on-demand capture command received ('c')");
            
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
        } else if (cmd == 's' || cmd == 'S') {
            const camera_telemetry_t* telem = camera_manager_get_telemetry();
            Serial.printf("[STATUS] Captures: %u, Failures: %u, Free PSRAM: %u KB, Free Heap: %u KB\n",
                          telem->total_captures, telem->capture_failures,
                          telem->free_psram_bytes / 1024, telem->free_heap_bytes / 1024);
        }
    }

    delay(20);
}

