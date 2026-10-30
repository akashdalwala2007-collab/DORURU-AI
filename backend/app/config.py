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
DEVICE_ID_ALLOWLIST = os.getenv("DORURU_ALLOWED_DEVICES", "DORURU-SENSE-01,DORURU-DEV").split(",")

# Server-side Gemini API credentials (never sent to robot)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Vision Service Settings
VISION_MAX_DIMENSION = int(os.getenv("VISION_MAX_DIMENSION", "1024"))
VISION_COMPRESS_THRESHOLD_BYTES = int(os.getenv("VISION_COMPRESS_THRESHOLD_BYTES", str(400 * 1024))) # 400KB
VISION_JPEG_QUALITY = int(os.getenv("VISION_JPEG_QUALITY", "85"))
VISION_REQUEST_TIMEOUT_SECONDS = float(os.getenv("VISION_REQUEST_TIMEOUT_SECONDS", "10.0"))
MAX_IMAGE_PAYLOAD_BYTES = int(os.getenv("MAX_IMAGE_PAYLOAD_BYTES", str(2 * 1024 * 1024))) # 2MB limit
# Maximum HTTP content length (allows 2 MB image's base64 encoding ~2.8 MB plus JSON envelope overhead)
MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(4 * 1024 * 1024))) # 4MB limit
PERSIST_IMAGES = os.getenv("PERSIST_IMAGES", "false").lower() in ("true", "1", "yes")
VISION_TEST_MODE = os.getenv("VISION_TEST_MODE", "false").lower() in ("true", "1", "yes")



# Session Lifecycle & Offline Fallback Settings
SESSION_EXPIRY_SECONDS = int(os.getenv("SESSION_EXPIRY_SECONDS", "900")) # 15 minutes default
COMMAND_TIMEOUT_MS = int(os.getenv("COMMAND_TIMEOUT_MS", "500"))
ALLOW_OFFLINE_MOVEMENT = os.getenv("ALLOW_OFFLINE_MOVEMENT", "false").lower() in ("true", "1", "yes")

# Local Server Settings
HOST = os.getenv("BACKEND_HOST", "0.0.0.0")
PORT = int(os.getenv("BACKEND_PORT", "8000"))

# College Knowledge Base & RAG Settings
BASE_DIR = Path(__file__).resolve().parent.parent.parent
KNOWLEDGE_BASE_DIR = Path(os.getenv("KNOWLEDGE_BASE_DIR", str(BASE_DIR / "knowledge_base" / "documents")))
INDEX_STORAGE_DIR = Path(os.getenv("INDEX_STORAGE_DIR", str(BASE_DIR / "knowledge_base" / "index")))
RAG_CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "500"))
RAG_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "80"))
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "3"))
RAG_MIN_SIMILARITY_SCORE = float(os.getenv("RAG_MIN_SIMILARITY_SCORE", "0.15"))
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "tfidf_local")

# Local Speech Configuration (Phase 7 Candidates)
TTS_MODEL_PATH = os.getenv("TTS_MODEL_PATH", "backend/models/piper/en_US-lessac-medium.onnx")
TTS_CONFIG_PATH = os.getenv("TTS_CONFIG_PATH", "backend/models/piper/en_US-lessac-medium.onnx.json")
TTS_TIMEOUT_SECONDS = float(os.getenv("TTS_TIMEOUT_SECONDS", "10.0"))
STT_MODEL_PATH = os.getenv("STT_MODEL_PATH", "base.en")
STT_COMPUTE_TYPE = os.getenv("STT_COMPUTE_TYPE", "auto")
STT_TIMEOUT_SECONDS = float(os.getenv("STT_TIMEOUT_SECONDS", "10.0"))
COMPUTE_DEVICE = os.getenv("COMPUTE_DEVICE", "auto")


class Settings:
    """Application settings for speech synthesis and recognition services."""

    def __init__(
        self,
        ENVIRONMENT: str = "development",
        COMPUTE_DEVICE: str = "auto",
        STT_MODEL_PATH: str = "base.en",
        STT_COMPUTE_TYPE: str = "auto",
        STT_TIMEOUT_SECONDS: float = 10.0,
        TTS_MODEL_PATH: str = "backend/models/piper/en_US-lessac-medium.onnx",
        TTS_CONFIG_PATH: str = "backend/models/piper/en_US-lessac-medium.onnx.json",
        TTS_TIMEOUT_SECONDS: float = 10.0,
        **kwargs,
    ):
        self.ENVIRONMENT = ENVIRONMENT
        self.COMPUTE_DEVICE = COMPUTE_DEVICE
        self.STT_MODEL_PATH = STT_MODEL_PATH
        self.STT_COMPUTE_TYPE = STT_COMPUTE_TYPE
        self.STT_TIMEOUT_SECONDS = STT_TIMEOUT_SECONDS
        self.TTS_MODEL_PATH = TTS_MODEL_PATH
        self.TTS_CONFIG_PATH = TTS_CONFIG_PATH
        self.TTS_TIMEOUT_SECONDS = TTS_TIMEOUT_SECONDS
        for k, v in kwargs.items():
            setattr(self, k, v)


def get_settings() -> Settings:
    """Retrieve application settings instance."""
    return Settings(
        COMPUTE_DEVICE=COMPUTE_DEVICE,
        STT_MODEL_PATH=STT_MODEL_PATH,
        STT_COMPUTE_TYPE=STT_COMPUTE_TYPE,
        STT_TIMEOUT_SECONDS=STT_TIMEOUT_SECONDS,
        TTS_MODEL_PATH=TTS_MODEL_PATH,
        TTS_CONFIG_PATH=TTS_CONFIG_PATH,
        TTS_TIMEOUT_SECONDS=TTS_TIMEOUT_SECONDS,
    )


