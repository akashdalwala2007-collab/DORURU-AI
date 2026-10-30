#pragma once

#include <stdint.h>
#include <stdbool.h>

namespace doruru {
namespace sensors {

/**
 * Sensor status indicator.
 */
enum class SensorStatus {
    UNAVAILABLE = 0, // Hardware not present or not confirmed
    OK = 1,          // Hardware initialized and providing valid data
    ERROR = 2        // Hardware failure or invalid reading
};

/**
 * Sensor interface providing hardware abstraction for distance sensors
 * and wheel encoders.
 * 
 * In accordance with DORURU architecture rules, any unconfirmed sensor
 * must return UNAVAILABLE and safe disabled states. No false claims of
 * distance-accurate movement or autonomous obstacle avoidance are allowed.
 */
class ISensorProvider {
public:
    virtual ~ISensorProvider() = default;

    // Distance sensing
    virtual bool isDistanceSensorAvailable() const = 0;
    virtual SensorStatus getDistanceSensorStatus() const = 0;
    virtual float getDistanceCm() const = 0;

    // Wheel odometry
    virtual bool isWheelEncoderAvailable() const = 0;
    virtual SensorStatus getEncoderStatus() const = 0;
    virtual int32_t getLeftEncoderTicks() const = 0;
    virtual int32_t getRightEncoderTicks() const = 0;

    // Autonomy capability queries
    virtual bool isObstacleAvoidanceSupported() const = 0;
    virtual bool isOdometrySupported() const = 0;
};

/**
 * Safe disabled sensor provider used when physical distance sensors
 * or wheel encoders are not confirmed.
 */
class DisabledSensorProvider : public ISensorProvider {
public:
    DisabledSensorProvider() = default;
    ~DisabledSensorProvider() override = default;

    bool isDistanceSensorAvailable() const override { return false; }
    SensorStatus getDistanceSensorStatus() const override { return SensorStatus::UNAVAILABLE; }
    float getDistanceCm() const override { return -1.0f; }

    bool isWheelEncoderAvailable() const override { return false; }
    SensorStatus getEncoderStatus() const override { return SensorStatus::UNAVAILABLE; }
    int32_t getLeftEncoderTicks() const override { return 0; }
    int32_t getRightEncoderTicks() const override { return 0; }

    bool isObstacleAvoidanceSupported() const override { return false; }
    bool isOdometrySupported() const override { return false; }
};

/**
 * Accessor for the active sensor provider singleton.
 */
ISensorProvider& getSensorProvider();

} // namespace sensors
} // namespace doruru

