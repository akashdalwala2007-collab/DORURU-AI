/**
 * @file camera_manager.cpp
 * @brief Implementation of OV3660 Camera Capture and Management.
 */

#include "camera_manager.h"
#include "display_interface.h"
#include <string.h>
#include <stdio.h>

#if defined(ESP32) || defined(ARDUINO)
#include <Arduino.h>
#include "esp_camera.h"
#include "esp_system.h"
#include "esp_heap_caps.h"
#else
// Host compilation mock stubs for verification and unit tests
#include <stdlib.h>
#include <time.h>

typedef int esp_err_t;
typedef int ledc_channel_t;
typedef int ledc_timer_t;
#define ESP_OK 0

typedef enum {
    PIXFORMAT_RGB565,
    PIXFORMAT_YUV422,
    PIXFORMAT_GRAYSCALE,
    PIXFORMAT_JPEG,
    PIXFORMAT_RGB888,
    PIXFORMAT_RAW,
} pixformat_t;

typedef enum {
    FRAMESIZE_QQVGA,    // 160x120
    FRAMESIZE_QVGA,     // 320x240
    FRAMESIZE_VGA,      // 640x480
    FRAMESIZE_SVGA,     // 800x600
    FRAMESIZE_XGA,      // 1024x768
} framesize_t;

typedef enum {
    CAMERA_FB_IN_DRAM,
    CAMERA_FB_IN_PSRAM
} camera_fb_location_t;

typedef enum {
    CAMERA_GRAB_WHEN_EMPTY,
    CAMERA_GRAB_LATEST
} camera_grab_mode_t;

typedef struct {
    int pin_pwdn;
    int pin_reset;
    int pin_xclk;
    int pin_sccb_sda;
    int pin_sccb_scl;
    int pin_d7;
    int pin_d6;
    int pin_d5;
    int pin_d4;
    int pin_d3;
    int pin_d2;
    int pin_d1;
    int pin_d0;
    int pin_vsync;
    int pin_href;
    int pin_pclk;
    int xclk_freq_hz;
    int ledc_timer;
    int ledc_channel;
    pixformat_t pixel_format;
    framesize_t frame_size;
    int jpeg_quality;
    size_t fb_count;
    camera_fb_location_t fb_location;
    camera_grab_mode_t grab_mode;
} camera_config_t;

typedef struct {
    uint8_t *buf;
    size_t len;
    size_t width;
    size_t height;
    pixformat_t format;
    struct timeval timestamp;
} camera_fb_t;

typedef struct {
    uint16_t PID;
} sensor_id_t;

typedef struct _sensor {
    sensor_id_t id;
    int (*set_vflip)(struct _sensor *s, int enable);
    int (*set_hmirror)(struct _sensor *s, int enable);
    int (*set_brightness)(struct _sensor *s, int level);
    int (*set_saturation)(struct _sensor *s, int level);
} sensor_t;

static int mock_sensor_set_noop(sensor_t *s, int val) { (void)s; (void)val; return 0; }
static sensor_t s_mock_sensor = {
    .id = { .PID = OV3660_CHIP_PID },
    .set_vflip = mock_sensor_set_noop,
    .set_hmirror = mock_sensor_set_noop,
    .set_brightness = mock_sensor_set_noop,
    .set_saturation = mock_sensor_set_noop
};

static bool s_mock_psram_found = true;
static size_t s_mock_free_psram = 8 * 1024 * 1024;
static size_t s_mock_free_heap = 320 * 1024;

static esp_err_t esp_camera_init(const camera_config_t *config) { (void)config; return 0; }
static esp_err_t esp_camera_deinit(void) { return 0; }
static sensor_t *esp_camera_sensor_get(void) { return &s_mock_sensor; }

