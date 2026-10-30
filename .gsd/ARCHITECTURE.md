# ARCHITECTURE.md — DORURU-AI System Architecture

> **System**: DORURU Interactive Robot & Lab Assistant  
> **Target Controller**: Seeed XIAO ESP32-S3 Sense  
> **Local Backend Host**: ASUS TUF A15 (Development Machine)  
> **Status**: APPROVED / ACTIVE  
> **Date**: 2026-10-30  

---

## 1. System Overview

DORURU is structured as a **Tri-Tier Hybrid Edge Architecture** that balances low-latency embedded control, high-throughput local AI processing, and cloud-scale conversational reasoning.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          TIER 1: DORURU EMBEDDED EDGE                           │
│                       (Seeed XIAO ESP32-S3 Sense)                               │
│                                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────────┐  │
│  │  ILI9341 Display│    │ MAX98357A Audio │    │    MX1508 Motor Driver      │  │
│  │ (Custom SPI)    │    │ (I2S_NUM_1)     │    │ (Local Timeout & E-Stop)    │  │
│  └────────▲────────┘    └────────▲────────┘    └──────────────▲──────────────┘  │
│           │                      │                            │                 │
│  ┌────────┴──────────────────────┴────────────────────────────┴──────────────┐  │
│  │                     ESP32-S3 Core & State Machine                         │  │
│  │   - Native USB CDC Debug Logging (UART0 Pin Conflict Bypass)              │  │
│  │   - 8MB Octal PSRAM (OPI) Memory Management                               │  │
│  │   - Local Wake-Word Engine (ESP-SR) / Push-to-Talk Fallback               │  │
│  │   - Local Safety Supervisor & Motor Boundary Enforcer                     │  │
│  └────────┬──────────────────────┬────────────────────────────▲──────────────┘  │
│           │                      │                            │                 │
│  ┌────────▼────────┐    ┌────────▼────────┐                   │                 │
│  │ Onboard PDM Mic │    │  OV3660 Camera  │                   │                 │
│  │ (I2S_NUM_0)     │    │ (On-Demand JPEG)│                   │                 │
│  └─────────────────┘    └─────────────────┘                   │                 │
└───────────────────────────────────┬───────────────────────────┼─────────────────┘
                                    │ Wi-Fi / Local REST / WS   │
                                    ▼                           │
┌───────────────────────────────────────────────────────────────┴─────────────────┐
│                        TIER 2: LOCAL BACKEND SERVER                             │
│                     (Python FastAPI on ASUS TUF A15)                            │
│                                                                                 │
│  ┌───────────────────────┐  ┌───────────────────────┐  ┌─────────────────────┐  │
│  │ Local Speech-to-Text  │  │ Local Text-to-Speech  │  │ College RAG Service │  │
│  │    (faster-whisper)   │  │        (Piper)        │  │ (Vector/BM25 Index) │  │
│  │  [CPU / CUDA Auto]    │  │   [Low-Latency ONNX]  │  │ [Verified Docs Only]│  │
│  └───────────▲───────────┘  └───────────▲───────────┘  └──────────▲──────────┘  │
│              │                          │                         │             │
│  ┌───────────┴──────────────────────────┴─────────────────────────┴──────────┐  │
│  │                   FastAPI AI Orchestration Engine                         │  │
│  │   - Device Authentication & Request Validation                            │  │
│  │   - Bounded Intent Parser (STOP / FORWARD / REVERSE / TURN)               │  │
│  │   - Session-Only In-Memory Conversation State                             │  │
│  │   - Vision Request Handler & Pre-processor                                │  │
│  └──────────────────────────────────────┬────────────────────────────────────┘  │
└─────────────────────────────────────────┼───────────────────────────────────────┘
                                          │ Secure HTTPS / TLS
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         TIER 3: CLOUD INTELLIGENCE                              │
│                          (Google Gemini API)                                    │
│                                                                                 │
│   - Configurable Model via Backend Environment Variables (never hardcoded)      │
│   - Multi-Turn Conversational Reasoning (Session-Scoped)                        │
│   - Grounded Response Generation using College Retrieved Evidence               │
│   - On-Demand Multimodal Image Inspection (OV3660 Still Frames)                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Confirmed Hardware Allocation and Fixed Pin Map

