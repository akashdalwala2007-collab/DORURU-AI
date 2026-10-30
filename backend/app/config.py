"""
backend/app/config.py - DORURU Backend Configuration

Security & Configuration Rules:
- Never hardcode the Gemini model name.
- Keep Gemini API key strictly server-side (never exposed to ESP32 firmware).
- Enforce ephemeral image storage policy (no permanent storage by default).
"""

import os
from pathlib import Path

# Device Authentication - Fail during startup when unset or empty
DEVICE_AUTH_TOKEN = os.getenv("DORURU_DEVICE_TOKEN")
if not DEVICE_AUTH_TOKEN or not DEVICE_AUTH_TOKEN.strip():
    raise ValueError("DORURU_DEVICE_TOKEN environment variable must be set and non-empty")
DEVICE_AUTH_TOKEN = DEVICE_AUTH_TOKEN.strip()
DEVICE_ID_ALLOWLIST = [d.strip() for d in os.getenv("DORURU_ALLOWED_DEVICES", "DORURU-SENSE-01,DORURU-DEV").split(",") if d.strip()]

# Server-side Gemini API credentials (never sent to robot)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash"))
GEMINI_REQUEST_TIMEOUT_SECONDS = float(os.getenv("GEMINI_REQUEST_TIMEOUT_SECONDS", "15.0"))

# Vision Service Settings
VISION_MAX_DIMENSION = int(os.getenv("VISION_MAX_DIMENSION", "1024"))
VISION_COMPRESS_THRESHOLD_BYTES = int(os.getenv("VISION_COMPRESS_THRESHOLD_BYTES", str(400 * 1024))) # 400KB
VISION_JPEG_QUALITY = int(os.getenv("VISION_JPEG_QUALITY", "85"))
VISION_REQUEST_TIMEOUT_SECONDS = float(os.getenv("VISION_REQUEST_TIMEOUT_SECONDS", "10.0"))
MAX_IMAGE_PAYLOAD_BYTES = int(os.getenv("MAX_IMAGE_PAYLOAD_BYTES", os.getenv("MAX_IMAGE_UPLOAD_BYTES", str(2 * 1024 * 1024)))) # 2MB limit
MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(4 * 1024 * 1024))) # 4MB limit
PERSIST_IMAGES = os.getenv("PERSIST_IMAGES", "false").lower() in ("true", "1", "yes")
VISION_TEST_MODE = os.getenv("VISION_TEST_MODE", "false").lower() in ("true", "1", "yes")

# Local Speech-to-Text (STT) Settings — faster-whisper
STT_MODEL_NAME = os.getenv("STT_MODEL_SIZE", os.getenv("STT_MODEL_NAME", "base"))
STT_MODEL_PATH = os.getenv("STT_MODEL_PATH", "")
STT_COMPUTE_DEVICE = os.getenv("STT_DEVICE", os.getenv("STT_COMPUTE_DEVICE", "cpu"))
STT_COMPUTE_TYPE = os.getenv("STT_COMPUTE_TYPE", "int8")
STT_SAMPLE_RATE = int(os.getenv("STT_SAMPLE_RATE", "16000"))
STT_TIMEOUT_SECONDS = float(os.getenv("STT_TIMEOUT_SECONDS", "10.0"))
MAX_AUDIO_PAYLOAD_BYTES = int(os.getenv("MAX_AUDIO_PAYLOAD_BYTES", str(10 * 1024 * 1024))) # 10MB audio limit
ALLOWED_AUDIO_TYPES = [
    "audio/wav", "audio/x-wav", "audio/wave", "audio/pcm",
    "audio/mpeg", "audio/mp3", "application/octet-stream"
]

# Local Text-to-Speech (TTS) Settings — Piper
PIPER_EXECUTABLE_PATH = os.getenv("PIPER_EXECUTABLE_PATH", "piper")
TTS_MODEL_PATH = os.getenv("PIPER_MODEL_PATH", os.getenv("TTS_MODEL_PATH", "models/piper/en_US-lessac-medium.onnx"))
TTS_CONFIG_PATH = os.getenv("PIPER_CONFIG_PATH", os.getenv("TTS_CONFIG_PATH", "models/piper/en_US-lessac-medium.onnx.json"))
TTS_VOICE_ID = os.getenv("TTS_VOICE_ID", "en_US-lessac-medium")
TTS_COMPUTE_DEVICE = os.getenv("TTS_DEVICE", os.getenv("TTS_COMPUTE_DEVICE", "cpu"))
TTS_TIMEOUT_SECONDS = float(os.getenv("TTS_TIMEOUT_SECONDS", "10.0"))

# Session Lifecycle & Offline Fallback Settings
SESSION_EXPIRY_SECONDS = int(os.getenv("SESSION_EXPIRY_SECONDS", "900")) # 15 minutes default
COMMAND_TIMEOUT_MS = int(os.getenv("COMMAND_TIMEOUT_MS", "500"))
ALLOW_OFFLINE_MOVEMENT = os.getenv("ALLOW_OFFLINE_MOVEMENT", "false").lower() in ("true", "1", "yes")
MAX_MOVE_DURATION_SECONDS = float(os.getenv("MAX_MOVE_DURATION_SECONDS", "3.0"))

# Local Server Settings
HOST = os.getenv("BACKEND_HOST", os.getenv("HOST", "0.0.0.0"))
PORT = int(os.getenv("BACKEND_PORT", os.getenv("PORT", "8000")))

# College Knowledge Base & RAG Settings
BASE_DIR = Path(__file__).resolve().parent.parent.parent
KNOWLEDGE_BASE_DIR = Path(os.getenv("KNOWLEDGE_BASE_DIR", os.getenv("COLLEGE_KB_DIR", str(BASE_DIR / "knowledge_base" / "documents"))))
INDEX_STORAGE_DIR = Path(os.getenv("INDEX_STORAGE_DIR", str(BASE_DIR / "knowledge_base" / "index")))
RAG_CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "500"))
RAG_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "80"))
RAG_TOP_K = int(os.getenv("RAG_TOP_K", os.getenv("COLLEGE_KB_SIMILARITY_TOP_K", "3")))
RAG_MIN_SIMILARITY_SCORE = float(os.getenv("RAG_MIN_SIMILARITY_SCORE", "0.15"))
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "tfidf_local")
