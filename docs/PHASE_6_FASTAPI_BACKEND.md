# PHASE 6: FASTAPI BACKEND FOUNDATION AND DEVICE API

> **Subsystem**: Unified FastAPI + Flask Backend & Device API  
> **Development Host**: ASUS TUF A15 Gaming Laptop (Portable to Mini PC)  
> **Status**: Verified & Integrated  
> **Milestone**: DORURU-AI v1.0  

---

## 1. Subsystem Architecture Overview

Phase 6 implements DORURU's high-performance Python backend. Built initially for the ASUS TUF Gaming A15 laptop (Ryzen 7 / RTX 3050 mobile) and portable to lightweight mini PCs, the backend provides an asynchronous, schema-validated device communication layer for the Seeed XIAO ESP32-S3 Sense robot.

The backend leverages a **Dual ASGI/WSGI Bridged Architecture**:
- **FastAPI (ASGI)**: High-throughput, asynchronous API powering device authentication, local speech transcription (STT), speech synthesis (TTS), unified voice query orchestration, bounded movement intent dispatch, and ephemeral session lifecycle management.
- **Flask (WSGI)**: Legacy and specialized endpoints for ephemeral camera vision transport, College RAG ingestion, and hardware clock synchronization mounted seamlessly onto FastAPI via `WSGIMiddleware`.
- **Zero Database Requirement**: All conversation turns, movement state counters, and device sessions reside strictly in volatile, thread-safe in-memory data structures that expire after inactivity.

