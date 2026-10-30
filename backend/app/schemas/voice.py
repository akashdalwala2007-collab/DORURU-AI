"""
backend/app/schemas/voice.py - Pydantic Schemas for Voice Interaction, STT & Audio Delivery
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class AudioTranscribeResponse(BaseModel):
    """Result of Speech-to-Text transcription."""
    status: str
    text: str
    duration_seconds: float
    confidence: float = 1.0
    language: str = "en"
    model: str = "faster-whisper"

class AudioDeliveryContract(BaseModel):
    """
    Contract defining audio playback payload format for DORURU MAX98357A speaker.
    Standard: 16kHz 16-bit Mono PCM/WAV.
    """
    format: str = Field(default="audio/wav", description="Audio MIME type")
    sample_rate: int = Field(default=16000, description="Audio sample rate in Hz")
    channels: int = Field(default=1, description="1=Mono, 2=Stereo")
    sample_width_bits: int = Field(default=16, description="Bits per sample")
    encoding: str = Field(default="PCM_16", description="PCM encoding type")
    audio_base64: Optional[str] = Field(None, description="Base64-encoded audio payload if requested")
    audio_length_bytes: int = Field(default=0, description="Total byte length of audio stream")

class VoiceQueryRequest(BaseModel):
    """User natural language query submission."""
    query: str = Field(..., min_length=1, max_length=1000, description="User spoken or typed text")
    session_id: Optional[str] = Field(None, description="Active ephemeral session ID")
    device_id: Optional[str] = Field(None, description="Reporting robot device ID")
    include_audio: bool = Field(default=True, description="True to synthesize TTS voice response")
    context_override: Optional[str] = Field(None, description="Optional extra ground context")

class VoiceQueryResponse(BaseModel):
    """Unified conversational answer and audio delivery."""
    status: str
    answer: str
    query_type: str = Field(..., description="'movement_intent', 'college_rag', or 'general_reasoning'")
    session_id: str
    source_attribution: Optional[List[Dict[str, Any]]] = None
    movement_command: Optional[Dict[str, Any]] = None
    audio_delivery: Optional[AudioDeliveryContract] = None
    latency_ms: float = 0.0

class TextToSpeechRequest(BaseModel):
    """Direct speech synthesis request."""
    text: str = Field(..., min_length=1, max_length=2000)
    voice_id: Optional[str] = None

