"""
backend/app/routers/voice.py - Voice Interaction, Local STT, Orchestration & Audio Delivery
"""

import base64
import time
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException, status, Response, File, UploadFile
from .. import config
from ..schemas.voice import (
    AudioTranscribeResponse,
    AudioDeliveryContract,
    VoiceQueryRequest,
    VoiceQueryResponse,
    TextToSpeechRequest,
)
from ..schemas.movement import MovementIntentRequest
from ..services.stt_service import get_stt_service
from ..services.tts_service import get_tts_service
from ..services.gemini_service import get_gemini_service
from ..services.movement_intent_parser import (
    MovementIntentParser,
    MovementIntentError,
    UnknownMovementIntentError,
    UnsupportedAutonomyError,
)
from ..session.session_manager import SessionManager
from ..rag.service import CollegeRAGService
from .deps import verify_device_token

router = APIRouter(prefix="/api/v1/voice", tags=["Voice Interaction"])

# Shared services
_session_manager = SessionManager(default_ttl_seconds=config.SESSION_EXPIRY_SECONDS)
_rag_service = CollegeRAGService()
_movement_parser = MovementIntentParser()

@router.post("/transcribe", response_model=AudioTranscribeResponse)
async def transcribe_audio(
    request: Request,
    token: str = Depends(verify_device_token)
):
    """
    Receives speech audio bytes from ESP32 PDM microphone and returns STT transcription.
    Validates payload size and audio MIME type.
    """
    # Validate payload size
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > config.MAX_AUDIO_PAYLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Audio payload exceeds maximum limit of {config.MAX_AUDIO_PAYLOAD_BYTES} bytes"
        )

    # Validate content type
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type and content_type not in config.ALLOWED_AUDIO_TYPES and not content_type.startswith("multipart/"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported audio type '{content_type}'. Supported: {config.ALLOWED_AUDIO_TYPES}"
        )

    audio_bytes = await request.body()
    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty audio payload received."
        )

    if len(audio_bytes) > config.MAX_AUDIO_PAYLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Audio payload exceeds maximum limit of {config.MAX_AUDIO_PAYLOAD_BYTES} bytes"
        )

    try:
        stt_result = get_stt_service().transcribe(audio_bytes)
        return AudioTranscribeResponse(
            status="success",
            text=stt_result.text,
            duration_seconds=stt_result.duration_seconds,
            confidence=stt_result.confidence,
            language=stt_result.language,
            model=stt_result.model
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Speech-to-Text transcription error: {str(e)}"
        )

@router.post("/query", response_model=VoiceQueryResponse)
async def process_voice_query(
    payload: VoiceQueryRequest,
    token: str = Depends(verify_device_token)
):
    """
    Unified Conversational Query Orchestrator.
    Routes queries to Movement Intent, College RAG, or Gemini General Reasoning,
    and attaches an audio delivery contract for ESP32 speaker playback.
    """
    start_time = time.time()
    query_text = payload.query.strip()
    session = _session_manager.get_or_create_session(payload.session_id)
    session.add_message("user", query_text)

    # 1. Evaluate Physical Movement Intent
    try:
        intent = _movement_parser.parse(MovementIntentRequest(text=query_text))
        # Query is a movement intent!
        answer_text = f"Executing {intent.direction.value} movement."
        if intent.direction.value == "STOP":
            answer_text = "Stopping all motors."

        movement_data = {
            "direction": intent.direction.value,
            "speed_pwm": intent.speed_pwm,
            "duration_ms": intent.duration_ms,
            "autonomy_level": intent.autonomy_level.value,
            "safety_disclaimer": intent.safety_disclaimer
        }

        # Synthesize voice feedback if requested
        audio_contract = None
        if payload.include_audio:
            tts_res = get_tts_service().synthesize(answer_text)
            audio_contract = AudioDeliveryContract(
                format=tts_res.format,
                sample_rate=tts_res.sample_rate,
                channels=tts_res.channels,
                sample_width_bits=tts_res.sample_width_bits,
                encoding="PCM_16",
                audio_base64=base64.b64encode(tts_res.audio_bytes).decode("ascii"),
                audio_length_bytes=len(tts_res.audio_bytes)
            )

        latency = round((time.time() - start_time) * 1000, 2)
        session.add_message("assistant", answer_text)
        return VoiceQueryResponse(
            status="success",
            answer=answer_text,
            query_type="movement_intent",
            session_id=session.session_id,
            movement_command=movement_data,
            audio_delivery=audio_contract,
            latency_ms=latency
        )
    except (MovementIntentError, UnknownMovementIntentError, UnsupportedAutonomyError):
        # Not a movement intent, proceed to information retrieval / conversation
        pass

    # 2. Evaluate College Knowledge Base (RAG)
    try:
        rag_res = _rag_service.answer_query(query_text)
    except Exception:
        rag_res = None

    if rag_res and isinstance(rag_res, dict) and rag_res.get("is_college_query") and rag_res.get("sources"):
        context_str = "\n".join([
            f"[{s.get('source_file', '')}] {s.get('text', '')}" if isinstance(s, dict) else str(s)
            for s in rag_res.get("sources", [])
        ])
        gemini_res = get_gemini_service().generate_response(
            prompt=query_text,
            context=context_str,
            history=session.conversation_history
        )
        answer_text = gemini_res.text or rag_res.get("answer", "")
        query_type = "college_rag"
        source_attribution = rag_res.get("sources")
    else:
        # 3. General Conversational Reasoning via Gemini
        gemini_res = get_gemini_service().generate_response(
            prompt=query_text,
            history=session.conversation_history
        )
        answer_text = gemini_res.text
        query_type = "general_reasoning"
        source_attribution = None

    # 4. Audio Delivery Synthesis
    audio_contract = None
    if payload.include_audio:
        tts_res = get_tts_service().synthesize(answer_text)
        audio_contract = AudioDeliveryContract(
            format=tts_res.format,
            sample_rate=tts_res.sample_rate,
            channels=tts_res.channels,
            sample_width_bits=tts_res.sample_width_bits,
            encoding="PCM_16",
            audio_base64=base64.b64encode(tts_res.audio_bytes).decode("ascii"),
            audio_length_bytes=len(tts_res.audio_bytes)
        )

    latency = round((time.time() - start_time) * 1000, 2)
    session.add_message("assistant", answer_text)

    return VoiceQueryResponse(
        status="success",
        answer=answer_text,
        query_type=query_type,
        session_id=session.session_id,
        source_attribution=source_attribution,
        audio_delivery=audio_contract,
        latency_ms=latency
    )

@router.post("/synthesize")
async def synthesize_speech(
    payload: TextToSpeechRequest,
    token: str = Depends(verify_device_token)
):
    """Direct speech synthesis returning standard 16kHz WAV audio bytes."""
    try:
        tts_res = get_tts_service().synthesize(payload.text, payload.voice_id)
        return Response(
            content=tts_res.audio_bytes,
            media_type="audio/wav",
            headers={
                "Content-Disposition": "attachment; filename=doruru_speech.wav",
                "X-Audio-Sample-Rate": str(tts_res.sample_rate),
                "X-Audio-Channels": str(tts_res.channels),
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Speech synthesis error: {str(e)}"
        )