All pins are confirmed and locked. Wiring must be preserved exactly.

| Subsystem | Peripheral / Signal | Board Pin | ESP32-S3 GPIO | Bus / Interface | Hardware & Configuration Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Microphone** | PDM_DATA | Internal | **GPIO41** | `I2S_NUM_0` (PDM RX) | Reserved internal Sense pin. Dedicated to PDM audio capture. |
| **Microphone** | PDM_CLK | Internal | **GPIO42** | `I2S_NUM_0` (PDM RX) | Reserved internal Sense pin. Never reassign. |
| **Camera** | OV3660 Interface | Internal | Dedicated | DVP Camera Bus | Reserved internal Sense pins. Direct parallel DVP. |
| **Display** | RESET | **D8** | **GPIO7** | Custom SPI Control | Active-low reset pulse required at boot. |
| **Display** | D/C (Data/Command) | **D7** | **GPIO44** | Custom SPI Control | **UART0 RX Pin**. Prohibit UART0 serial logging. |
| **Display** | MOSI / SDI | **D9** | **GPIO8** | Custom SPI Data | Custom master-out slave-in SPI data line. |
| **Display** | SCK / CLK | **D10** | **GPIO9** | Custom SPI Clock | Custom SPI clock line. |
| **Display** | CS (Chip Select) | — | **GND** | Tied to GND | Physically grounded. Software configured with `CS = -1`. |
| **Display** | MISO | — | — | Not connected | Software configured with `MISO = -1`. |
| **Display** | VCC | 5V / VBUS | 5V Rail | Power | Valid only for breakout with onboard 3.3V LDO. |
| **Display** | LED | 3V3 | 3.3V Rail | Power | Display backlight supply. |
| **Audio Out** | DIN | **D4** | **GPIO5** | `I2S_NUM_1` (I2S TX) | Serial audio data to MAX98357A. |
| **Audio Out** | BCLK | **D5** | **GPIO6** | `I2S_NUM_1` (I2S TX) | Bit clock for audio output. |
| **Audio Out** | LRC | **D6** | **GPIO43** | `I2S_NUM_1` (I2S TX) | **UART0 TX Pin**. Prohibit UART0 serial logging. |
| **Audio Out** | VIN / GND | 3V3 / GND | 3.3V Rail | Power | MAX98357A logic/amp power and ground reference. |
| **Motors** | IN1 | **D3** | **GPIO4** | MX1508 H-Bridge | Motor A control 1. |
| **Motors** | IN2 | **D2** | **GPIO3** | MX1508 H-Bridge | Motor A control 2. |
| **Motors** | IN3 | **D1** | **GPIO2** | MX1508 H-Bridge | Motor B control 1. |
| **Motors** | IN4 | **D0** | **GPIO1** | MX1508 H-Bridge | Motor B control 2. |

### Critical Hardware Constraint Rules:
1. **UART0 Pin Conflict**: D6 (GPIO43) and D7 (GPIO44) are the ESP32-S3 default UART0 TX/RX pins. Using hardware UART0 serial output toggles these pins and corrupts both display commands and speaker audio. Serial logging must use native USB CDC (`ARDUINO_USB_CDC_ON_BOOT=1`).
2. **Dual I2S Peripheral Separation**: On ESP32-S3, PDM RX hardware is strictly tied to `I2S_NUM_0`. Therefore:
   - `I2S_NUM_0` = Reserved strictly for Onboard PDM Microphone (`GPIO41`/`GPIO42`).
   - `I2S_NUM_1` = Reserved strictly for MAX98357A Speaker Amplifier (`GPIO5`/`GPIO6`/`GPIO43`).