static camera_fb_t *esp_camera_fb_get(void) {
    camera_fb_t *fb = (camera_fb_t*)malloc(sizeof(camera_fb_t));
    if (!fb) return NULL;
    fb->len = 1024;
    fb->buf = (uint8_t*)malloc(fb->len);
    if (!fb->buf) { free(fb); return NULL; }
    // JPEG SOI marker (0xFF, 0xD8) and EOI marker (0xFF, 0xD9)
    fb->buf[0] = 0xFF; fb->buf[1] = 0xD8;
    memset(fb->buf + 2, 0xAA, fb->len - 4);
    fb->buf[fb->len - 2] = 0xFF; fb->buf[fb->len - 1] = 0xD9;
    fb->width = 640;
    fb->height = 480;
    fb->format = PIXFORMAT_JPEG;
    return fb;
}

static void esp_camera_fb_return(camera_fb_t *fb) {
    if (fb) {
        if (fb->buf) free(fb->buf);
        free(fb);
    }
}
#endif

static camera_telemetry_t s_telemetry = {0};
static doruru_frame_t s_active_frames[MAX_BURST_FRAMES_LIMIT] = {0};
static bool s_frame_slot_in_use[MAX_BURST_FRAMES_LIMIT] = {false};

static void log_info(const char* msg) {
    printf("[OV3660] %s\n", msg);
}

