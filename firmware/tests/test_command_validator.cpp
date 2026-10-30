#include <iostream>
#include <cassert>
#include "command_validator.h"
#include "motor_controller.h"
#include "sensor_interface.h"

using namespace doruru;
using namespace doruru::motor;
using namespace doruru::safety;
using namespace doruru::sensors;

class MockGpioDriver : public IGpioDriver {
public:
    void setPinModeOutput(uint8_t) override {}
    void writeDigital(uint8_t, uint8_t) override {}
    void writePwm(uint8_t, uint8_t) override {}
    uint32_t getMillis() override { return simulated_millis; }
    uint32_t simulated_millis{0};
};

static int g_tests_passed = 0;
static int g_tests_total = 0;

#define TEST_ASSERT(cond, msg) \
    do { \
        if (!(cond)) { \
            std::cerr << "  ❌ ASSERTION FAILED: " << msg << " (" << #cond << ") at line " << __LINE__ << std::endl; \
            return false; \
        } \
    } while(0)

#define RUN_TEST(fn) \
    do { \
        g_tests_total++; \
        std::cout << "[TEST " << g_tests_total << "] Running " << #fn << "..." << std::endl; \
        if (fn()) { \
            g_tests_passed++; \
            std::cout << "  ✅ PASSED" << std::endl; \
        } else { \
            std::cerr << "  ❌ FAILED" << std::endl; \
        } \
    } while(0)

bool test_valid_packet_accepted() {
    MockGpioDriver mock;
    DisabledSensorProvider sensors;
    MotorController controller(mock, sensors);
    controller.init();
    CommandValidator validator;

    InboundCommandPacket packet{
        1,                                          // sequence_id
        static_cast<uint8_t>(Direction::FORWARD),  // direction
        150,                                        // speed_pwm
        1000,                                       // duration_ms
        1000,                                       // timestamp_ms
        1000,                                       // ttl_ms
        1                                           // autonomy_level
    };

    MotionCommand out_cmd{};
    uint32_t device_now_ms = 1200; // Age is 200ms < 1000ms TTL

    auto res = validator.validate(packet, device_now_ms, controller, out_cmd);
    TEST_ASSERT(res == ValidationResult::ACCEPTED, "Valid packet must be accepted");
    TEST_ASSERT(out_cmd.direction == Direction::FORWARD, "Direction must be FORWARD");
    TEST_ASSERT(out_cmd.speed_pwm == 150, "Speed must be 150");
    TEST_ASSERT(out_cmd.duration_ms == 1000, "Duration must be 1000ms");
    TEST_ASSERT(validator.getLastSequenceId() == 1, "Last sequence ID must be 1");

    return true;
}

bool test_replay_attack_rejected() {
    MockGpioDriver mock;
    DisabledSensorProvider sensors;
    MotorController controller(mock, sensors);
    controller.init();
    CommandValidator validator;

    MotionCommand out_cmd{};

    // Packet 1 (sequence 1) -> accepted
    InboundCommandPacket p1{1, 1, 150, 1000, 1000, 1000, 1};
    TEST_ASSERT(validator.validate(p1, 1100, controller, out_cmd) == ValidationResult::ACCEPTED, "P1 accepted");

    // Packet 2 (sequence 2) -> accepted
    InboundCommandPacket p2{2, 1, 150, 1000, 1100, 1000, 1};
    TEST_ASSERT(validator.validate(p2, 1200, controller, out_cmd) == ValidationResult::ACCEPTED, "P2 accepted");

    // Replay Packet 2 (duplicate sequence 2) -> rejected
    TEST_ASSERT(validator.validate(p2, 1250, controller, out_cmd) == ValidationResult::REJECTED_REPLAY_ATTACK,
                "Duplicate sequence must be rejected as replay attack");

    // Replay Packet 1 (older sequence 1) -> rejected
    TEST_ASSERT(validator.validate(p1, 1300, controller, out_cmd) == ValidationResult::REJECTED_REPLAY_ATTACK,
                "Older sequence must be rejected as replay attack");

    // Packet 3 (sequence 3) -> accepted
    InboundCommandPacket p3{3, 1, 150, 1000, 1300, 1000, 1};
    TEST_ASSERT(validator.validate(p3, 1350, controller, out_cmd) == ValidationResult::ACCEPTED, "P3 accepted");

    return true;
}

