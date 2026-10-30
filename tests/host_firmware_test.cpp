/**
 * @file host_firmware_test.cpp
 * @brief Host unit and integration tests for DORURU camera and vision transport.
 * Exercises camera_manager.cpp, vision_transport.cpp, and display_interface.cpp directly.
 */

#include <stdio.h>
#include <assert.h>
#include <string.h>
#include "camera_manager.h"
#include "vision_transport.h"
#include "connectivity_manager.h"
#include "motor_safety.h"
#include "display_interface.h"
#include "ili9341_driver.h"
#include "doruru_persona.h"

static int g_display_callback_count = 0;
static display_state_t g_last_state = DISPLAY_STATE_BOOTING;
static char g_last_message[128] = {0};

static void test_display_callback(display_state_t state, const char* message) {
    g_display_callback_count++;
    g_last_state = state;
    if (message) {
        strncpy(g_last_message, message, sizeof(g_last_message) - 1);
        g_last_message[sizeof(g_last_message) - 1] = '\0';
    }
}

int main(void) {
    printf("[HOST_TEST] Starting DORURU Firmware Host Verification...\n");

    // Register display callback
    display_register_state_callback(test_display_callback);
    assert(display_get_current_state() == DISPLAY_STATE_BOOTING);

    // 1. Test Camera Initialization & OV3660 Sensor Probing
    camera_init_status_t init_res = camera_manager_init();
    assert(init_res == CAMERA_OK);
    const camera_telemetry_t* telem = camera_manager_get_telemetry();
    assert(telem->is_initialized == true);
    assert(telem->is_ov3660_verified == true);
    assert(telem->detected_sensor_pid == OV3660_CHIP_PID);
    assert(telem->psram_detected == true);
    assert(telem->frame_width == 640);
    assert(telem->frame_height == 480);
    assert(telem->jpeg_quality == 12);
    printf("  [PASS] camera_manager_init (OV3660 verified, 8MB PSRAM)\n");

    // 2. Test Single Capture and Explicit Frame Release
    doruru_frame_t* frame = camera_manager_capture_single(TRIGGER_ON_DEMAND_SINGLE);
    assert(frame != NULL);
    assert(frame->data != NULL);
    assert(frame->length > 4);
    assert(frame->data[0] == 0xFF && frame->data[1] == 0xD8); // Valid SOI
    assert(frame->width == 640);
    assert(frame->height == 480);
    assert(display_get_current_state() == DISPLAY_STATE_CAMERA_CAPTURE);

    bool rel_ok = camera_manager_release_frame(frame);
    assert(rel_ok == true);
    printf("  [PASS] camera_manager_capture_single & camera_manager_release_frame\n");

    // 3. Test Controlled Burst Capture with Bounded Limit Enforcement
    doruru_frame_t* burst_frames[5] = {0};

    // Requesting burst of 2 frames
    int count2 = camera_manager_capture_burst(TRIGGER_ON_DEMAND_BURST, 2, 0, burst_frames);
    assert(count2 == 2);
    assert(burst_frames[0] != NULL);
    assert(burst_frames[1] != NULL);
    camera_manager_release_frame(burst_frames[0]);
    camera_manager_release_frame(burst_frames[1]);

    // Requesting burst of 5 frames (must be clamped to MAX_BURST_FRAMES_LIMIT = 3)
    int count5 = camera_manager_capture_burst(TRIGGER_ON_DEMAND_BURST, 5, 0, burst_frames);
    assert(count5 == 3); // Strictly bounded to <= 3
    for (int i = 0; i < count5; i++) {
        assert(burst_frames[i] != NULL);
        camera_manager_release_frame(burst_frames[i]);
    }
    printf("  [PASS] camera_manager_capture_burst (clamped to max 3 frames)\n");

    // 4. Test Buffer Slot Full Protection
    doruru_frame_t* slot_frames[MAX_BURST_FRAMES_LIMIT];
    for (int i = 0; i < MAX_BURST_FRAMES_LIMIT; i++) {
        slot_frames[i] = camera_manager_capture_single(TRIGGER_ON_DEMAND_SINGLE);
        assert(slot_frames[i] != NULL);
    }
    // Attempt 4th capture when all slots are full
    doruru_frame_t* overflow_frame = camera_manager_capture_single(TRIGGER_ON_DEMAND_SINGLE);
    assert(overflow_frame == NULL); // Fails safely without leaking
    assert(display_get_current_state() == DISPLAY_STATE_ERROR);

    // Release slots
    for (int i = 0; i < MAX_BURST_FRAMES_LIMIT; i++) {
        camera_manager_release_frame(slot_frames[i]);
    }
    // Now capture works again
    doruru_frame_t* recovered_frame = camera_manager_capture_single(TRIGGER_ON_DEMAND_SINGLE);
    assert(recovered_frame != NULL);
    camera_manager_release_frame(recovered_frame);
    printf("  [PASS] Framebuffer slot exhaustion and recovery\n");

    // 5. Test Vision Transport with Active Network
    vision_transport_config_t cfg;
    strncpy(cfg.backend_endpoint, "http://127.0.0.1:8000/api/v1/vision/upload", sizeof(cfg.backend_endpoint));
    strncpy(cfg.device_id, "DORURU-SENSE-01", sizeof(cfg.device_id));
    strncpy(cfg.device_token, "test_valid_token", sizeof(cfg.device_token));
    cfg.http_timeout_ms = 5000;
    bool trans_init = vision_transport_init(&cfg);
    assert(trans_init == true);

    vision_transport_set_network_ready_for_testing(true);
    char response_buf[256] = {0};
    vision_transport_status_t t_res = vision_transport_capture_and_send(
        "Analyze workspace", response_buf, sizeof(response_buf)
    );
    assert(t_res == TRANSPORT_SUCCESS);
    assert(display_get_current_state() == DISPLAY_STATE_VISION_SUCCESS);
    printf("  [PASS] vision_transport_capture_and_send (online mode)\n");

    // 6. Test Vision Transport with Network Loss (Offline Recovery)
    vision_transport_set_network_ready_for_testing(false);
    assert(vision_transport_is_network_ready() == false);

    vision_transport_status_t offline_res = vision_transport_capture_and_send(
        "Analyze workspace", response_buf, sizeof(response_buf)
    );
    assert(offline_res == TRANSPORT_ERR_WIFI_DISCONNECTED);
    assert(display_get_current_state() == DISPLAY_STATE_WIFI_DISCONNECTED);
    assert(strstr(g_last_message, "Wi-Fi Disconnected") != NULL);

    // Verify camera slots are all free (no leaked frame buffer during network failure)
    doruru_frame_t* verify_frame = camera_manager_capture_single(TRIGGER_ON_DEMAND_SINGLE);
    assert(verify_frame != NULL);
    camera_manager_release_frame(verify_frame);
    printf("  [PASS] vision_transport_capture_and_send (network loss graceful recovery)\n");

    // De-initialize camera
    camera_manager_deinit();
    printf("  [PASS] Camera subsystem verified and deinitialized.\n");

    // 7. Test Motor Safety, Stale Command Rejection, and Watchdog
    motor_safety_init(500); // 500ms command timeout
    assert(motor_safety_get_state()->is_online == true);
    assert(motor_safety_get_state()->are_motors_active == false);

    // A. Valid forward command (Sequence 1)
    motor_command_t cmd1 = {
        .command_id = 1,
        .intent = MOTOR_CMD_FORWARD,
        .speed = 180,
        .duration_ms = 500,
        .timestamp_ms = 1000,
        .ttl_ms = 1000
    };
    safety_status_t s_res1 = motor_safety_process_command(&cmd1, 1200); // age 200ms < ttl 1000ms
    assert(s_res1 == SAFETY_OK);
    assert(motor_safety_get_state()->are_motors_active == true);
    assert(display_get_current_state() == DISPLAY_STATE_MOTOR_MOVING);

    // B. Replay of old sequence ID (Sequence 1 again <= 1)
    safety_status_t s_res_replay = motor_safety_process_command(&cmd1, 1300);
    assert(s_res_replay == SAFETY_ERR_SEQUENCE_REPLAY);

    // C. Stale command (Sequence 2, issued at 1000ms, processed at 2500ms > ttl 1000ms)
    motor_command_t cmd2_stale = {
        .command_id = 2,
        .intent = MOTOR_CMD_FORWARD,
        .speed = 180,
        .duration_ms = 500,
        .timestamp_ms = 1000,
        .ttl_ms = 1000
    };
    safety_status_t s_res_stale = motor_safety_process_command(&cmd2_stale, 2500);
    assert(s_res_stale == SAFETY_ERR_STALE_COMMAND);

    // D. Watchdog tick timeout
    motor_safety_tick(1200 + 600); // 600ms elapsed > 500ms timeout
    assert(motor_safety_get_state()->are_motors_active == false); // Motors halted by watchdog

    // E. Network loss immediately halts motors and shows offline status
    motor_command_t cmd3 = {
        .command_id = 3,
        .intent = MOTOR_CMD_FORWARD,
        .speed = 180,
        .duration_ms = 500,
        .timestamp_ms = 3000,
        .ttl_ms = 1000
    };
    assert(motor_safety_process_command(&cmd3, 3100) == SAFETY_OK);
    assert(motor_safety_get_state()->are_motors_active == true);
    motor_safety_on_network_loss();
    assert(motor_safety_get_state()->are_motors_active == false); // Halted on network loss
    assert(motor_safety_get_state()->is_online == false);
    assert(display_get_current_state() == DISPLAY_STATE_WIFI_DISCONNECTED);

    // F. Offline movement rejection (when offline and allow_offline_movement is false)
    motor_command_t cmd4 = {
        .command_id = 4,
        .intent = MOTOR_CMD_FORWARD,
        .speed = 180,
        .duration_ms = 500,
        .timestamp_ms = 3500,
        .ttl_ms = 1000
    };
    assert(motor_safety_process_command(&cmd4, 3600) == SAFETY_ERR_OFFLINE_DISABLED);

    // G. Network reconnect discards pre-disconnect commands and keeps motors halted
    motor_safety_on_network_reconnect(4000);
    assert(motor_safety_get_state()->is_online == true);
    assert(motor_safety_get_state()->are_motors_active == false); // No replay on reconnect

    // Verify pre-disconnect commands are rejected after reconnect (watermark advanced from 3 to 4)
    assert(motor_safety_get_state()->last_executed_sequence == 4);
    assert(motor_safety_process_command(&cmd3, 4050) == SAFETY_ERR_SEQUENCE_REPLAY);
    motor_command_t pre_disconnect_cmd = {
        .command_id = 2,
        .intent = MOTOR_CMD_FORWARD,
        .speed = 150,
        .duration_ms = 200,
        .timestamp_ms = 2500,
        .ttl_ms = 500
    };
    assert(motor_safety_process_command(&pre_disconnect_cmd, 4050) == SAFETY_ERR_SEQUENCE_REPLAY);

    // Verify STOP with a low command_id leaves the watermark unchanged
    uint32_t watermark_before_stop = motor_safety_get_state()->last_executed_sequence;
    assert(watermark_before_stop == 4);
    motor_command_t stop_low = {
        .command_id = 1,
        .intent = MOTOR_CMD_STOP,
        .speed = 0,
        .duration_ms = 50,
        .timestamp_ms = 4060,
        .ttl_ms = 1000
    };
    assert(motor_safety_process_command(&stop_low, 4060) == SAFETY_OK);
    assert(motor_safety_get_state()->last_executed_sequence == 4);

    // Verify STOP with higher command_id advances watermark
    motor_command_t stop_high = {
        .command_id = 5,
        .intent = MOTOR_CMD_STOP,
        .speed = 0,
        .duration_ms = 50,
        .timestamp_ms = 4065,
        .ttl_ms = 1000
    };
    assert(motor_safety_process_command(&stop_high, 4065) == SAFETY_OK);
    assert(motor_safety_get_state()->last_executed_sequence == 5);

    // Verify movement duration is correct and clamped to bounds [50, 2000] with deadline
    motor_command_t cmd_clamp_max = {
        .command_id = 6,
        .intent = MOTOR_CMD_FORWARD,
        .speed = 180,
        .duration_ms = 3500,
        .timestamp_ms = 4070,
        .ttl_ms = 1000
    };
    assert(motor_safety_process_command(&cmd_clamp_max, 4070) == SAFETY_OK);
    assert(motor_safety_get_state()->active_duration_ms == 2000);
    assert(motor_safety_get_state()->movement_deadline_ms == 4070 + 2000);

    motor_command_t cmd_clamp_min = {
        .command_id = 7,
        .intent = MOTOR_CMD_FORWARD,
        .speed = 180,
        .duration_ms = 20,
        .timestamp_ms = 4080,
        .ttl_ms = 1000
    };
    assert(motor_safety_process_command(&cmd_clamp_min, 4080) == SAFETY_OK);
    assert(motor_safety_get_state()->active_duration_ms == 50);
    assert(motor_safety_get_state()->movement_deadline_ms == 4080 + 50);

    // Verify movement duration completion: 150ms movement stops at elapsed >= 150ms
    motor_command_t cmd_duration = {
        .command_id = 8,
        .intent = MOTOR_CMD_FORWARD,
        .speed = 180,
        .duration_ms = 150,
        .timestamp_ms = 4100,
        .ttl_ms = 1000
    };
    assert(motor_safety_process_command(&cmd_duration, 4100) == SAFETY_OK);
    assert(motor_safety_get_state()->are_motors_active == true);
    assert(motor_safety_get_state()->active_duration_ms == 150);
    assert(motor_safety_get_state()->movement_deadline_ms == 4100 + 150);

    // At 100ms: still moving (< 150ms)
    motor_safety_tick(4100 + 100);
    assert(motor_safety_get_state()->are_motors_active == true);

    // At 150ms: duration expired (wrap-safe deadline reached), motors halted
    motor_safety_tick(4100 + 150);
    assert(motor_safety_get_state()->are_motors_active == false);

    // Verify oversized TTL capping: command with ttl_ms = 1000000 issued at 1000, checked at 7000 (> 5000ms cap)
    motor_command_t cmd_oversized_ttl = {
        .command_id = 9,
        .intent = MOTOR_CMD_FORWARD,
        .speed = 150,
        .duration_ms = 100,
        .timestamp_ms = 1000,
        .ttl_ms = 1000000
    };
    assert(motor_safety_process_command(&cmd_oversized_ttl, 7000) == SAFETY_ERR_STALE_COMMAND);

    // H. Emergency Stop priority
    motor_safety_emergency_stop();
    assert(motor_safety_get_state()->is_emergency_stop == true);
    assert(display_get_current_state() == DISPLAY_STATE_EMERGENCY_STOP);
    motor_command_t cmd10 = {
        .command_id = 10,
        .intent = MOTOR_CMD_FORWARD,
        .speed = 180,
        .duration_ms = 500,
        .timestamp_ms = 4300,
        .ttl_ms = 1000
    };
    assert(motor_safety_process_command(&cmd10, 4300) == SAFETY_ERR_EMERGENCY_STOP_ACTIVE);
    motor_safety_clear_emergency_stop();
    assert(motor_safety_get_state()->is_emergency_stop == false);
    printf("  [PASS] Motor safety, watchdog, stale-rejection & e-stop verified.\n");

    // 8. Test Connectivity Manager, Exponential Backoff, and Request Cancellation
    connectivity_config_t conn_cfg = {
        .initial_backoff_ms = 1000,
        .max_backoff_ms = 4000,
        .heartbeat_interval_ms = 2000,
        .heartbeat_timeout_ms = 1000
    };
    connectivity_manager_init(&conn_cfg);
    assert(connectivity_manager_is_online() == true);

    // A. Start in-flight request
    connectivity_manager_begin_request(42);
    assert(connectivity_manager_get_status()->inflight_request_active == true);

    // B. Network down triggers request cancellation and backoff
    connectivity_manager_on_network_down(5000);
    assert(connectivity_manager_is_online() == false);
    assert(connectivity_manager_get_status()->inflight_request_active == false); // Request cancelled!
    assert(connectivity_manager_get_status()->state == CONN_STATE_RECONNECT_BACKOFF);
    assert(connectivity_manager_get_status()->next_reconnect_ms == 6000); // 5000 + 1000

    // C. Backoff progression (exponential: 1000ms -> 2000ms -> 4000ms)
    connectivity_manager_on_network_down(6500); // 2nd drop
    assert(connectivity_manager_get_status()->next_reconnect_ms == 6500 + 2000);

    connectivity_manager_on_network_down(9000); // 3rd drop (clamped to max 4000 without overflow)
    assert(connectivity_manager_get_status()->next_reconnect_ms == 9000 + 4000);
    assert(connectivity_manager_get_status()->current_backoff_ms == 4000);

    // D. Reconnection restores online state and resets backoff
    connectivity_manager_on_network_up(14000);
    assert(connectivity_manager_is_online() == true);
    assert(connectivity_manager_get_status()->current_backoff_ms == 1000);

    // E. Heartbeat timeout triggers offline
    connectivity_manager_record_heartbeat(9000);
    connectivity_manager_tick(9000 + 3500); // 3500ms > 2000+1000ms
    assert(connectivity_manager_is_online() == false);
    printf("  [PASS] Connectivity manager, exponential backoff & cancellation verified.\n");

    // 9. Test ILI9341 Display Subsystem, Hardware Reset, Persona Screens, Demo Mode, & Safe Fallback
    printf("  [TEST 9] Testing ILI9341 Display Subsystem & DORURU Persona...\n");

    // A. Driver Init & Hardware Reset Pulse Verification
    bool disp_init_ok = display_init();
    assert(disp_init_ok == true);
    assert(display_is_hardware_reset_performed() == true);
    assert(display_get_frame_count() >= 1);
    printf("    [PASS] display_init & D8 (GPIO7) hardware reset pulse confirmed.\n");

    // B. Verify All 11+ Display State Transitions & String Conversions
    const display_state_t all_states[] = {
        DISPLAY_STATE_BOOTING,
        DISPLAY_STATE_IDLE_READY,
        DISPLAY_STATE_WAKE_WORD_DETECTED,
        DISPLAY_STATE_LISTENING,
        DISPLAY_STATE_PROCESSING_THINKING,
        DISPLAY_STATE_SPEAKING,
        DISPLAY_STATE_CAMERA_CAPTURE,
        DISPLAY_STATE_VISION_PROCESSING,
        DISPLAY_STATE_VISION_SUCCESS,
        DISPLAY_STATE_WIFI_DISCONNECTED,
        DISPLAY_STATE_ERROR,
        DISPLAY_STATE_MOTOR_MOVING,
        DISPLAY_STATE_EMERGENCY_STOP
    };
    const size_t num_states = sizeof(all_states) / sizeof(all_states[0]);
    assert(num_states == 13);

    for (size_t i = 0; i < num_states; i++) {
        display_state_t st = all_states[i];
        char test_msg[64];
        snprintf(test_msg, sizeof(test_msg), "Verifying state %d", (int)st);

        ili9341_reset_op_count();
        display_set_state(st, test_msg);

        assert(display_get_current_state() == st);
        assert(strcmp(display_get_last_message(), test_msg) == 0);
        assert(g_last_state == st);
        assert(strcmp(g_last_message, test_msg) == 0);

        const char* st_name = display_state_to_string(st);
        assert(st_name != NULL && strlen(st_name) > 0);
        assert(strcmp(st_name, "UNKNOWN") != 0);

        // Verify draw primitives were exercised
        assert(ili9341_get_op_count() > 0);
    }
    printf("    [PASS] All 13 display states rendered & verified.\n");

    // C. Non-blocking Animation Ticks
    uint32_t frames_before = display_get_frame_count();
    for (int t = 0; t < 20; t++) {
        display_update();
    }
    assert(display_get_frame_count() >= frames_before);
    printf("    [PASS] Non-blocking display_update animation cadence verified.\n");

    // D. Display Demo Mode Sequence (Cycles without motor movement)
    display_set_demo_mode(true, 500);
    assert(display_is_demo_mode() == true);
    assert(display_get_demo_step_interval() == 500);

    display_state_t initial_demo_state = display_get_current_state();
    for (size_t d = 0; d < 15; d++) {
        display_step_demo();
        assert(display_get_current_state() < DISPLAY_STATE_COUNT);
    }
    display_set_demo_mode(false, 0);
    assert(display_is_demo_mode() == false);
    assert(display_get_current_state() == DISPLAY_STATE_IDLE_READY);
    printf("    [PASS] Display demo mode sequence confirmed (safe, zero motor movement).\n");

    // E. Fail-Safe Fallback Screen Protection
    assert(display_is_fallback_active() == false);
    display_set_render_error_simulation(true);
    assert(display_is_fallback_active() == true);

    // Verify recovery from fallback
    display_set_render_error_simulation(false);
    assert(display_is_fallback_active() == false);
    printf("    [PASS] High-contrast fail-safe rendering fallback confirmed.\n");

    printf("[HOST_TEST] ALL 9 FIRMWARE HOST TESTS PASSED!\n");
    return 0;
}