```
┌────────────────────────────────────────────────────────────────────────┐
│             DORURU UNIFIED LOCAL BACKEND ARCHITECTURE (PORT 8000)      │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  [ ESP32-S3 Sense ] ──(Wi-Fi / HTTP / Bearer / X-Device-Token)───╮     │
│                                                                  │     │
│  FastAPI Root Application (ASGI / Uvicorn)                       │     │
│  ├── /health & /api/v1/health          ── Health & Telemetry     │     │
│  ├── /api/v1/device/register           ── Per-device Auth        │     │
│  ├── /api/v1/voice/transcribe          ── Local STT Upload       │     │
│  ├── /api/v1/voice/synthesize          ── Local TTS Synthesis    │     │
│  ├── /api/v1/voice/query               ── Conversational Triage  │     │
│  │   ├── 1. Movement Intent Parser     ── Bounded Motion (L1)    │     │
│  │   ├── 2. College RAG Pipeline       ── Grounded Campus Info   │     │
│  │   └── 3. Gemini Reasoning Service   ── DORURU Robot Persona   │     │
│  ├── /api/v1/session/new, /status, /reset ── Ephemeral Lifecycle │     │
│  │                                                               │     │
│  └── WSGIMiddleware (Mounted at /)                               │     │
│      └── Flask WSGI App                                          │     │
│          ├── /api/v1/vision/upload     ── Ephemeral JPEG Buffer  │     │
│          └── /api/v1/knowledge/query   ── College Document RAG   │     │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Configuration & Secrets Management

Configuration is strictly environment-driven via `backend/app/config.py` and `.env.example`. Hardcoded models, credentials, and tokens are prohibited.

### 2.1 Key Environment Variables

| Variable | Default Value | Description | Safety Rule |
| :--- | :--- | :--- | :--- |
| `GEMINI_API_KEY` | `""` | Google AI Studio Gemini API Key | Server-side only; never committed to Git |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Configurable multimodal model | Never hardcoded; dynamic selection |
| `DORURU_DEVICE_TOKEN` | `""` | Shared device authentication token | Verified via constant-time HMAC |
| `DORURU_ALLOWED_DEVICES` | `DORURU-SENSE-01,DORURU-DEV` | Comma-separated device ID allowlist | Rejects unknown hardware (403) |
| `STT_MODEL_SIZE` | `base` | faster-whisper model size / weights | Runs locally on host machine |
| `STT_DEVICE` | `cpu` | STT compute device (`cpu` or `cuda`) | Auto-detects CUDA; falls back to CPU |
| `STT_COMPUTE_TYPE` | `int8` | Model precision (`int8`, `float16`) | Optimized for laptop / mini PC CPU |
| `PIPER_EXECUTABLE_PATH`| `piper` | Path to local Piper binary | Synthesizes offline speech |
| `PIPER_MODEL_PATH` | `models/piper/en_US-lessac-medium.onnx` | ONNX voice model path | Offline TTS |
| `SESSION_EXPIRY_SECONDS`| `900` | Inactivity TTL (15 minutes) | Purges memory to avoid leakage |
| `MAX_AUDIO_PAYLOAD_BYTES`| `10485760` (10MB)| Audio upload payload ceiling | Protects host memory from overflow |
| `MAX_IMAGE_PAYLOAD_BYTES`| `2097152` (2MB) | Camera frame upload ceiling | Rejects oversized JPEG frames (413) |

---

## 3. Structured Logging Architecture

Implemented in `backend/app/logging_config.py`, the system configures standardized JSON and console logging under the `doruru.backend` hierarchy:
- **Timestamped ISO 8601 UTC Logs**: Every request, endpoint dispatch, and hardware state transition logs timestamp, log level, and component tag.
- **Sensitive Data Redaction**: Automatically suppresses API keys, device bearer tokens, and binary audio/image buffers from log outputs.
- **Performance Profiling**: Captures latency in milliseconds (`latency_ms`) across STT transcription, RAG retrieval, Gemini generation, and TTS synthesis.

---

## 4. Pydantic Request & Response Schemas

All FastAPI endpoints validate input payloads using strict Pydantic models in `backend/app/schemas/`:

1. **Device Identity (`schemas/device.py`)**:
   - `DeviceRegisterRequest`: `device_id: str`, `firmware_version: str`, `mac_address: Optional[str]`, `hardware_type: str`.
   - `DeviceRegisterResponse`: `status: str`, `device_id: str`, `session_token: str`, `server_time_utc: float`, `keepalive_interval_seconds: int`.
2. **Speech & Audio Delivery (`schemas/voice.py`)**:
   - `AudioTranscribeResponse`: `status: str`, `text: str`, `duration_seconds: float`, `confidence: float`, `language: str`, `model: str`.
   - `AudioDeliveryContract`: Exact 16kHz 16-bit mono PCM/WAV payload parameters matching the MAX98357A I2S hardware sink.
   - `VoiceQueryRequest`: `query: str`, `session_id: Optional[str]`, `include_audio: bool = True`.
   - `VoiceQueryResponse`: `status: str`, `answer: str`, `query_type: str`, `session_id: str`, `movement_command: Optional[dict]`, `audio_delivery: Optional[AudioDeliveryContract]`, `latency_ms: float`.
   - `TextToSpeechRequest`: `text: str` (min 1, max 2000 chars), `voice_id: Optional[str]`, `sample_rate: int = 16000`.
3. **Session Lifecycle (`schemas/session.py`)**:
   - `SessionCreateRequest`: `ttl_seconds: Optional[int]` (validated integer between 1 and 86400, rejecting boolean inputs).
   - `SessionCreateResponse`: `status: str`, `session_id: str`, `created_at: float`, `ttl_seconds: int`.
   - `SessionStatusResponse`: `session_id: str`, `turns_count: int`, `is_expired: bool`, `active_sessions_count: int`.
   - `SessionResetRequest`: `session_id: str`.

---

## 5. Device Authentication & Security

Implemented in `backend/app/routers/deps.py`:
- **Dual Header Support**: Accepts `X-Device-Token` header or `Authorization: Bearer <token>`.
- **Constant-Time Verification**: Uses `hmac.compare_digest` to prevent timing side-channel attacks against device secrets.
- **Allowlist Enforced**: Registration against `/api/v1/device/register` verifies `device_id` against `DORURU_ALLOWED_DEVICES`. Unauthorized IDs are rejected with `403 Forbidden`. Missing or invalid tokens return `401 Unauthorized`.

---

## 6. Service Interfaces & Processing Pipeline

### 6.1 Speech-to-Text Interface (`backend/app/services/stt_service.py`)
- `BaseSTTService` abstract interface.
- `FasterWhisperSTTService`: Runs local `faster-whisper` with automatic CUDA GPU detection. If CUDA is unavailable, falls back to CPU execution with `int8` quantization.
- Resilient Fallback: If `faster_whisper` is uninstalled or models are downloading, operates in mock fallback mode so test suites and integration benches do not crash.

### 6.2 Text-to-Speech Interface (`backend/app/services/tts_service.py`)
- `BaseTTSService` abstract interface.
- `PiperTTSService`: Synthesizes offline speech using the local Piper executable and ONNX model.
- **Audio Delivery Contract**: Strictly formats output as **16,000 Hz, 16-bit, Single Channel (Mono) Linear PCM / WAV**. This matches the exact configuration of DORURU's MAX98357A I2S amplifier (`I2S_NUM_1`, `BCLK=GPIO6, LRC=GPIO43, DIN=GPIO5`).

### 6.3 Gemini Reasoning & Robot Persona (`backend/app/services/gemini_service.py`)
- `BaseGeminiService` abstract interface.
- `GeminiChatService`: Connects to Google GenAI SDK using `config.GEMINI_MODEL`.
- **Persona Prompt**: Embeds DORURU's persona instructions — helpful, concise campus robotic companion, friendly tone, no fictional wall-following or false continuous autonomy claims, disclaiming Level 2-4 autonomy when unverified.

---

## 7. Unified Conversational Query Orchestrator

The endpoint `POST /api/v1/voice/query` orchestrates natural robot interactions through a three-stage triage:

```
User Query ("turn left", "where is library", "what is quantum computing")
       │
       ▼