camera_init_status_t camera_manager_init(void) {
    memset(&s_telemetry, 0, sizeof(camera_telemetry_t));

    // 1. Measure Free PSRAM and Heap
#if defined(ESP32) || defined(ARDUINO)
    s_telemetry.psram_detected = psramFound();
    s_telemetry.total_psram_bytes = ESP.getPsramSize();
    s_telemetry.free_psram_bytes = ESP.getFreePsram();
    s_telemetry.free_heap_bytes = ESP.getFreeHeap();
#else
    s_telemetry.psram_detected = s_mock_psram_found;
    s_telemetry.total_psram_bytes = 8 * 1024 * 1024;
    s_telemetry.free_psram_bytes = s_mock_free_psram;
    s_telemetry.free_heap_bytes = s_mock_free_heap;
#endif

    snprintf(s_telemetry.status_message, sizeof(s_telemetry.status_message),
             "PSRAM=%s (%zu KB free), Heap=%zu KB",
             s_telemetry.psram_detected ? "FOUND" : "NOT FOUND",
             s_telemetry.free_psram_bytes / 1024,
             s_telemetry.free_heap_bytes / 1024);
    log_info(s_telemetry.status_message);

    // 2. Configure esp_camera driver with Seeed XIAO ESP32-S3 Sense Camera Pinout
    camera_config_t config;
    config.ledc_channel = (ledc_channel_t)0;
    config.ledc_timer = (ledc_timer_t)0;
    config.pin_d0 = CAMERA_PIN_D0;
    config.pin_d1 = CAMERA_PIN_D1;
    config.pin_d2 = CAMERA_PIN_D2;
    config.pin_d3 = CAMERA_PIN_D3;
    config.pin_d4 = CAMERA_PIN_D4;
    config.pin_d5 = CAMERA_PIN_D5;
    config.pin_d6 = CAMERA_PIN_D6;
    config.pin_d7 = CAMERA_PIN_D7;
    config.pin_xclk = CAMERA_PIN_XCLK;
    config.pin_pclk = CAMERA_PIN_PCLK;
    config.pin_vsync = CAMERA_PIN_VSYNC;
    config.pin_href = CAMERA_PIN_HREF;
    config.pin_sccb_sda = CAMERA_PIN_SIOD;
    config.pin_sccb_scl = CAMERA_PIN_SIOC;
    config.pin_pwdn = CAMERA_PIN_PWDN;
    config.pin_reset = CAMERA_PIN_RESET;
    config.xclk_freq_hz = 20000000;
    config.pixel_format = PIXFORMAT_JPEG;
    config.grab_mode = CAMERA_GRAB_LATEST; // Always grab fresh frame on on-demand capture

    // 3. Dynamic Frame Buffer Allocation based on measured memory
    if (s_telemetry.psram_detected && s_telemetry.free_psram_bytes >= (1024 * 1024)) {
        // High quality mode with 8MB Octal PSRAM
        config.frame_size = FRAMESIZE_VGA;  // 640x480 crisp for vision inference
        config.jpeg_quality = 12;           // High JPEG quality (lower is better, range 10-63)
        config.fb_count = 1;                // 1 buffer avoids stale frames on on-demand captures
        config.fb_location = CAMERA_FB_IN_PSRAM;
        s_telemetry.frame_width = 640;
        s_telemetry.frame_height = 480;
        s_telemetry.jpeg_quality = 12;
    } else if (s_telemetry.free_heap_bytes >= (64 * 1024)) {
        // Safe DRAM fallback when PSRAM is unavailable or constrained
        log_info("WARNING: Operating in fallback DRAM mode due to PSRAM absence");
        config.frame_size = FRAMESIZE_QVGA; // 320x240 safe for internal DRAM
        config.jpeg_quality = 20;
        config.fb_count = 1;
        config.fb_location = CAMERA_FB_IN_DRAM;
        s_telemetry.frame_width = 320;
        s_telemetry.frame_height = 240;
        s_telemetry.jpeg_quality = 20;
    } else {
        snprintf(s_telemetry.status_message, sizeof(s_telemetry.status_message),
                 "CRITICAL: Insufficient memory (DRAM < 64KB, PSRAM missing)");
        log_info(s_telemetry.status_message);
        display_set_state(DISPLAY_STATE_ERROR, "CAM ERR: NO MEM");
        return CAMERA_ERR_NO_PSRAM_HEAP;
    }

    // 4. Initialize ESP Camera Driver
    esp_err_t err = esp_camera_init(&config);
    if (err != 0) {
        snprintf(s_telemetry.status_message, sizeof(s_telemetry.status_message),
                 "Driver init failed with error 0x%x", err);
        log_info(s_telemetry.status_message);
        display_set_state(DISPLAY_STATE_ERROR, "CAM ERR: INIT");
        return CAMERA_ERR_DRIVER_INIT_FAILED;
    }

    // 5. Inspect Sensor PID and verify OV3660 Hardware Identity
    sensor_t *s = esp_camera_sensor_get();
    if (!s) {
        snprintf(s_telemetry.status_message, sizeof(s_telemetry.status_message),
                 "Failed to obtain camera sensor pointer");
        log_info(s_telemetry.status_message);
        esp_camera_deinit();
        return CAMERA_ERR_SENSOR_PROBE_FAILED;
    }

    s_telemetry.detected_sensor_pid = s->id.PID;
    if (s_telemetry.detected_sensor_pid == OV3660_CHIP_PID) {
        s_telemetry.is_ov3660_verified = true;
        snprintf(s_telemetry.status_message, sizeof(s_telemetry.status_message),
                 "OV3660 confirmed (PID=0x%04X)", s_telemetry.detected_sensor_pid);
        log_info(s_telemetry.status_message);

        // OV3660-specific hardware register tuning
        s->set_vflip(s, 1);       // Vertical flip for physical XIAO mounting
        s->set_hmirror(s, 0);     // Normal orientation
        s->set_brightness(s, 1);  // Slight boost for indoor environments
        s->set_saturation(s, 0);  // Natural saturation
    } else {
        s_telemetry.is_ov3660_verified = false;
        snprintf(s_telemetry.status_message, sizeof(s_telemetry.status_message),
                 "WARNING: Sensor PID mismatch: read 0x%04X, expected OV3660 (0x%04X)",
                 s_telemetry.detected_sensor_pid, OV3660_CHIP_PID);
        log_info(s_telemetry.status_message);
        // Do not silently replace OV3660 with OV2640. Flag warning in telemetry.
    }

    s_telemetry.is_initialized = true;
    display_set_state(DISPLAY_STATE_IDLE_READY, "Camera Ready");
    return CAMERA_OK;
}

