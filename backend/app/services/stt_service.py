"""Faster-Whisper Speech-to-Text (STT) Service Implementation.

Performs local speech transcription with automatic hardware/precision selection:
- Attempts CUDA acceleration (float16/int8) if available
- Automatically falls back to CPU (int8 with multi-threading)
- In-memory audio validation (format, sample rate, duration, size)
- Formats raw PCM or WAV payloads seamlessly without disk persistence
- Concurrency control via asyncio.Semaphore
- Timeout protection and graceful error responses
"""

import asyncio
import io
import logging
import os
import time
import wave
from pathlib import Path
from typing import Optional

from app.config import Settings
from app.core.exceptions import DoruruException
from app.schemas.audio import AudioTranscribeResponse
from app.services.interfaces import STTService

logger = logging.getLogger("doruru.stt")

try:
    from faster_whisper import WhisperModel
    _FASTER_WHISPER_AVAILABLE = True
except ImportError:
    _FASTER_WHISPER_AVAILABLE = False


class FasterWhisperSTTService(STTService):
    """Local Speech-to-Text service powered by faster-whisper (CTranslate2)."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._model: Optional[WhisperModel] = None
        self._actual_device: str = "unknown"
        self._actual_compute_type: str = "unknown"
        self._semaphore = asyncio.Semaphore(2)
        self._initialized = False

    @property
    def actual_device(self) -> str:
        """Return the active compute device (cpu or cuda)."""
        return self._actual_device

    @property
    def actual_compute_type(self) -> str:
        """Return the active compute precision (e.g. int8, float16)."""
        return self._actual_compute_type

    def is_available(self) -> bool:
        """Return True if faster-whisper package is available."""
        return _FASTER_WHISPER_AVAILABLE

    def _resolve_model_path(self) -> str:
        """Resolve model name or local directory path."""
        model_path_str = self.settings.STT_MODEL_PATH

        # If it's a direct directory that exists, use it
        p = Path(model_path_str)
        if p.exists():
            return str(p.resolve())

        # Check relative to backend directory or workspace root
        alt_path = Path(__file__).resolve().parent.parent.parent / model_path_str
        if alt_path.exists():
            return str(alt_path.resolve())

        # Otherwise assume it's a Hugging Face model identifier (e.g., 'base.en', 'tiny.en', 'base')
        return model_path_str

    def _ensure_initialized(self) -> None:
        """Load WhisperModel into memory with CUDA capability check and CPU int8 fallback."""
        if self._initialized:
            return

        if not _FASTER_WHISPER_AVAILABLE:
            raise DoruruException(
                message="faster-whisper package is not installed in the environment.",
                code="STT_PACKAGE_NOT_INSTALLED",
                status_code=503,
            )

        model_id = self._resolve_model_path()
        target_device = self.settings.COMPUTE_DEVICE.lower()
        compute_type = self.settings.STT_COMPUTE_TYPE.lower()

        t0 = time.perf_counter()

        # Try CUDA if configured or auto-selected
        if target_device in ("cuda", "auto"):
            cuda_compute = compute_type if compute_type != "auto" else "float16"
            logger.info(
                f"Attempting to load faster-whisper model '{model_id}' on CUDA (compute_type={cuda_compute})..."
            )
            try:
                self._model = WhisperModel(
                    model_id,
                    device="cuda",
                    compute_type=cuda_compute,
                )
                self._actual_device = "cuda"
                self._actual_compute_type = cuda_compute
                self._initialized = True
                elapsed_ms = (time.perf_counter() - t0) * 1000
                logger.info(f"faster-whisper loaded on CUDA in {elapsed_ms:.1f}ms")
                return
            except Exception as e:
                logger.warning(
                    f"CUDA initialization failed for faster-whisper ({e}). Falling back to CPU int8..."
                )

        # Fallback to CPU with int8 precision
        cpu_threads = min(8, os.cpu_count() or 4)
        logger.info(
            f"Loading faster-whisper model '{model_id}' on CPU with compute_type=int8 (cpu_threads={cpu_threads})..."
        )
        try:
            self._model = WhisperModel(
                model_id,
                device="cpu",
                compute_type="int8",
                cpu_threads=cpu_threads,
            )
            self._actual_device = "cpu"
            self._actual_compute_type = "int8"
            self._initialized = True
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.info(f"faster-whisper loaded on CPU (int8) in {elapsed_ms:.1f}ms")
        except Exception as e:
            raise DoruruException(
                message=f"Failed to initialize faster-whisper model '{model_id}': {e}",
                code="STT_MODEL_LOAD_ERROR",
                status_code=500,
            ) from e

    def _prepare_audio_stream(
        self, audio_bytes: bytes, content_type: str
    ) -> tuple[io.BytesIO, float]:
        """Validate audio structure and return an in-memory stream plus duration in seconds."""
        if not audio_bytes or len(audio_bytes) < 44:
            raise DoruruException(
                message="Audio payload is empty or too short to contain audio data.",
                code="EMPTY_AUDIO_PAYLOAD",
                status_code=400,
            )

        # Detect WAV container
        if audio_bytes.startswith(b"RIFF"):
            try:
                with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
                    channels = wf.getnchannels()
                    sampwidth = wf.getsampwidth()
                    framerate = wf.getframerate()
                    nframes = wf.getnframes()
                    if framerate <= 0 or nframes <= 0 or channels <= 0 or sampwidth <= 0:
                        raise ValueError("Invalid WAV header frame rate, frame count, or sample parameters.")
                    duration = nframes / float(framerate)
            except Exception as e:
                raise DoruruException(
                    message=f"Invalid or corrupted WAV audio header: {e}",
                    code="CORRUPT_AUDIO_PAYLOAD",
                    status_code=400,
                ) from e

            if duration < 0.05:
                raise DoruruException(
                    message="Audio duration is too short for transcription (minimum 0.05 seconds).",
                    code="AUDIO_TOO_SHORT",
                    status_code=400,
                )
            if duration > 60.0:
                raise DoruruException(
                    message=f"Audio duration ({duration:.1f}s) exceeds maximum allowed (60 seconds).",
                    code="AUDIO_TOO_LONG",
                    status_code=400,
                )

            return io.BytesIO(audio_bytes), duration

        # Raw PCM fallback (ESP32 raw capture at 16000Hz, 16-bit mono)
        sample_rate = 16000
        bytes_per_sample = 2
        total_samples = len(audio_bytes) // bytes_per_sample
        duration = total_samples / float(sample_rate)

        if duration < 0.05:
            raise DoruruException(
                message="Audio duration is too short for transcription (minimum 0.05 seconds).",
                code="AUDIO_TOO_SHORT",
                status_code=400,
            )
        if duration > 60.0:
            raise DoruruException(
                message=f"Audio duration ({duration:.1f}s) exceeds maximum allowed (60 seconds).",
                code="AUDIO_TOO_LONG",
                status_code=400,
            )

        # Wrap raw PCM into a standard WAV container in-memory for PyAV/CTranslate2
        wav_buf = io.BytesIO()
        with wave.open(wav_buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(bytes_per_sample)
            wf.setframerate(sample_rate)
            wf.writeframes(audio_bytes)

        return io.BytesIO(wav_buf.getvalue()), duration

    def _transcribe_sync(
        self, audio_stream: io.BytesIO, language: Optional[str] = None
    ) -> tuple[str, Optional[str], float]:
        """Synchronously execute faster-whisper transcription."""
        self._ensure_initialized()

        t0 = time.perf_counter()
        segments, info = self._model.transcribe(
            audio_stream,
            language=language,
            beam_size=1,  # Fast greedy decoding for conversational speed
            vad_filter=True,  # Filter silence before speech
            vad_parameters=dict(min_silence_duration_ms=400),
        )

        text_pieces = [seg.text.strip() for seg in segments if seg.text.strip()]
        full_transcript = " ".join(text_pieces).strip()
        elapsed_ms = (time.perf_counter() - t0) * 1000

        detected_lang = getattr(info, "language", None)
        return full_transcript, detected_lang, elapsed_ms

    async def transcribe(
        self,
        audio_bytes: bytes,
        content_type: str,
        language: Optional[str] = None,
    ) -> AudioTranscribeResponse:
        """Transcribe speech audio bytes into text with concurrency control and timeout."""
        audio_stream, duration_sec = self._prepare_audio_stream(audio_bytes, content_type)

        async with self._semaphore:
            try:
                transcript, detected_lang, elapsed_ms = await asyncio.wait_for(
                    asyncio.to_thread(self._transcribe_sync, audio_stream, language),
                    timeout=self.settings.STT_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError as exc:
                raise DoruruException(
                    message=f"STT transcription timed out after {self.settings.STT_TIMEOUT_SECONDS}s.",
                    code="STT_TIMEOUT",
                    status_code=504,
                ) from exc

        return AudioTranscribeResponse(
            transcript=transcript,
            detected_language=detected_lang,
            processing_time_ms=round(elapsed_ms, 2),
            audio_duration_seconds=round(duration_sec, 2),
        )