bool test_stale_packet_timestamp_expired() {
    MockGpioDriver mock;
    DisabledSensorProvider sensors;
    MotorController controller(mock, sensors);
    controller.init();
    CommandValidator validator;
    MotionCommand out_cmd{};

    // Created at 1000ms, TTL 1000ms. Received at device time 2500ms (age = 1500ms > TTL)
    InboundCommandPacket stalePacket{1, 1, 150, 1000, 1000, 1000, 1};
    auto res = validator.validate(stalePacket, 2500, controller, out_cmd);
    TEST_ASSERT(res == ValidationResult::REJECTED_STALE_PACKET, "Stale packet must be dropped");

    return true;
}

bool test_future_dated_packet_rejected() {
    MockGpioDriver mock;
    DisabledSensorProvider sensors;
    MotorController controller(mock, sensors);
    controller.init();
    CommandValidator validator;
    MotionCommand out_cmd{};

    // 1. Within future skew allowance (timestamp 1150ms vs device time 1000ms, delta=150ms <= 200ms)
    InboundCommandPacket futureWithinSkew{1, 1, 150, 1000, 1150, 1000, 1};
    auto res1 = validator.validate(futureWithinSkew, 1000, controller, out_cmd);
    TEST_ASSERT(res1 == ValidationResult::ACCEPTED,
                "Future-dated packet within skew allowance (<=200ms) must be accepted");

    // 2. Beyond future skew allowance (timestamp 1350ms vs device time 1000ms, delta=350ms > 200ms)
    InboundCommandPacket futureBeyondSkew{2, 1, 150, 1000, 1350, 1000, 1};
    auto res2 = validator.validate(futureBeyondSkew, 1000, controller, out_cmd);
    TEST_ASSERT(res2 == ValidationResult::REJECTED_STALE_PACKET,
                "Future-dated packet beyond skew allowance (>200ms) must return REJECTED_STALE_PACKET");

    return true;
}

bool test_unsupported_autonomy_level_rejected() {
    MockGpioDriver mock;
    DisabledSensorProvider sensors;
    MotorController controller(mock, sensors);
    controller.init();
    CommandValidator validator;
    MotionCommand out_cmd{};

    // Level 2 (Obstacle-aware) request -> rejected
    InboundCommandPacket pLevel2{1, 1, 150, 1000, 1000, 1000, 2};
    TEST_ASSERT(validator.validate(pLevel2, 1100, controller, out_cmd) == ValidationResult::REJECTED_UNSUPPORTED_AUTONOMY_LEVEL,
                "Level 2 autonomy must be rejected without hardware sensors");

    // Level 4 (Full autonomous / user following) -> rejected
    InboundCommandPacket pLevel4{2, 1, 150, 1000, 1100, 1000, 4};
    TEST_ASSERT(validator.validate(pLevel4, 1200, controller, out_cmd) == ValidationResult::REJECTED_UNSUPPORTED_AUTONOMY_LEVEL,
                "Level 4 autonomy must be rejected");

    return true;
}

bool test_speed_and_duration_bounds() {
    MockGpioDriver mock;
    DisabledSensorProvider sensors;
    MotorController controller(mock, sensors);
    controller.init();
    CommandValidator validator;
    MotionCommand out_cmd{};

    // Speed too low (40 < 60)
    InboundCommandPacket pSlow{1, 1, 40, 1000, 1000, 1000, 1};
    TEST_ASSERT(validator.validate(pSlow, 1100, controller, out_cmd) == ValidationResult::REJECTED_SPEED_OUT_OF_BOUNDS,
                "Speed below 60 must be rejected");

    // Speed too high (240 > 220)
    InboundCommandPacket pFast{2, 1, 240, 1000, 1100, 1000, 1};
    TEST_ASSERT(validator.validate(pFast, 1200, controller, out_cmd) == ValidationResult::REJECTED_SPEED_OUT_OF_BOUNDS,
                "Speed above 220 must be rejected");

    // Duration too brief (20ms < 50ms)
    InboundCommandPacket pBrief{3, 1, 150, 20, 1200, 1000, 1};
    TEST_ASSERT(validator.validate(pBrief, 1300, controller, out_cmd) == ValidationResult::REJECTED_DURATION_OUT_OF_BOUNDS,
                "Duration below 50ms must be rejected");

    // Duration too long (4000ms > 3000ms)
    InboundCommandPacket pLong{4, 1, 150, 4000, 1300, 1000, 1};
    TEST_ASSERT(validator.validate(pLong, 1400, controller, out_cmd) == ValidationResult::REJECTED_DURATION_OUT_OF_BOUNDS,
                "Duration above 3000ms must be rejected");

    return true;
}

