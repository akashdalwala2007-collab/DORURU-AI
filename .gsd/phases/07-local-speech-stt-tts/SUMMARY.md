# Phase 7: Local Speech: Faster-Whisper STT and Piper TTS — Summary

## Execution Overview
Phase 7 has been successfully implemented on the ASUS TUF A15 development host with full hardware inspection, local STT via `faster-whisper`, local TTS via `piper-tts`, ESP32 MAX98357A delivery contract compliance, automated regression testing (58/58 tests passing), and real latency benchmarking.

---

## 1. Hardware Inspection & Telemetry (ASUS TUF A15)
- **OS**: Windows 11 Pro 64-bit (Build 10.0.26200)
- **CPU**: AMD Ryzen 7 250 (8 cores, 16 logical threads, AVX-512/AVX2)
- **RAM**: 24 GB visible (~8.2 GB free)
- **GPU**: NVIDIA GeForce RTX 5050 Laptop GPU (8151 MiB VRAM, Driver 621.01, CUDA UMD 13.5)
- **Storage**: C: drive (~49 GB free space)
- **Compute Selection**: CUDA acceleration verified and operational with `float16` precision; automatic CPU fallback with `int8` precision and multi-threading verified.

---

## 2. Key Implementations

### Faster-Whisper STT Service (`backend/app/services/stt_service.py`)
- Implements `STTService` abstract interface.
- **Dynamic Device Detection**: Tests CUDA `float16` initialization on the NVIDIA RTX 5050; automatically catches runtime exceptions (such as missing cuDNN DLLs) and gracefully falls back to CPU `int8` with 8 worker threads.
- **Audio Validation & Preprocessing**:
  - In-memory inspection of RIFF WAV containers via `wave` module.
  - Duration boundaries enforced: minimum 0.05 seconds, maximum 60 seconds.
  - Headless raw PCM audio (`audio/pcm`, `audio/raw`) automatically wrapped into standard WAV container in-memory without disk persistence.
  - Rejects empty payloads (`EMPTY_AUDIO_PAYLOAD`), short payloads (`AUDIO_TOO_SHORT`), overly long payloads (`AUDIO_TOO_LONG`), and corrupt headers (`CORRUPT_AUDIO_PAYLOAD`).
- **Concurrency & Resource Protection**:
  - Guarded by `asyncio.Semaphore(2)` preventing memory/compute exhaustion.
  - Offloaded to `asyncio.to_thread` with timeout protection (`settings.STT_TIMEOUT_SECONDS`).
- **Privacy Assurance**: Audio bytes are held strictly in transient memory buffers and discarded after transcription; zero audio is uploaded to Gemini or cloud providers.

### Piper TTS Service (`backend/app/services/tts_service.py`)
- Implements `TTSService` abstract interface.
- **Voice Model**: Local ONNX model `en_US-lessac-medium.onnx` with configuration `en_US-lessac-medium.onnx.json` downloaded into `backend/models/piper/` (gitignored).
- **ESP32 MAX98357A Contract**: Generates standard 16-bit signed PCM mono WAV audio at 22050Hz (or 16000Hz) matching the I2S decoder specifications on `I2S_NUM_1` (`DIN=GPIO5`, `BCLK=GPIO6`, `LRC=GPIO43`).
- **In-Memory Speech Cache**: Bounded LRU cache (100 items) keyed by `sha256(voice + text)`:
  - Common phrases (e.g., greetings, status messages, emergency stop warnings) are served in **0.032 ms**.
  - Returns a unique `audio_id` per synthesis request to ensure stream isolation while reusing cached audio data.
- **Concurrency & Error Handling**: Guarded by `asyncio.Semaphore(2)` and `settings.TTS_TIMEOUT_SECONDS`; gracefully reports `TTS_MODEL_NOT_FOUND` (HTTP 503) when model files are absent.

### Transient Audio Streaming & Backend Integration
- `backend/app/services/audio_store.py`: Preserves delivery metadata (`sample_rate`, `channels`, `bit_depth`) in transient `AudioBuffer`.
- `backend/app/api/v1/audio.py`: Streams audio to ESP32 with accurate `X-Audio-Sample-Rate`, `X-Audio-Channels`, and `X-Audio-Bit-Depth` response headers.
- `backend/app/main.py`: Dynamically initializes real `FasterWhisperSTTService` and `PiperTTSService` in production/development, with mock fallback during fast testing.

---

## 3. Empirical Latency Benchmark Results
Benchmarked using `backend/scripts/benchmark_speech.py` on the ASUS TUF A15 development host:

### Text-to-Speech (Piper ONNX)
| Test Case | Text Length | Generated Audio | Average Latency | Real-Time Factor (RTF) |
| :--- | :--- | :--- | :--- | :--- |
| **Cold Start** | Model load from disk | N/A | **3508.57 ms** | N/A |
| **Short Utterance** | 4 words ("Hello, I am DORURU.") | 1490 ms | **55.39 ms** | **0.037x** (27x faster than real-time) |
| **Medium Utterance** | 10 words ("The autonomous robotics...") | 3436 ms | **105.08 ms** | **0.031x** (32x faster than real-time) |
| **Long Utterance** | 20 words ("DORURU is an autonomous...") | 8582 ms | **287.32 ms** | **0.033x** (30x faster than real-time) |
| **Cache Hit** | Reusable robot phrase | 1800 ms | **0.032 ms** | **< 0.0001x** (instantaneous) |

### Speech-to-Text (Faster-Whisper `base.en`)
#### Active Mode: CUDA Acceleration (NVIDIA RTX 5050 Laptop GPU, float16)
| Audio Duration | Iterations | Average Latency | Min Latency | Max Latency | Real-Time Factor (RTF) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Cold Start** | Model load into VRAM | **1013.38 ms** | N/A | N/A | N/A |
| **1.0 second clip** | 5 runs | **33.96 ms** | 29.58 ms | 44.88 ms | **0.034x** (29x faster than real-time) |
| **2.0 second clip** | 5 runs | **34.99 ms** | 32.73 ms | 38.49 ms | **0.017x** (57x faster than real-time) |
| **4.0 second clip** | 5 runs | **39.00 ms** | 36.92 ms | 40.47 ms | **0.010x** (102x faster than real-time) |

#### Fallback Mode: CPU Execution (AMD Ryzen 7 250, int8 multi-threaded)
| Audio Duration | Iterations | Average Latency | Real-Time Factor (RTF) |
| :--- | :--- | :--- | :--- |
| **1.0 second clip** | 5 runs | **45.42 ms** | **0.045x** |
| **2.0 second clip** | 5 runs | **43.76 ms** | **0.022x** |
| **4.0 second clip** | 5 runs | **45.51 ms** | **0.011x** |

---

## 4. Verification & Testing Evidence
1. **Unit & Integration Tests**:
   - `backend/tests/test_speech_services.py`: 10/10 tests passed.
   - Full regression suite: **58/58 tests passed** across all backend test modules.
2. **Code Quality**:
   - `ruff check backend`: All checks passed cleanly with 0 errors.
3. **Firmware Compilation (Phase 4)**:
   - PlatformIO build for `seeed_xiao_esp32s3` passed with code 0 (`RAM: 7.0%`, `Flash: 10.3%`).
4. **Git Cleanliness**:
   - Zero commits or pushes created.
   - Model weights (`.onnx`, `.onnx.json`) and `.env` strictly ignored by `.gitignore`.