1. Movement Intent Check (MovementIntentParser)
   ├── Match STOP, FORWARD, REVERSE, TURN_LEFT, TURN_RIGHT
   └── If matched: Execute bounded Level 1 motion packet + synthesize confirmation
       │
       ▼ (If not a movement intent)
2. College Knowledge Base Check (CollegeRAGService)
   ├── Match institutional campus keywords / course info / admissions
   └── If matched: Return grounded response with document citations
       │
       ▼ (If general question)
3. Gemini General Reasoning (GeminiChatService)
   └── Generate conversational response adhering to DORURU persona
```

If `include_audio=True`, the orchestrator attaches base64-encoded 16kHz WAV audio conforming to the audio delivery contract for direct speaker playback on the robot.

---

## 8. Ephemeral Session Lifecycle

Implemented in `backend/app/session/session_manager.py` and `backend/app/routers/session.py`:
- `create_session(ttl_seconds)`: Issues a new UUID session token with configurable inactivity TTL.
- `touch()` / `add_message()`: Tracks conversation turns and updates timestamp.
- Expiration: When `(now - last_activity_at) > ttl_seconds`, session is purged on next access or cleanup cycle.
- `reset_session()`: Explicitly wipes all conversation history and temporary context, issuing a fresh clean session.
- Thread-Safe: Protected by `threading.Lock` across concurrent robot requests.

---

## 9. Verification & Test Evidence

All unit and integration tests execute successfully:

```
Test Suite Execution Results:
======================================================================
1. FastAPI Backend Test Suite (tests/test_fastapi_backend.py):
   - test_environment_driven_configuration        ... OK
   - test_health_check_endpoints                  ... OK
   - test_device_registration_success             ... OK
   - test_device_registration_unauthorized        ... OK
   - test_device_registration_forbidden_device_id ... OK
   - test_audio_transcribe_success                ... OK
   - test_audio_transcribe_unauthorized           ... OK
   - test_audio_transcribe_oversized_payload      ... OK (413)
   - test_audio_transcribe_unsupported_media_type ... OK (415)
   - test_voice_query_movement_routing            ... OK
   - test_voice_query_general_reasoning           ... OK
   - test_voice_query_unauthorized                ... OK
   - test_synthesize_speech_success               ... OK (16kHz WAV)
   - test_synthesize_speech_empty_text_rejected   ... OK (422)
   - test_session_lifecycle_fastapi               ... OK
   - test_session_invalid_ttl_rejected            ... OK (422)
   Ran 16 tests in 0.142s -> ALL OK

2. Full Test Discovery (python -m unittest discover -s tests):
   Ran 90 tests in 1.448s -> ALL OK (100% Passing)

3. Movement Intent Pytest Suite (backend/tests/test_movement_intent.py):
   28 passed in 0.88s -> ALL OK (100% Passing)
======================================================================
Total Passing Backend & Firmware Tests: 118 / 118 (100% Pass Rate)
```