3. **Custom SPI Routing**: Standard board SPI macros default to different pins. Software display initialization must explicitly configure: `SCK=GPIO9`, `MOSI=GPIO8`, `MISO=-1`, `CS=-1`, `DC=GPIO44`, `RST=GPIO7`.
4. **8MB Octal PSRAM (OPI)**: Essential for OV3660 JPEG framebuffers and audio buffers. Build configuration must enable OPI PSRAM (`board_build.arduino.memory_type = qio_opi`, `-DBOARD_HAS_PSRAM`). Boot code must verify PSRAM size at runtime.

---

## 3. Hardware Power and Electrical Safety

> [!WARNING]
> **ELECTRICAL VERIFICATION MANDATE**: Software safety routines mitigate errors but CANNOT replace physical hardware verification. The following items are documented as **UNRESOLVED** and require physical multimeter testing and datasheet confirmation before high-load operations.

### Unresolved Electrical Verification Items
1. **Motor Rated Voltage & Stall Current**:
   - Product reference screenshot shows a 3V N20 micro turbo worm geared motor (16 RPM).
   - *Unresolved*: Verify whether both installed physical motors match this specification or differ.
   - *Unresolved*: Measure no-load current (~30mA–60mA) and stall current (~300mA–1.0A at 3V–5V) for both motors using a multimeter/bench supply.
2. **MX1508 Driver Ratings vs Motor Demand**:
   - The MX1508 dual H-bridge operates from 2V to 10V with rated continuous current ~800mA and peak current ~1.5A–2.5A per channel.
   - *Unresolved*: Verify that motor stall current does not exceed MX1508 thermal or peak limits.
   - *Unresolved*: Verify if heatsinking or thermal relief is required under load.
3. **Battery Chemistry and Discharge Ratings**:
   - *Unresolved*: Identify battery chemistry (1S Li-Ion/LiPo 3.7V nominal / 4.2V max, 2S 7.4V nominal, or NiMH pack).
   - *Unresolved*: Verify continuous and burst C-rating discharge capability to confirm whether battery can support simultaneous ESP32-S3 RF bursts (~350mA peak) + motor inrush current + MAX98357A audio peaks (~500mA peak) without voltage collapse.
4. **Voltage Regulator & Distribution Topology**:
   - *Unresolved*: Determine if an external step-down (buck) or step-up/step-down regulator is installed to supply 5V to the ESP32 VBUS/5V pin and display, or if a separate regulator feeds the MX1508 motor supply (VM).
   - *Unresolved*: Thermal limits and maximum current rating of onboard and external voltage regulators.
5. **Common Ground Integrity**:
   - *Mandatory*: A clean, low-impedance common ground reference must connect battery negative, motor driver GND, ESP32 GND, display GND, and audio amplifier GND to prevent ground loops and erratic SPI/I2S logic levels.
6. **ESP32 3.3V/5V Stability & Brownout Risk**:
   - Inductive motor startup, stall, or fast direction reversal generates substantial back-EMF and instantaneous voltage dips.
   - *Risk*: Voltage sag on the ESP32 3.3V rail below ~2.8V trips the ESP32-S3 brownout detector, triggering an uncontrolled reboot loop.
   - *Unresolved*: Check for sufficient decoupling capacitors (e.g., 100uF–470uF low-ESR electrolytic across motor supply rails, 100nF ceramic near driver and logic rails).
7. **Cross-Rail Voltage Compatibility**:
   - ILI9341 display VCC is wired to 5V/VBUS. This is acceptable ONLY if the breakout board integrates an onboard 3.3V LDO regulator (e.g., XC6206 / RT9193) and level-shifting or 3.3V-tolerant SPI logic inputs.
   - Display LED backlight is powered from 3.3V.
   - MAX98357A VIN is powered from 3.3V (acceptable, operating down to 2.5V with ~1W output into 8 ohms).

