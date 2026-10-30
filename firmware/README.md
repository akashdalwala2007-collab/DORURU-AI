# DORURU Firmware — Motor Control & Hardware Abstraction

**Target Controller**: Seeed Studio XIAO ESP32-S3 Sense  
**Framework**: Arduino ESP32 / PlatformIO  
**Status**: Phase 3 Verified  

---

## 1. Confirmed Hardware Pinout

| Peripheral | Board Pin | ESP32-S3 GPIO | Function / Notes |
| :--- | :--- | :--- | :--- |
| **MX1508 Motor A (Left)** | **D3** | **GPIO4** | IN1 (PWM / Direction) |
| **MX1508 Motor A (Left)** | **D2** | **GPIO3** | IN2 (PWM / Direction) |
| **MX1508 Motor B (Right)**| **D1** | **GPIO2** | IN3 (PWM / Direction) |
| **MX1508 Motor B (Right)**| **D0** | **GPIO1** | IN4 (PWM / Direction) |
| **MAX98357A Audio** | **D4** | **GPIO5** | DIN (I2S_NUM_1) |
| **MAX98357A Audio** | **D5** | **GPIO6** | BCLK (I2S_NUM_1) |
| **MAX98357A Audio** | **D6** | **GPIO43**| LRC (I2S_NUM_1) — *UART0 TX Conflict Avoided* |
| **ILI9341 Display** | **D8** | **GPIO7** | RESET Pulse |
| **ILI9341 Display** | **D7** | **GPIO44**| D/C — *UART0 RX Conflict Avoided* |
| **ILI9341 Display** | **D9** | **GPIO8** | MOSI / SDI (Custom SPI) |
| **ILI9341 Display** | **D10**| **GPIO9** | SCK / CLK (Custom SPI) |
| **ILI9341 Display** | — | **GND** | CS permanently grounded (software `CS = -1`) |
| **Onboard PDM Mic** | Internal | **GPIO41**| DATA (I2S_NUM_0) — *Reserved Sense Pin* |
| **Onboard PDM Mic** | Internal | **GPIO42**| CLK (I2S_NUM_0) — *Reserved Sense Pin* |
| **OV3660 Camera** | Internal | Dedicated | Dedicated Sense DVP Camera Bus |

---

## 2. Critical Safety & Electrical Rules

> [!CAUTION]
> **ELECTRICAL POWER WARNING**:
> - **NEVER power DC motors from the ESP32 3.3V or 5V rail.**
> - Use an independent battery or dedicated regulated motor supply connected to MX1508 `VM` / `+`.
> - Maintain a **clean common ground (GND)** between battery, MX1508, ESP32-S3, display, and audio amplifier.
> - Ensure decoupling capacitors (e.g. 100uF–470uF low-ESR electrolytic across motor supply terminals) are installed to prevent inductive voltage sags that trip the ESP32 brownout detector.

### Software Safety Invariants:
1. **Startup Default STOP**: At boot, all motor pins are set to OUTPUT and driven LOW.
2. **Emergency Stop (Highest Priority)**: Instantly halts all motion, sets pins LOW, and locks controller out until explicit clear (`clearEmergencyStop()`).
3. **Automatic Watchdog Timeout**: Movement duration is capped at `MAX_DURATION_MS = 3000ms`. When duration expires, motors automatically stop without requiring a remote stop command.
4. **Heartbeat Communication Loss Watchdog**: If backend or Wi-Fi command stream drops for `> 1500ms`, motors immediately stop.
5. **Soft-Start PWM Ramp Limiter**: Limits rate of duty cycle change to mitigate current inrush spikes.
6. **Autonomy Lock**: Distance sensors and wheel encoders are unconfirmed; software interface returns `DISABLED/UNAVAILABLE`. Autonomous navigation is locked out, and time-based movements are labeled `approximate`.

---

## 3. Bench Testing Protocol

> [!IMPORTANT]
> **WHEEL ELEVATION MANDATE**: Before applying motor power or issuing movement commands on the bench, **elevate the robot chassis so both wheels spin freely in the air**. Do not place the robot on an open table or unconstrained surface during initial testing.

### Interactive Serial Bench Console (USB CDC at 115200 baud):
- `F <pwm> <ms>` : Forward (e.g. `F 150 1000` = 150 PWM for 1.0s)
- `B <pwm> <ms>` : Reverse (e.g. `B 150 1000`)
- `L <pwm> <ms>` : Pivot Left (differential spin: Left reverse, Right forward)
- `R <pwm> <ms>` : Pivot Right (differential spin: Left forward, Right reverse)
- `S` : Immediate Normal Stop
- `E` : **Emergency Stop** (Locks controller; all subsequent motion rejected)
- `C` : Clear Emergency Stop
- `H` : Feed Heartbeat Watchdog
- `T` : Print Real-time Telemetry
- `?` : Print Help Menu

---

## 4. Build Configuration

In `platformio.ini`:
```ini
[env:seeed_xiao_esp32s3]
platform = espressif32
board = seeed_xiao_esp32s3
framework = arduino
board_build.mcu = esp32s3
board_build.f_cpu = 240000000L
board_build.arduino.memory_type = qio_opi
build_flags = 
    -DBOARD_HAS_PSRAM
    -DARDUINO_USB_CDC_ON_BOOT=1
    -DARDUINO_USB_MODE=1
    -I include
```
* Note: `ARDUINO_USB_CDC_ON_BOOT=1` routes Serial over native USB CDC, avoiding UART0 pin conflicts on D6 (GPIO43) and D7 (GPIO44).