doruru_frame_t* camera_manager_capture_single(camera_trigger_mode_t trigger) {
    if (!s_telemetry.is_initialized) {
        log_info("Capture requested but camera not initialized");
        display_set_state(DISPLAY_STATE_ERROR, "CAM NOT INIT");
        return NULL;
    }

    // Notify display state machine
    display_set_state(DISPLAY_STATE_CAMERA_CAPTURE, "Looking...");

    // Find a free internal wrapper slot
    int slot = -1;
    for (int i = 0; i < MAX_BURST_FRAMES_LIMIT; i++) {
        if (!s_frame_slot_in_use[i]) {
            slot = i;
            break;
        }
    }
    if (slot == -1) {
        log_info("All frame buffer slots busy. Please release previously captured frames.");
        s_telemetry.capture_failures++;
        display_set_state(DISPLAY_STATE_ERROR, "FB SLOTS FULL");
        return NULL;
    }

    // Capture camera framebuffer from driver
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb || fb->len == 0 || !fb->buf) {
        log_info("Capture failed: null or zero-length framebuffer");
        if (fb) esp_camera_fb_return(fb);
        s_telemetry.capture_failures++;
        display_set_state(DISPLAY_STATE_ERROR, "CAPTURE FAIL");
        return NULL;
    }

    // Verify JPEG Magic Bytes (SOI 0xFF 0xD8)
    if (fb->format == PIXFORMAT_JPEG) {
        if (fb->len < 4 || fb->buf[0] != 0xFF || fb->buf[1] != 0xD8) {
            log_info("Capture failed: Corrupted JPEG header (missing SOI 0xFFD8)");
            esp_camera_fb_return(fb);
            s_telemetry.capture_failures++;
            display_set_state(DISPLAY_STATE_ERROR, "CORRUPT JPEG");
            return NULL;
        }
    }

    // Populate frame wrapper
    doruru_frame_t* dframe = &s_active_frames[slot];
    dframe->data = fb->buf;
    dframe->length = fb->len;
    dframe->width = (uint16_t)fb->width;
    dframe->height = (uint16_t)fb->height;
    dframe->trigger_mode = trigger;
#if defined(ESP32) || defined(ARDUINO)
    dframe->timestamp_ms = millis();
#else
    dframe->timestamp_ms = (uint32_t)clock();
#endif
    dframe->_internal_fb_ref = fb;
    s_frame_slot_in_use[slot] = true;

    s_telemetry.total_captures++;
    return dframe;
}

int camera_manager_capture_burst(camera_trigger_mode_t trigger,
                                uint8_t burst_count,
                                uint16_t interval_ms,
                                doruru_frame_t** out_frames) {
    if (!s_telemetry.is_initialized || !out_frames) {
        return 0;
    }

    // Strictly enforce burst ceiling (no continuous capture or streaming)
    if (burst_count > MAX_BURST_FRAMES_LIMIT) {
        log_info("Burst count exceeds maximum safe limit of 3; clamping");
        burst_count = MAX_BURST_FRAMES_LIMIT;
    }

    int captured = 0;
    for (uint8_t i = 0; i < burst_count; i++) {
        doruru_frame_t* frame = camera_manager_capture_single(trigger);
        if (frame) {
            out_frames[captured++] = frame;
        } else {
            break;
        }

        if (i < burst_count - 1 && interval_ms > 0) {
#if defined(ESP32) || defined(ARDUINO)
            delay(interval_ms);
#endif
        }
    }

    return captured;
}

bool camera_manager_release_frame(doruru_frame_t* frame) {
    if (!frame || !frame->_internal_fb_ref) {
        return false;
    }

    camera_fb_t* fb = (camera_fb_t*)frame->_internal_fb_ref;
    esp_camera_fb_return(fb);

    // Clear and free the slot
    for (int i = 0; i < MAX_BURST_FRAMES_LIMIT; i++) {
        if (&s_active_frames[i] == frame) {
            s_frame_slot_in_use[i] = false;
            memset(&s_active_frames[i], 0, sizeof(doruru_frame_t));
            return true;
        }
    }

    return true;
}

const camera_telemetry_t* camera_manager_get_telemetry(void) {
    return &s_telemetry;
}

bool camera_manager_deinit(void) {
    for (int i = 0; i < MAX_BURST_FRAMES_LIMIT; i++) {
        if (s_frame_slot_in_use[i]) {
            camera_manager_release_frame(&s_active_frames[i]);
        }
    }

    esp_err_t err = esp_camera_deinit();
    s_telemetry.is_initialized = false;
    display_set_state(DISPLAY_STATE_IDLE_READY, "Camera Off");
    return (err == 0);
}

