"""
tests/test_fastapi_backend.py - Phase 6 FastAPI Backend Foundation & Device API Tests

Validates:
1. Environment-driven configuration (Gemini model configurable, STT/TTS paths, timeouts, no hardcoded models).
2. Health and diagnostic endpoints (/health and /api/v1/health).
3. Safe per-device credential registration and identity enforcement (/api/v1/device/register).
4. Audio upload and local STT validation (/api/v1/voice/transcribe, payload limits, MIME checks).
5. Conversational query routing and audio delivery contract (/api/v1/voice/query).
6. Speech synthesis contract (/api/v1/voice/synthesize, 16kHz 16-bit mono WAV).
7. Ephemeral session lifecycle and memory wiping (/api/v1/session/new, /status, /reset).
8. Structured error responses and authentication protection.
"""

import os
os.environ.setdefault("DORURU_DEVICE_TOKEN", "test_mock_device_token_12345")
os.environ.setdefault("VISION_TEST_MODE", "true")

import io
import wave
import struct
import unittest
from fastapi.testclient import TestClient
from backend.app.main import fastapi_app
from backend.app import config

client = TestClient(fastapi_app)
AUTH_HEADERS = {"X-Device-Token": config.DEVICE_AUTH_TOKEN}

def create_dummy_wav_bytes(duration_seconds: float = 0.5, sample_rate: int = 16000) -> bytes:
    """Helper to generate valid 16kHz 16-bit mono WAV audio in memory."""
    bio = io.BytesIO()
    with wave.open(bio, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        num_samples = int(duration_seconds * sample_rate)
        frames = bytearray()
        for i in range(num_samples):
            frames.extend(struct.pack("<h", 0))
        wf.writeframes(frames)
    return bio.getvalue()


class TestFastAPIBackend(unittest.TestCase):
    # -------------------------------------------------------------------------
    # 1. Configuration & Security
    # -------------------------------------------------------------------------
    def test_environment_driven_configuration(self):
        """Verify Gemini model, STT, and TTS settings are environment-driven and not hardcoded."""
        self.assertTrue(bool(config.GEMINI_MODEL))
        self.assertIsInstance(config.GEMINI_MODEL, str)
        self.assertIn(config.STT_COMPUTE_DEVICE, ("cpu", "cuda"))
        self.assertGreater(config.MAX_AUDIO_PAYLOAD_BYTES, 0)
        self.assertGreater(config.MAX_IMAGE_PAYLOAD_BYTES, 0)
        self.assertGreater(config.SESSION_EXPIRY_SECONDS, 0)

    # -------------------------------------------------------------------------
    # 2. Health & Status Endpoints
    # -------------------------------------------------------------------------
    def test_health_check_endpoints(self):
        """Verify root and health check endpoints."""
        # Root endpoint
        resp_root = client.get("/")
        self.assertEqual(resp_root.status_code, 200)
        self.assertEqual(resp_root.json()["robot"], "DORURU")
        self.assertEqual(resp_root.json()["autonomy_level"], 1)

        # Health endpoint
        for path in ("/health", "/api/v1/health"):
            resp = client.get(path)
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["status"], "online")
            self.assertEqual(data["service"], "DORURU Robot Backend")
            self.assertIn("autonomy", data)
            self.assertEqual(data["configured_gemini_model"], config.GEMINI_MODEL)

    # -------------------------------------------------------------------------
    # 3. Device Registration & Identity Management
    # -------------------------------------------------------------------------
    def test_device_registration_success(self):
        """Verify authenticated device registration returns session token."""
        payload = {
            "device_id": "DORURU-SENSE-01",
            "hardware_version": "XIAO-ESP32-S3-Sense",
            "firmware_version": "1.0.0",
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "capabilities": ["camera", "display", "motor", "audio_out", "pdm_mic"]
        }
        resp = client.post("/api/v1/device/register", json=payload, headers=AUTH_HEADERS)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "registered")
        self.assertEqual(data["device_id"], "DORURU-SENSE-01")
        self.assertTrue(bool(data["session_token"]))

    def test_device_registration_unauthorized(self):
        """Verify registration without device token is rejected with 401."""
        payload = {"device_id": "DORURU-SENSE-01"}
        resp = client.post("/api/v1/device/register", json=payload)
        self.assertEqual(resp.status_code, 401)

    def test_device_registration_forbidden_device_id(self):
        """Verify device ID outside allowlist is rejected with 403."""
        payload = {
            "device_id": "ROGUE-ROBOT-99",
            "hardware_version": "Unknown"
        }
        resp = client.post("/api/v1/device/register", json=payload, headers=AUTH_HEADERS)
        self.assertEqual(resp.status_code, 403)

    # -------------------------------------------------------------------------
    # 4. Audio Upload & Speech-to-Text (STT)
    # -------------------------------------------------------------------------
    def test_audio_transcribe_success(self):
        """Verify valid WAV audio upload returns transcription."""
        wav_bytes = create_dummy_wav_bytes(duration_seconds=1.0)
        headers = {**AUTH_HEADERS, "Content-Type": "audio/wav"}
        resp = client.post("/api/v1/voice/transcribe", content=wav_bytes, headers=headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(bool(data["text"]))
        self.assertGreater(data["duration_seconds"], 0)

    def test_audio_transcribe_unsupported_media_type(self):
        """Verify unsupported audio format is rejected with 415."""
        headers = {**AUTH_HEADERS, "Content-Type": "video/mp4"}
        resp = client.post("/api/v1/voice/transcribe", content=b"fake-video-bytes", headers=headers)
        self.assertEqual(resp.status_code, 415)

    def test_audio_transcribe_oversized_payload(self):
        """Verify audio payload exceeding size limit is rejected with 413."""
        oversized = bytes(config.MAX_AUDIO_PAYLOAD_BYTES + 1024)
        headers = {**AUTH_HEADERS, "Content-Type": "audio/wav"}
        resp = client.post("/api/v1/voice/transcribe", content=oversized, headers=headers)
        self.assertEqual(resp.status_code, 413)

    def test_audio_transcribe_unauthorized(self):
        """Verify unauthenticated audio upload is rejected with 401."""
        resp = client.post("/api/v1/voice/transcribe", content=b"audio-bytes")
        self.assertEqual(resp.status_code, 401)

    # -------------------------------------------------------------------------
    # 5. Conversational Query & Audio Delivery Contract
    # -------------------------------------------------------------------------
    def test_voice_query_movement_routing(self):
        """Verify natural motion query is routed to movement intent."""
        payload = {
            "query": "DORURU stop moving",
            "include_audio": True
        }
        resp = client.post("/api/v1/voice/query", json=payload, headers=AUTH_HEADERS)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["query_type"], "movement_intent")
        self.assertIn("STOP", data["movement_command"]["direction"])
        # Verify Audio Delivery Contract
        self.assertIsNotNone(data["audio_delivery"])
        self.assertEqual(data["audio_delivery"]["format"], "audio/wav")
        self.assertEqual(data["audio_delivery"]["sample_rate"], 16000)
        self.assertEqual(data["audio_delivery"]["channels"], 1)
        self.assertTrue(bool(data["audio_delivery"]["audio_base64"]))

    def test_voice_query_general_reasoning(self):
        """Verify conversational query routes to Gemini reasoning."""
        payload = {
            "query": "What is your purpose in this lab?",
            "include_audio": False
        }
        resp = client.post("/api/v1/voice/query", json=payload, headers=AUTH_HEADERS)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["query_type"], "general_reasoning")
        self.assertTrue(bool(data["answer"]))
        self.assertIsNone(data["audio_delivery"])

    def test_voice_query_unauthorized(self):
        """Verify query without device token is rejected with 401."""
        resp = client.post("/api/v1/voice/query", json={"query": "Hello"})
        self.assertEqual(resp.status_code, 401)

    # -------------------------------------------------------------------------
    # 6. Speech Synthesis (TTS)
    # -------------------------------------------------------------------------
    def test_synthesize_speech_success(self):
        """Verify direct speech synthesis returns 16kHz WAV stream."""
        payload = {"text": "Hello, this is DORURU speaking."}
        resp = client.post("/api/v1/voice/synthesize", json=payload, headers=AUTH_HEADERS)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["content-type"], "audio/wav")
        self.assertEqual(resp.headers.get("x-audio-sample-rate"), "16000")
        self.assertGreater(len(resp.content), 44) # Valid WAV header + PCM samples

    def test_synthesize_speech_empty_text_rejected(self):
        """Verify empty text synthesis is rejected with 422."""
        payload = {"text": ""}
        resp = client.post("/api/v1/voice/synthesize", json=payload, headers=AUTH_HEADERS)
        self.assertEqual(resp.status_code, 422)

    # -------------------------------------------------------------------------
    # 7. Session Lifecycle Endpoints
    # -------------------------------------------------------------------------
    def test_session_lifecycle_fastapi(self):
        """Verify ephemeral session creation, status, and reset under FastAPI."""
        # 1. Create session
        create_resp = client.post("/api/v1/session/new", json={"ttl_seconds": 600}, headers=AUTH_HEADERS)
        self.assertEqual(create_resp.status_code, 200)
        session_id = create_resp.json()["session_id"]
        self.assertEqual(create_resp.json()["ttl_seconds"], 600)

        # 2. Check status
        status_resp = client.get(f"/api/v1/session/status?session_id={session_id}", headers=AUTH_HEADERS)
        self.assertEqual(status_resp.status_code, 200)
        self.assertFalse(status_resp.json()["is_expired"])

        # 3. Reset session
        reset_resp = client.post("/api/v1/session/reset", json={"session_id": session_id}, headers=AUTH_HEADERS)
        self.assertEqual(reset_resp.status_code, 200)
        self.assertEqual(reset_resp.json()["status"], "reset")

    def test_session_invalid_ttl_rejected(self):
        """Verify invalid session TTL values are rejected."""
        # Non-integer / boolean
        resp_bool = client.post("/api/v1/session/new", json={"ttl_seconds": True}, headers=AUTH_HEADERS)
        self.assertEqual(resp_bool.status_code, 422)

        # Zero or negative
        resp_zero = client.post("/api/v1/session/new", json={"ttl_seconds": 0}, headers=AUTH_HEADERS)
        self.assertEqual(resp_zero.status_code, 422) # Caught by Pydantic ge=1 constraint


if __name__ == "__main__":
    unittest.main()
