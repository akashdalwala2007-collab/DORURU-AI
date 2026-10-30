# Phase 7: Local Speech: Faster-Whisper STT and Piper TTS — Plan

## Objective
Implement local, privacy-safe speech processing on the backend computer (ASUS TUF A15 development host, portable to a mini PC):
- Speech-to-Text (STT) using `faster-whisper` (CTranslate2) with automatic CUDA acceleration and CPU int8 fallback.
- Text-to-Speech (TTS) using `piper-tts` generating 16-bit PCM mono WAV audio formatted strictly for the ESP32 MAX98357A I2S DAC on `I2S_NUM_1`.
- Fast in-memory caching for reusable robotic speech utterances.
- Zero raw audio persistence to disk; zero user audio uploads to third-party clouds.
- Empirical latency benchmarking measuring cold-start and warm inference on actual machine hardware.

## Execution Steps
1. **Hardware & Environment Inspection**:
   - Inspect OS, CPU, RAM, GPU, and disk space on the ASUS TUF A15 development host without assuming CUDA availability.
   - Verify CUDA device support and CTranslate2 compute type capabilities.
2. **Dependency Installation**:
   - Install `faster-whisper` (CTranslate2, PyAV, ONNX Runtime) and `piper-tts`.
   - Update `backend/requirements.txt`.
3. **Voice Model Selection & Storage**:
   - Download Piper ONNX voice model (`en_US-lessac-medium.onnx` and config) into `backend/models/piper/`.
   - Update `.gitignore` so local model weights are never tracked in Git.
4. **Service Implementations**:
   - `FasterWhisperSTTService` implementing `STTService`:
     - Load model from `settings.STT_MODEL_PATH` (`base.en`).
     - Detect CUDA runtime support; fall back automatically to CPU int8 multi-threading if CUDA is unavailable or fails.
     - Validate audio format, duration (0.05s - 60s), size, and channels.
     - Format raw PCM payloads into in-memory WAV streams without disk persistence.
     - Protect with `asyncio.Semaphore(2)` and `settings.STT_TIMEOUT_SECONDS`.
   - `PiperTTSService` implementing `TTSService`:
     - Synthesize 16-bit signed PCM mono WAV audio at 22050Hz or 16000Hz matching MAX98357A I2S sink.
     - Implement in-memory bounded LRU cache for reusable robot utterances (e.g. status, confirmations).
     - Protect with `asyncio.Semaphore(2)` and `settings.TTS_TIMEOUT_SECONDS`.
     - Gracefully report missing model files (HTTP 503).
5. **FastAPI Backend Wiring**:
   - Update `app/main.py` (`create_app`) to initialize real speech services in development/production while preserving lightweight mocks in test runs.
   - Update `app/api/v1/audio.py` and `app/services/audio_store.py` to preserve audio delivery metadata (`sample_rate`, `channels`, `bit_depth`) for ESP32 streaming.
6. **Testing & Verification**:
   - Create comprehensive test suite `backend/tests/test_speech_services.py` covering format validation, corruption handling, PCM wrapping, live STT transcription, live TTS synthesis, contract compliance, caching, and 503 errors.
   - Run full regression suite (`pytest backend/tests -v`).
   - Run Ruff linter (`ruff check backend`).
7. **Empirical Benchmarking**:
   - Create `backend/scripts/benchmark_speech.py` and measure cold-start, warm inference, and cache hit latencies on the actual hardware.