### Strict Electrical Rules
1. **Never power motors directly from the ESP32 3.3V pin** (the onboard 3.3V LDO cannot supply inductive motor current).
2. **Do not invent battery ratings, regulator specs, or motor current values** without physical confirmation.
3. **Do not declare the power distribution system electrically safe** until component datasheets and measurements are verified.
4. **Preserve existing physical wiring** unless a genuine electrical hazard is proven and the user approves.
5. **Never allow software assumptions to replace electrical verification**.

---

## 4. Subsystem Responsibilities

```
┌───────────────────────────────────┬───────────────────────────────────┬───────────────────────────────────┐
│     TIER 1: ESP32-S3 FIRMWARE     │      TIER 2: LOCAL FASTAPI        │       TIER 3: GEMINI CLOUD        │
├───────────────────────────────────┼───────────────────────────────────┼───────────────────────────────────┤
│ • Hardware peripheral init        │ • FastAPI HTTP/WS server          │ • High-level conversational AI    │
│ • Custom SPI display rendering    │ • Local faster-whisper STT        │ • Complex semantic reasoning      │
│ • MAX98357A audio playback        │ • Local Piper TTS                 │ • Multimodal image interpretation │
│ • PDM microphone audio capture    │ • College RAG document index      │ • Context-grounded institutional  │
│ • Local wake-word / PTT trigger   │ • Vector/lexical text search      │   question answering              │
│ • OV3660 camera frame capture     │ • Intent normalization & bounds   │                                   │
│ • MX1508 motor PWM/direction      │ • In-memory session lifecycle     │                                   │
│ • Hard motor safety timeouts      │ • Device authentication check     │                                   │
│ • Local physical emergency stop   │ • Vision resizing & staging       │                                   │
│ • Wi-Fi connection & telemetry    │ • Gemini API client management    │                                   │
│ • Offline fallback display/stop   │                                   │                                   │
└───────────────────────────────────┴───────────────────────────────────┴───────────────────────────────────┘
```

---

## 5. End-to-End System Flows

### A. High-Level Voice Interaction Flow
1. **Wake Trigger**: Local wake-word engine on ESP32 (`I2S_NUM_0`) detects wake phrase, OR push-to-talk button/serial fallback is triggered.
2. **Audio Capture**: ESP32 switches display to "Listening" and captures 16kHz 16-bit mono PCM utterance into a bounded ringbuffer.
3. **Upload to Local Server**: ESP32 posts binary PCM audio to FastAPI `/api/v1/voice/transcribe`.
4. **Local STT**: Backend runs `faster-whisper` (on CPU or CUDA depending on verified host capability), producing text transcript.
5. **Orchestrator Routing**:
   - If user query is a physical motion intent (e.g. "go forward", "stop") -> routes to Movement Intent Layer.
   - If user query is a visual inspection request -> triggers On-Demand Vision Flow.
   - If user query is college-specific -> queries College Knowledge Base (RAG) and passes context + query to Gemini API.
   - If general inquiry -> passes conversation history + query to Gemini API.
6. **Gemini Reasoning**: Cloud Gemini API generates concise conversational reply.
7. **Local TTS**: Backend synthesizes voice using local `Piper` ONNX model into 16kHz/22kHz PCM/WAV.
8. **Audio Streaming & Playback**: Backend delivers synthesized audio stream to ESP32; ESP32 routes stream directly to `I2S_NUM_1` (MAX98357A) while displaying "Speaking" persona.

