"""Unit and integration tests for faster-whisper STT and Piper TTS services."""

import io
import struct
import wave

import pytest

from app.config import Settings
from app.core.exceptions import DoruruException
from app.services.stt_service import FasterWhisperSTTService
from app.services.tts_service import PiperTTSService


def create_dummy_wav(duration_ms: int = 500, sample_rate: int = 16000) -> bytes:
    """Generate a clean 16-bit PCM mono WAV file."""
    num_samples = int(sample_rate * (duration_ms / 1000.0))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{num_samples}h", *([0] * num_samples)))
    return buf.getvalue()


@pytest.fixture
def speech_settings() -> Settings:
    return Settings(
        ENVIRONMENT="testing",
        COMPUTE_DEVICE="auto",
        STT_MODEL_PATH="base.en",
        STT_COMPUTE_TYPE="auto",
        STT_TIMEOUT_SECONDS=10.0,
        TTS_MODEL_PATH="backend/models/piper/en_US-lessac-medium.onnx",
        TTS_CONFIG_PATH="backend/models/piper/en_US-lessac-medium.onnx.json",
        TTS_TIMEOUT_SECONDS=10.0,
    )


# ---------------------------------------------------------------------------
# FasterWhisperSTTService Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stt_audio_validation_empty(speech_settings):
    """Test STT rejects empty audio bytes."""
    service = FasterWhisperSTTService(speech_settings)
    with pytest.raises(DoruruException) as exc_info:
        await service.transcribe(b"", "audio/wav")
    assert exc_info.value.code == "EMPTY_AUDIO_PAYLOAD"


@pytest.mark.asyncio
async def test_stt_audio_validation_too_short(speech_settings):
    """Test STT rejects audio shorter than 0.05 seconds."""
    service = FasterWhisperSTTService(speech_settings)
    # 20ms WAV is < 50ms min threshold
    short_wav = create_dummy_wav(duration_ms=20)
    with pytest.raises(DoruruException) as exc_info:
        await service.transcribe(short_wav, "audio/wav")
    assert exc_info.value.code == "AUDIO_TOO_SHORT"


@pytest.mark.asyncio
async def test_stt_audio_validation_corrupt_wav(speech_settings):
    """Test STT rejects corrupt WAV header."""
    service = FasterWhisperSTTService(speech_settings)
    corrupt_wav = b"RIFF" + (b"\x00" * 40) + b"WAVEbadheader"
    with pytest.raises(DoruruException) as exc_info:
        await service.transcribe(corrupt_wav, "audio/wav")
    assert exc_info.value.code == "CORRUPT_AUDIO_PAYLOAD"


@pytest.mark.asyncio
async def test_stt_raw_pcm_handling(speech_settings):
    """Test raw PCM payload is correctly wrapped and duration validated."""
    service = FasterWhisperSTTService(speech_settings)
    # 1 second of 16-bit 16kHz mono raw PCM = 32000 bytes
    raw_pcm = b"\x00" * 32000
    stream, duration = service._prepare_audio_stream(raw_pcm, "audio/pcm")
    assert round(duration, 2) == 1.0
    # Stream should be a valid WAV
    with wave.open(stream, "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getframerate() == 16000
        assert wf.getsampwidth() == 2


@pytest.mark.asyncio
async def test_stt_transcription_live(speech_settings):
    """Test real faster-whisper transcription on synthetic audio."""
    service = FasterWhisperSTTService(speech_settings)
    # 500ms of audio (silence)
    wav_bytes = create_dummy_wav(duration_ms=500)
    response = await service.transcribe(wav_bytes, "audio/wav", language="en")
    assert response.processing_time_ms > 0
    assert response.audio_duration_seconds > 0
    assert service.actual_device in ("cpu", "cuda")


# ---------------------------------------------------------------------------
# PiperTTSService Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tts_empty_text_rejected(speech_settings):
    """Test TTS rejects empty text string."""
    service = PiperTTSService(speech_settings)
    with pytest.raises(DoruruException) as exc_info:
        await service.synthesize("   ")
    assert exc_info.value.code == "EMPTY_TTS_TEXT"


@pytest.mark.asyncio
async def test_tts_overly_long_text_rejected(speech_settings):
    """Test TTS rejects text exceeding max limit."""
    service = PiperTTSService(speech_settings)
    with pytest.raises(DoruruException) as exc_info:
        await service.synthesize("a" * 2001)
    assert exc_info.value.code == "TTS_TEXT_TOO_LONG"


@pytest.mark.asyncio
async def test_tts_missing_model_raises_503():
    """Test TTS gracefully reports missing model file."""
    settings = Settings(
        TTS_MODEL_PATH="nonexistent/path/model.onnx",
        TTS_CONFIG_PATH="nonexistent/path/model.onnx.json",
    )
    service = PiperTTSService(settings)
    assert not service.is_available()
    with pytest.raises(DoruruException) as exc_info:
        await service.synthesize("Hello")
    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "TTS_MODEL_NOT_FOUND"


@pytest.mark.asyncio
async def test_tts_synthesize_and_contract(speech_settings):
    """Test real Piper synthesis produces MAX98357A-compatible WAV audio."""
    service = PiperTTSService(speech_settings)
    text = "Hello DORURU."
    wav_bytes, delivery = await service.synthesize(text)

    # Audio bytes assertions
    assert len(wav_bytes) > 0
    assert wav_bytes.startswith(b"RIFF")

    # Delivery contract assertions for ESP32 MAX98357A I2S sink
    assert delivery.format == "wav"
    assert delivery.sample_rate in (16000, 22050)
    assert delivery.channels == 1
    assert delivery.bit_depth == 16
    assert delivery.duration_ms > 0
    assert delivery.size_bytes == len(wav_bytes)
    assert delivery.stream_url.startswith("/api/v1/audio/")


@pytest.mark.asyncio
async def test_tts_caching_behavior(speech_settings):
    """Test in-memory cache returns identical audio bytes with a fresh audio_id."""
    service = PiperTTSService(speech_settings)
    text = "Status nominal."

    wav1, deliv1 = await service.synthesize(text)
    wav2, deliv2 = await service.synthesize(text)

    # Audio content must match
    assert wav1 == wav2
    assert deliv1.duration_ms == deliv2.duration_ms
    assert deliv1.size_bytes == deliv2.size_bytes
    # Audio ID must be unique so individual stream references are isolated
    assert deliv1.audio_id != deliv2.audio_id
