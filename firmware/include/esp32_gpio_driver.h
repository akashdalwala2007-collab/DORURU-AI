#pragma once

#ifdef ARDUINO
#include <Arduino.h>
#include "motor_controller.h"

namespace doruru {
namespace hal {

/**
 * Hardware Abstraction Layer for ESP32 Arduino GPIO and PWM operations.
 */
class Esp32GpioDriver : public motor::IGpioDriver {
public:
    Esp32GpioDriver() = default;
    ~Esp32GpioDriver() override = default;

    void setPinModeOutput(uint8_t pin) override {
        pinMode(pin, OUTPUT);
    }

    void writeDigital(uint8_t pin, uint8_t level) override {
        if (!level) {
            // Clear / detach LEDC PWM output before driving pin LOW
            analogWrite(pin, 0);
            digitalWrite(pin, LOW);
        } else {
            digitalWrite(pin, HIGH);
        }
    }

    void writePwm(uint8_t pin, uint8_t duty_cycle) override {
        // ESP32 Arduino v2.x / v3.x supports analogWrite mapped over LEDC
        analogWrite(pin, duty_cycle);
    }

    uint32_t getMillis() override {
        return millis();
    }
};

} // namespace hal
} // namespace doruru
#endif

