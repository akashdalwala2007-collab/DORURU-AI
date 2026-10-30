# STACK.md — DORURU-AI Technology Stack

> **Status**: APPROVED  
> **Date**: 2026-10-30  

---

## 1. Embedded Firmware Stack (Tier 1: ESP32-S3 Sense)

| Subsystem | Technology / Library | Purpose / Notes |
| :--- | :--- | :--- |
| **Target Controller** | Seeed XIAO ESP32-S3 Sense | Dual-core Xtensa LX7 @ 240MHz, 8MB Octal PSRAM (OPI), Wi-Fi & BLE 5.0 |
| **Framework** | Arduino ESP32 / ESP-IDF | Target framework for peripheral management and Wi-Fi stack |
| **Serial Debug** | Native USB CDC | Configured with `ARDUINO_USB_CDC_ON_BOOT=1` to prevent UART0 D6/D7 pin conflict |
| **Display Library** | TFT_eSPI / Adafruit_ILI9341 | Custom SPI driver: SCK=9, MOSI=8, MISO=-1, CS=-1, DC=44, RST=7 |
| **Audio Capture** | ESP-IDF I2S PDM Driver | Dedicated to `I2S_NUM_0` reading onboard PDM mic on GPIO41/GPIO42 (16kHz 16-bit) |
| **Audio Output** | ESP-IDF I2S TX Driver | Dedicated to `I2S_NUM_1` driving MAX98357A on GPIO5/GPIO6/GPIO43 |
| **Camera Driver** | `esp_camera` (ESP32-Camera) | OV3660 configuration using internal DVP bus and 8MB OPI PSRAM framebuffers |
| **Motor Control** | ESP32 `ledc` PWM / GPIO | MX1508 dual H-bridge control with software safety timeout and emergency stop |
| **Wake Word** | ESP-SR / WakeNet (with PTT) | Onboard PDM wake-word evaluation with mandatory push-to-talk fallback |

---

## 2. Local Backend Stack (Tier 2: ASUS TUF A15)

| Subsystem | Technology | Purpose / Notes |
| :--- | :--- | :--- |
| **Runtime** | Python 3.12.11 / 3.14 | Core language for backend services |
| **Web Framework** | FastAPI (ASGI) + Uvicorn | High-concurrency async REST and WebSocket device API |
| **Validation** | Pydantic v2 | Strict schema validation for audio, vision, movement, and session contracts |
| **Local STT** | `faster-whisper` (CTranslate2) | Local speech-to-text; auto-detects CUDA (RTX 3050) with CPU `int8` fallback |
| **Local TTS** | `Piper` (ONNX Runtime) | Low-latency neural speech synthesis generating 16/22kHz PCM/WAV streams |
| **Embeddings & Search** | `sentence-transformers` / BM25 | College document chunk embedding (`all-MiniLM-L6-v2`) and local retrieval |
| **Session Cache** | In-Memory (Python `dict` / LRU) | Ephemeral, privacy-first session memory (10-minute expiry) |
| **Image Processing** | Pillow (PIL) | On-demand image normalization, dimension validation, and resizing |

---

## 3. Cloud Intelligence Stack (Tier 3: Google Cloud)

| Service | Technology | Purpose / Notes |
| :--- | :--- | :--- |
| **Reasoning & Vision** | Google Gemini API | Conversational intelligence and multimodal inspection |
| **Client SDK** | Official Google GenAI SDK | Secure server-side client consuming `GEMINI_API_KEY` from `.env` |
| **Model Selection** | Configurable via `.env` | Driven by `GEMINI_MODEL_NAME` (e.g. `gemini-2.5-flash`); never hardcoded |

---

## 4. Host Machine & Hardware Capabilities

| Component | Verified Specification | Status |
| :--- | :--- | :--- |
| **Host Machine** | ASUS TUF A15 Gaming Laptop | Development & local server target |
| **Operating System** | Windows 11 (PowerShell environment) | Verified |
| **GPU** | NVIDIA GeForce RTX 3050 Laptop GPU (4GB VRAM) | Verified via `nvidia-smi` (Driver 610.74, CUDA 13.3) |
| **Node.js & npm** | Node.js v24.16.0 / npm 11.13.0 | Verified |
| **Python** | Python 3.12.11 & Python 3.14.6 | Verified |
| **Version Control** | Git 2.56.0 | Verified (Local repository clean on branch `master`) |

---

*Last updated: 2026-10-30*

