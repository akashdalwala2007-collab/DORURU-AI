"""Audio processing and delivery contract schemas.

Specifically formatted to interface with the ESP32 MAX98357A I2S audio output.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class AudioDeliveryContract(BaseModel):
    """Audio delivery specification for ESP32 MAX98357A I2S playback.

    Ensures the audio stream parameters match the hardware decoder capability:
    - Format: WAV (RIFF header) or raw PCM
    - Standard sample rate: 16000Hz or 22050Hz
    - Bit depth: 16-bit signed integer
    - Channels: 1 (mono) or 2 (stereo)
    """

    audio_id: str = Field(..., description="Unique reference ID for this audio payload.")
    format: Literal["wav", "pcm"] = Field(
        default="wav", description="Container format. WAV provides standard RIFF metadata."
    )
    sample_rate: Literal[16000, 22050] = Field(default=16000, description="Audio sample rate in Hz.")
    channels: int = Field(default=1, ge=1, le=2, description="Channel count: 1=mono, 2=stereo.")
    bit_depth: Literal[16] = Field(default=16, description="Bit depth per sample (16-bit PCM).")
    duration_ms: int = Field(..., ge=0, description="Playback duration in milliseconds.")
    size_bytes: int = Field(..., gt=0, description="Payload size in bytes.")
    stream_url: Optional[str] = Field(
        default=None, description="Endpoint URL to stream or download audio buffer."
    )


class AudioTranscribeResponse(BaseModel):
    """Result of speech-to-text inference."""

    transcript: str = Field(..., description="Transcribed text from speech utterance.")
    detected_language: Optional[str] = Field(
        default=None, description="Detected language code (e.g. 'en')."
    )
    processing_time_ms: float = Field(..., description="Inference processing time in milliseconds.")
    audio_duration_seconds: float = Field(..., description="Duration of input audio in seconds.")


class TTSSynthesizeRequest(BaseModel):
    """Request text to be converted to speech audio."""

    text: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Text to synthesize into speech.",
    )
    voice: Optional[str] = Field(
        default=None, description="Optional voice identifier; defaults to configured Piper voice."
    )


class TTSSynthesizeResponse(BaseModel):
    """Response containing synthesis metadata and audio delivery contract."""

    text: str = Field(..., description="Original synthesized text.")
    delivery: AudioDeliveryContract = Field(..., description="Delivery contract for playback.")