bool test_emergency_stop_lockout_in_validator() {
    MockGpioDriver mock;
    DisabledSensorProvider sensors;
    MotorController controller(mock, sensors);
    controller.init();
    CommandValidator validator;
    MotionCommand out_cmd{};

    // Engage Emergency Stop on motor controller
    controller.emergencyStop();

    InboundCommandPacket packet{1, 1, 150, 1000, 1000, 1000, 1};
    auto res = validator.validate(packet, 1100, controller, out_cmd);
    TEST_ASSERT(res == ValidationResult::REJECTED_EMERGENCY_STOP_ACTIVE,
                "Inbound command must be rejected when emergency stop is active");

    return true;
}

bool test_sequence_exhaustion_and_recovery() {
    MockGpioDriver mock;
    DisabledSensorProvider sensors;
    MotorController controller(mock, sensors);
    controller.init();
    CommandValidator validator;
    MotionCommand out_cmd{};

    // 1. Process packet with maximum uint32 sequence ID
    InboundCommandPacket maxSeqPacket{UINT32_MAX, 1, 150, 1000, 1000, 1000, 1};
    auto res1 = validator.validate(maxSeqPacket, 1050, controller, out_cmd);
    TEST_ASSERT(res1 == ValidationResult::ACCEPTED, "UINT32_MAX sequence packet must be accepted");
    TEST_ASSERT(validator.isSequenceExhausted() == true, "Validator must report sequence space exhausted");

    // 2. Further packet with wrapped/lower sequence ID is rejected as replay attack
    InboundCommandPacket wrappedPacket{1, 1, 150, 1000, 1100, 1000, 1};
    auto res2 = validator.validate(wrappedPacket, 1150, controller, out_cmd);
    TEST_ASSERT(res2 == ValidationResult::REJECTED_REPLAY_ATTACK,
                "Wrapped packet after UINT32_MAX must be rejected as replay attack");

    // 3. Apply recovery behavior: reset validator state
    validator.reset();
    TEST_ASSERT(validator.isSequenceExhausted() == false, "Validator must clear exhausted state after reset");
    TEST_ASSERT(validator.getLastSequenceId() == 0, "Last sequence ID must be reset to 0");

    // 4. Inbound packet with sequence 1 is now accepted after reset recovery
    auto res3 = validator.validate(wrappedPacket, 1200, controller, out_cmd);
    TEST_ASSERT(res3 == ValidationResult::ACCEPTED, "Sequence 1 must be accepted following recovery reset");

    return true;
}

int main() {
    std::cout << "==================================================" << std::endl;
    std::cout << "  DORURU FIRMWARE COMMAND VALIDATOR TEST SUITE     " << std::endl;
    std::cout << "==================================================" << std::endl;

    RUN_TEST(test_valid_packet_accepted);
    RUN_TEST(test_replay_attack_rejected);
    RUN_TEST(test_stale_packet_timestamp_expired);
    RUN_TEST(test_future_dated_packet_rejected);
    RUN_TEST(test_unsupported_autonomy_level_rejected);
    RUN_TEST(test_speed_and_duration_bounds);
    RUN_TEST(test_emergency_stop_lockout_in_validator);
    RUN_TEST(test_sequence_exhaustion_and_recovery);

    std::cout << "==================================================" << std::endl;
    std::cout << "TEST SUMMARY: " << g_tests_passed << " / " << g_tests_total << " passed." << std::endl;
    std::cout << "==================================================" << std::endl;

    return (g_tests_passed == g_tests_total) ? 0 : 1;
}

