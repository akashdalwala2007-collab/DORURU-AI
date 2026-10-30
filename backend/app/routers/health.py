"""
backend/app/routers/health.py - Health, Diagnostic, and Service Status Endpoints
"""

import time
from fastapi import APIRouter
from .. import config
from ..schemas.movement import AutonomyCapabilities

router = APIRouter(tags=["Health & Status"])

@router.get("/health")
@router.get("/api/v1/health")
async def health_check():
    """Unified system health check."""
    return {
        "status": "online",
        "service": "DORURU Robot Backend",
        "timestamp": time.time(),
        "gemini_model_configured": bool(config.GEMINI_MODEL),
        "configured_gemini_model": config.GEMINI_MODEL,
        "stt_model": config.STT_MODEL_NAME,
        "stt_compute_device": config.STT_COMPUTE_DEVICE,
        "tts_voice_id": config.TTS_VOICE_ID,
        "autonomy": AutonomyCapabilities().model_dump(),
    }

