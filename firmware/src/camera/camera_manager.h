/**
 * @file camera_manager.h
 * @brief OV3660 Camera Capture and Memory Management for DORURU
 * @details Target: Seeed Studio XIAO ESP32-S3 Sense
 *
 * Requirements:
 * - Preserve OV3660 sensor definition; probe and verify PID (0x3660).
 * - Enforce 8MB Octal PSRAM runtime check before allocating buffers.
 * - Dynamic frame size & JPEG quality sizing based on measured memory.
 * - HYBRID vision mode: On-demand (single/controlled burst) and selected events only.
 * - No continuous streaming or continuous cloud uploading.
 * - Strict buffer release to prevent memory leaks.
 */

#pragma once

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include "board_pins.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Maximum allowable frames in a controlled burst (safety limit) */
#define MAX_BURST_FRAMES_LIMIT  3

typedef enum {
    CAMERA_OK = 0,
    CAMERA_ERR_NO_PSRAM_HEAP,
    CAMERA_ERR_DRIVER_INIT_FAILED,
    CAMERA_ERR_SENSOR_PROBE_FAILED,
    CAMERA_ERR_SENSOR_PID_MISMATCH,
    CAMERA_ERR_CAPTURE_FAILED,
    CAMERA_ERR_TIMEOUT,
    CAMERA_ERR_INVALID_PARAM,
    CAMERA_ERR_BUSY
} camera_init_status_t;

typedef enum {
    TRIGGER_ON_DEMAND_SINGLE = 0,   // User asked DORURU to look
    TRIGGER_ON_DEMAND_BURST,        // User requested small burst (<= 3 frames)
    TRIGGER_SELECTED_EVENT          // Explicit configured event (e.g. user arrival)
} camera_trigger_mode_t;

typedef struct {
    bool is_initialized;
    bool psram_detected;
    size_t total_psram_bytes;
    size_t free_psram_bytes;
    size_t free_heap_bytes;
    uint16_t detected_sensor_pid;
    bool is_ov3660_verified;
    uint16_t frame_width;
    uint16_t frame_height;
    int jpeg_quality;
    uint32_t total_captures;
    uint32_t capture_failures;
    char status_message[80];
} camera_telemetry_t;

typedef struct {
    uint8_t* data;
    size_t length;
    uint16_t width;
    uint16_t height;
    uint32_t timestamp_ms;
    camera_trigger_mode_t trigger_mode;
    void* _internal_fb_ref; // Pointer to underlying camera_fb_t
} doruru_frame_t;

/**
 * @brief Initialize the OV3660 camera on XIAO ESP32-S3 Sense.
 * Verifies 8MB OPI PSRAM, configures pins, initializes esp_camera driver,
 * and reads/verifies sensor PID (0x3660).
 */
camera_init_status_t camera_manager_init(void);

/**
 * @brief Capture a single frame in hybrid on-demand/event mode.
 * Automatically notifies TFT display.
 * Caller MUST call camera_manager_release_frame() after use.
 *
 * @param trigger The reason/mode for capture.
 * @return doruru_frame_t* Pointer to frame metadata and buffer, or NULL on failure.
 */
doruru_frame_t* camera_manager_capture_single(camera_trigger_mode_t trigger);

/**
 * @brief Capture a small controlled burst of frames (max 3 frames).
 * Enforces safety boundary: will reject count > MAX_BURST_FRAMES_LIMIT.
 * Caller MUST call camera_manager_release_frame() on each captured frame.
 *
 * @param trigger Trigger mode.
 * @param burst_count Number of frames (1 to 3).
 * @param interval_ms Delay between captures in milliseconds.
 * @param out_frames Array of doruru_frame_t pointers (allocated by caller with burst_count slots).
 * @return int Number of frames successfully captured.
 */
int camera_manager_capture_burst(camera_trigger_mode_t trigger,
                                uint8_t burst_count,
                                uint16_t interval_ms,
                                doruru_frame_t** out_frames);

/**
 * @brief Release a captured frame buffer back to the camera driver immediately.
 * Protects against memory leaks and PSRAM exhaustion.
 */
bool camera_manager_release_frame(doruru_frame_t* frame);

/**
 * @brief Get read-only copy of camera manager telemetry and hardware status.
 */
const camera_telemetry_t* camera_manager_get_telemetry(void);

/**
 * @brief De-initialize camera peripheral and free all resources.
 */
bool camera_manager_deinit(void);

#ifdef __cplusplus
}
#endif