### B. High-Level Vision Flow
1. **Trigger**: Explicit user voice command (e.g., "DORURU, look at this") or configured administrative trigger.
2. **Capture**: ESP32 displays "Camera Capture", captures single frame from OV3660 in PSRAM framebuffer as JPEG.
3. **Local Ingestion**: Frame transmitted to backend `/api/v1/vision/analyze` via multipart POST.
4. **Gemini Multimodal Call**: Backend stages image with user prompt and dispatches to Gemini API using configured model.
5. **Speech Response**: Gemini description is synthesized via local Piper TTS and played back through DORURU's speaker.
6. **Buffer Release**: Framebuffer immediately released from ESP32 PSRAM and backend memory. No continuous streaming.

### C. Bounded Movement Safety Flow
1. **Intent Extraction**: User voice command parsed into strict enum (`STOP`, `FORWARD`, `REVERSE`, `TURN_LEFT`, `TURN_RIGHT`).
2. **Server-Side Validation**: Backend verifies duration bounds (`duration_ms <= 3000`) and issues structured signed command packet.
3. **ESP32 Local Validation**: Firmware validates command envelope, enforces maximum allowable duration and PWM duty cycle limit.
4. **Execution & Hardware Timeout**: Firmware drives MX1508 H-bridge while arming a hardware watchdog timer.
5. **Autonomous Stop**: Motors stop immediately upon timeout expiration, Wi-Fi signal loss, or local emergency stop invocation.

---

## 6. Autonomy Levels and Unconfirmed Navigation Hardware

Autonomous navigation is strictly gated by physical sensor availability:

| Autonomy Level | Description | Hardware Requirements | DORURU Status |
| :--- | :--- | :--- | :--- |
| **Level 1** | **Bounded Timed Motion** | MX1508 + DC Motors | **ACTIVE / SUPPORTED** (Approximate open-loop movement with strict software timeouts) |
| **Level 2** | **Obstacle-Aware Motion** | Level 1 + Distance Sensors (ToF / Ultrasonic) | **DISABLED / UNCONFIRMED** (Sensor interfaces stubbed with safe disabled default) |
| **Level 3** | **Odometry-Based Navigation** | Level 2 + Wheel Encoders | **DISABLED / UNCONFIRMED** (Encoders not physically installed) |
| **Level 4** | **Target Tracking / Autonomous SLAM**| Level 3 + LiDAR / 3D Vision / Tracking Sensor | **DISABLED / OUT OF SCOPE** (Standard OV3660 camera cannot provide safe autonomous SLAM) |

---

## 7. College Knowledge Base & RAG Architecture

1. **Verified Sources Only**: Ingests user-supplied Markdown, text, and PDF files placed in `knowledge_base/documents/`. Hallucination of college history, dates, leadership, or statistics is strictly forbidden.
2. **Chunking & Indexing**: Documents chunked with overlap; indexed using lightweight embeddings (`all-MiniLM-L6-v2`) or BM25 lexical search.
3. **Retrieval Grounding**: For college-related questions, top-$K$ evidence chunks are injected into the Gemini system prompt:
   > *"Answer the question using ONLY the provided verified college context. If the answer cannot be found in the context, state clearly that the information is not verified in official records."*
4. **Source Attribution**: Response metadata includes file name and section reference for transparent auditability.

---

## 8. Session-Only Conversation Lifecycle

- **Ephemeral Storage**: Conversation state exists exclusively in volatile memory (`dict` / LRU session cache in FastAPI process).
- **Session Lifecycle**:
  - Automatically expires after 10 minutes of inactivity.
  - Cleared immediately upon explicit "Reset" command or backend process restart.
- **Privacy Enforcement**: No conversation transcripts, user audio recordings, or captured images written to permanent disk storage by default.

---

## 9. Offline Fallback & Fault Recovery

When local Wi-Fi or backend server connectivity is lost:
1. **Motors Safe Stop**: All motor outputs instantly set to LOW; active timers cancelled.
2. **TFT UI State**: Display transitions to "Wi-Fi Disconnected / Offline" indicator.
3. **Local Actions Only**: Only local emergency stop and hardwired test diagnostics remain responsive.
4. **Reconnection & Replay Prevention**: Upon Wi-Fi reconnection, stale queued commands are purged to prevent unexpected motor activation.

