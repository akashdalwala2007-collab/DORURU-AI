# PHASE 4: DISPLAY STATES, EXPRESSIONS AND ROBOT PERSONA

> **Subsystem**: ILI9341 2.8" SPI TFT & DORURU Robot Persona  
> **Target Controller**: Seeed Studio XIAO ESP32-S3 Sense  
> **Status**: Verified & Integrated  
> **Milestone**: DORURU-AI v1.0  

---

## 1. Subsystem Architecture Overview

Phase 4 establishes the visual personality and responsive user interface for **DORURU** on the 2.8-inch ILI9341 SPI TFT display (320x240 landscape orientation). The subsystem connects high-level system states from the motor safety supervisor, camera manager, vision transport client, and speech pipelines to expressive, real-time facial animations and readable diagnostic banners.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        DORURU DISPLAY SUBSYSTEM                         │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  [ Header Bar ]     [ DORURU ]       STATE TITLE         (Status Dot)  │
│  ────────────────────────────────────────────────────────────────────  │
│                                                                        │
│  [ Face Canvas ]      ╭──────╮                        ╭──────╮         │
│                       │  ●   │   (Expression Area)    │  ●   │         │
│                       ╰──────╯                        ╰──────╯         │
│                                (Mouth / Waveform)                      │
│                                                                        │
│  ────────────────────────────────────────────────────────────────────  │
│  [ Footer Bar ]     Subsystem diagnostic status or user message        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Display Hardware & SPI Configuration

### 2.1 Confirmed Pin Mapping (Preserved Exactly)

The display uses the confirmed custom SPI bus configuration established in Phase 2. Default board SPI pin macros are strictly avoided:

| Display Pin | XIAO Sense D-Pin | ESP32-S3 GPIO | Bus / Signal Function | Hardware Constraint & Protection |
| :--- | :--- | :--- | :--- | :--- |
| **SCK / CLK** | **D10** | **GPIO9** | Custom SPI Clock | Master clock for ILI9341 SPI transactions |
| **MOSI / SDI**| **D9** | **GPIO8** | Custom SPI MOSI | Master-out slave-in SPI data line |
| **MISO** | — | **-1** | Not Connected | Unidirectional write-only display bus |
| **CS** | — | **-1** | Grounded (GND) | Hardwired to GND; software SS pin is disabled (`-1`) |
| **D/C** | **D7** | **GPIO44** | Data / Command Select | **UART0 RX Pin**: Protected via Native USB CDC logging |
| **RESET** | **D8** | **GPIO7** | Hardware Reset Pulse | Active-low reset pulse executed at boot |
| **VCC** | 5V / VBUS | 5V Rail | Power Supply | Valid for breakout with onboard 3.3V LDO regulator |
| **LED** | 3V3 | 3.3V Rail | Backlight Power | Display backlight supply |

### 2.2 Critical Hardware Rules & Protections

1. **Hardware Reset Pulse on D8 (GPIO7)**:  
   During `ili9341_driver_init()`, the driver executes a mandatory hardware reset pulse on `TFT_PIN_RESET` (D8 / GPIO7):
   - Drive `TFT_PIN_RESET` HIGH for 10ms.
   - Assert LOW for 20ms.
   - Drive HIGH for 150ms to allow ILI9341 internal controller bootloader completion.
2. **UART0 Pin Conflict Mitigation on D7 (GPIO44)**:  
   Because D7 (GPIO44) is the ESP32-S3 default hardware UART0 RX pin, hardware UART0 serial output is disabled. Debug output is routed over native USB CDC (`-DARDUINO_USB_CDC_ON_BOOT=1 -DARDUINO_USB_MODE=1`). This guarantees that serial logging never toggles GPIO44 or corrupts display D/C signaling.
3. **Power & Ground Topology**:  
   - ILI9341 display VCC is wired to VBUS/5V. This assumes the display breakout board incorporates an onboard 3.3V low-dropout (LDO) regulator (such as XC6206 or RT9193) and 3.3V SPI logic compatibility.
   - Physical CS is hardwired to GND (permanently selected).  
   > [!IMPORTANT]
   > If hardware display desynchronization ever occurs on this specific ILI9341 module, report the condition rather than suggesting unapproved physical rewiring.

---

## 3. DORURU Persona & Display State System

The robot maintains a friendly, expressive personality named **DORURU** (never WALL-E branding). The display interface renders 13 distinct system states:

| State Enum | Title | Expression / Visual Feature | Description |
| :--- | :--- | :--- | :--- |
| `DISPLAY_STATE_BOOTING` | `BOOTING` | Horizontal slit eyes gently opening, animated progress bar | Displayed during bootloader and hardware peripheral initialization. |
| `DISPLAY_STATE_IDLE_READY` | `READY` | Big glowing Cyan rounded eyes with white pupil reflections; periodic natural eye blinking; resting smile | Standard idle state when ready for wake-word or motion commands. |
| `DISPLAY_STATE_WAKE_WORD_DETECTED` | `WAKE CONFIRMED` | Wide alert yellow/gold eyes with 4-point sparkle star accents | Triggered when wake phrase ("Hey DORURU") is detected. |
| `DISPLAY_STATE_LISTENING` | `LISTENING` | Attentive cyan eyes with 5-bar dynamic voice equalizer waveform | Shown while capturing user speech PCM utterance for transcription. |
| `DISPLAY_STATE_PROCESSING_THINKING`| `THINKING` | Thoughtful tilted eye with cycling 3-dot neural pulse | Displayed while local faster-whisper transcribes or Gemini Cloud reasons. |
| `DISPLAY_STATE_SPEAKING` | `SPEAKING` | Happy arched crescent eyes (`^_^`) with expanding speech mouth bar | Displayed while Piper TTS synthesizes speech and plays on I2S_NUM_1. |
| `DISPLAY_STATE_CAMERA_CAPTURE` | `VISION CAPTURE` | Yellow corner reticle brackets with center shutter aperture icon | Displayed when on-demand OV3660 camera frame capture is triggered. |
| `DISPLAY_STATE_VISION_PROCESSING` | `ANALYZING SCENE` | Viewfinder brackets with sweeping horizontal laser scan line | Displayed while transmitting JPEG payload to backend / Gemini multimodal. |
| `DISPLAY_STATE_VISION_SUCCESS` | `VISION COMPLETE` | Smiling eyes with green checkmark badge | Brief confirmation screen upon successful image recognition. |
| `DISPLAY_STATE_WIFI_DISCONNECTED` | `OFFLINE` | Sad droopy eyes with angled eyelids; prominent slashed Wi-Fi symbol | Displayed when Wi-Fi is lost; informs user that offline local safety mode is active. |
| `DISPLAY_STATE_ERROR` | `SYSTEM ALERT` | Bold red "X" crossed eyes with yellow/red warning triangle badge | Displays diagnostic error codes and messages without system freeze. |
| `DISPLAY_STATE_MOTOR_MOVING` | `MOTION ACTIVE` | Focused determined eyes with directional motion chevrons (`>>>`) | Warns bystanders that motors are currently in motion. |
| `DISPLAY_STATE_EMERGENCY_STOP` | `EMERGENCY STOP` | Flashing red/yellow alert border, bold octagonal STOP sign | Highest-priority screen shown when emergency stop locks all motors. |

---

## 4. Non-Blocking Architecture & Memory Safety

1. **Procedural Shape Rasterization**:  
   Rather than allocating a 153.6 KB full-screen double buffer in DRAM (which would compete with camera framebuffers and audio buffers), expressions are rendered procedurally using hardware-accelerated SPI drawing primitives (`fill_round_rect`, `fill_circle`, `draw_fast_h_line`). Memory overhead is near zero.
2. **Non-Blocking Cadence**:  
   `display_update()` is called inside `loop()` and throttled to 20 FPS (50ms interval). Only the dynamic sub-regions (e.g. blinking eyelids, equalizer bars, thinking dots, speech mouth) are redrawn, consuming less than 1.5ms per update. This prevents audio buffer starvation and watchdog timeouts.
3. **Safe Rendering Fallback**:  
   If an animation step encounters a rendering error (`display_set_render_error_simulation(true)`), the subsystem automatically activates `doruru_persona_render_fallback()`. This renders a high-contrast black/white screen with explicit state text, diagnostic messages, and confirmation that motor safety remains intact.

---

## 5. Display Demo / Test Mode

To verify screens on the bench without commanding physical motor motion:

- **Bench Serial Console**: Press `'D'` or `'d'` in the serial monitor to toggle Display Demo Mode.
- **Behavior**: Automatically cycles through all 13 states sequentially at a configurable cadence (default 1500ms):
  `BOOTING -> READY -> WAKE -> LISTENING -> THINKING -> SPEAKING -> CAPTURE -> ANALYZING -> SUCCESS -> MOVING -> OFFLINE -> ERROR -> E-STOP -> READY`
- **Motor Safety**: Demo mode operates strictly on the display; motor controllers remain in their safe `STOP` state with all H-bridge pins driven LOW.

---

## 6. Verification & Test Evidence

- **C++ Compilation**: Compiled cleanly with Clang++ (`tests/host_firmware_test.exe`) with static linking and zero warnings.
- **Host Unit Tests**: Section 9 in `tests/host_firmware_test.cpp` validates hardware reset pulse execution, state transitions across all 13 states, op counters, demo mode progression, and fallback screen recovery.
- **Python Unit Suite**: `tests/test_display_persona.py` verified 9/9 tests passing.
- **Regression Suite**: 71 unittest test cases and 28 pytest movement intent tests (99 total) passing 100%.