---

## 10. Secrets, Privacy, and Environment Configuration

1. **Server-Side API Key Isolation**: Google Gemini API key is maintained strictly in backend `.env`; never compiled into ESP32 firmware or exposed to client endpoints.
2. **Configurable Model Name**: Gemini model identifier is loaded exclusively from `GEMINI_MODEL_NAME` in `.env` (defaulting to e.g. `gemini-2.5-flash`), allowing zero-downtime updates as Google upgrades models.
3. **Local Audio Privacy**: Microphone data is processed on the local LAN backend (ASUS TUF A15). No microphone audio is transmitted to cloud services.
4. **Git Protection**: `.env`, credentials, certificates, temporary audio/image buffers, and binary files are strictly excluded via `.gitignore`.

---

## 11. Phase Dependency Graph

```
Phase 1: Repository Audit, GSD Baseline & Electrical Safety Plan
    │
    ▼
Phase 2: Firmware Foundation (USB CDC, OPI PSRAM, Custom SPI, Dual I2S Allocation, Reserved Pins)
    ├────────────────────────────────┼──────────────────────────────┐
    ▼                                ▼                              ▼
Phase 3: Motor Control & Safety   Phase 4: TFT UI & Persona      Phase 5: OV3660 Camera Capture
    │                                │                              │
    └────────────────────────────────┼──────────────────────────────┘
                                     ▼
Phase 6: FastAPI Backend Foundation & Device API
    ├────────────────────────────────┼──────────────────────────────┐
    ▼                                ▼                              ▼
Phase 7: Local STT/TTS            Phase 8: Gemini Orchestration  Phase 11: Hybrid Vision Flow
(faster-whisper & Piper)         (Env-Configured Model)         (Depends on P5 + P6 + P8)
    │                                │
    │                                ├───► Phase 9: College RAG Knowledge Base
    │                                │
    ▼                                ▼
Phase 10: Local Wake-Word & Voice State Machine (Depends on P2, P6, P7, P8)
    │
    ▼
Phase 12: Movement Intent & Autonomy Readiness (Depends on P3, P6, P8)
    │
    ▼
Phase 13: Offline Fallback & Recovery (Depends on P2, P3, P4, P6, P7, P8, P10, P12)
    │
    ▼
Phase 14: Full System Integration & Manual Verification Checklist
    │
    ▼
Phase 15: GSD Security, Quality, and Release Audit
```

---

## 12. Risks, Assumptions, and Open Decisions

| Item | Type | Impact | Mitigation Strategy |
| :--- | :--- | :--- | :--- |
| **D6/D7 UART0 Conflict** | Known Hardware Risk | Display glitches, speaker audio corruption | Mandatory native USB CDC logging; hardware UART0 disabled in firmware. |
| **I2S Concurrent Usage** | Framework Risk | DMA lockup or peripheral bus collision | Dedicate `I2S_NUM_0` to PDM mic and `I2S_NUM_1` to MAX98357A; verify framework drivers. |
| **Display CS Tied to GND** | Electrical Risk | Display controller SPI desync on reset | Software configured with `CS = -1`; emit hard reset pulse on D8 (GPIO7) at boot. |
| **ESP-SR PDM Compatibility**| Embedded AI Risk | Wake-word engine failing on PDM input | Maintain push-to-talk / manual trigger fallback at all times. |
| **Motor Stall Brownout** | Power Safety Risk | ESP32-S3 brownout resets under load | Independent motor power rail, common ground, decoupling capacitors, software current ramps. |
| **GPU / CUDA Availability** | Backend Risk | STT latency degradation on CPU | Verify NVIDIA RTX 3050 driver runtime; provide automatic fallback to `int8` CPU inference. |

---

*Last updated: 2026-10-30*

