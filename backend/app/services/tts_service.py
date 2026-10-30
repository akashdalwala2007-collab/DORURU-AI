"""Piper Text-to-Speech (TTS) Service Implementation.

Generates 16-bit PCM WAV audio for the ESP32 MAX98357A I2S audio sink.
Supports in-memory LRU caching for reusable robotic speech utterances,
configurable voice models, concurrency limits, and graceful error handling.
"""

import asyncio
import hashlib
import io
import logging
import time
import uuid
import wave
from collections import OrderedDict
from pathlib import Path
from typing import Optional, Tuple

from app.config import Settings
from app.core.exceptions import DoruruException
from app.schemas.audio import AudioDeliveryContract
from app.services.interfaces import TTSService

logger = logging.getLogger("doruru.tts")

try:
    from piper import PiperVoice
    _PIPER_AVAILABLE = True
except ImportError:
    _PIPER_AVAILABLE = False


class PiperTTSService(TTSService):
    """Local Text-to-Speech service powered by Piper ONNX models."""

    def __init__(self, settings: Settings, max_cache_entries: int = 100):
        self.settings = settings
        self.max_cache_entries = max_cache_entries
        self._voice: Optional[PiperVoice] = None
        self._voice_sample_rate: int = 22050
        self._semaphore = asyncio.Semaphore(2)
        self._cache: OrderedDict[str, Tuple[bytes, int, int]] = OrderedDict()  # key -> (wav_bytes, sample_rate, duration_ms)
        self._initialized = False

    def _resolve_model_path(self) -> Optional[Path]:
        """Resolve path to the Piper ONNX voice model."""
        candidates = [
            Path(self.settings.TTS_MODEL_PATH),
            Path(__file__).resolve().parent.parent.parent / self.settings.TTS_MODEL_PATH,
            Path.cwd() / "backend" / self.settings.TTS_MODEL_PATH,
            Path.cwd() / self.settings.TTS_MODEL_PATH,
        ]
        for p in candidates:
            if p.is_file():
                return p.resolve()
        return None

    def _resolve_config_path(self) -> Optional[Path]:
        """Resolve path to the Piper voice JSON configuration file."""
        candidates = [
            Path(self.settings.TTS_CONFIG_PATH),
            Path(__file__).resolve().parent.parent.parent / self.settings.TTS_CONFIG_PATH,
            Path.cwd() / "backend" / self.settings.TTS_CONFIG_PATH,
            Path.cwd() / self.settings.TTS_CONFIG_PATH,
        ]
        for p in candidates:
            if p.is_file():
                return p.resolve()
        return None

    def is_available(self) -> bool:
        """Return True if Piper is installed and model files exist."""
        if not _PIPER_AVAILABLE:
            return False
        return self._resolve_model_path() is not None

    def _ensure_initialized(self) -> None:
        """Synchronously load the Piper voice model if not already loaded."""
        if self._initialized:
            return

        if not _PIPER_AVAILABLE:
            raise DoruruException(
                message="piper-tts package is not installed in the environment.",
                code="TTS_PACKAGE_NOT_INSTALLED",
                status_code=503,
            )

        model_path = self._resolve_model_path()
        if not model_path:
            raise DoruruException(
                message=f"Piper voice model file not found at '{self.settings.TTS_MODEL_PATH}'.",
                code="TTS_MODEL_NOT_FOUND",
                status_code=503,
            )

        config_path = self._resolve_config_path()

        use_cuda = self.settings.COMPUTE_DEVICE == "cuda"
        logger.info(
            f"Loading Piper TTS voice model from '{model_path}' (cuda={use_cuda})..."
        )
        try:
            t0 = time.perf_counter()
            self._voice = PiperVoice.load(
                model_path=str(model_path),
                config_path=str(config_path) if config_path else None,
                use_cuda=use_cuda,
            )
            self._voice_sample_rate = getattr(self._voice.config, "sample_rate", 22050)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.info(
                f"Piper TTS voice loaded successfully in {elapsed_ms:.1f}ms "
                f"(Sample Rate: {self._voice_sample_rate}Hz)"
            )
            self._initialized = True
        except Exception as e:
            if use_cuda:
                logger.warning(
                    f"Failed loading Piper with CUDA ({e}). Retrying with CPU execution..."
                )
                try:
                    self._voice = PiperVoice.load(
                        model_path=str(model_path),
                        config_path=str(config_path) if config_path else None,
                        use_cuda=False,
                    )
                    self._voice_sample_rate = getattr(self._voice.config, "sample_rate", 22050)
                    self._initialized = True
                    logger.info("Piper TTS loaded successfully on CPU fallback.")
                    return
                except Exception as fallback_exc:
                    raise DoruruException(
                        message=f"Failed to load Piper voice model on CPU: {fallback_exc}",
                        code="TTS_MODEL_LOAD_ERROR",
                        status_code=500,
                    ) from fallback_exc
            raise DoruruException(
                message=f"Failed to load Piper voice model: {e}",
                code="TTS_MODEL_LOAD_ERROR",
                status_code=500,
            ) from e

    def _synthesize_sync(self, text: str) -> Tuple[bytes, int, int]:
        """Synchronously synthesize text to WAV audio using PiperVoice."""
        self._ensure_initialized()
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav_file:
            self._voice.synthesize_wav(text=text, wav_file=wav_file, set_wav_format=True)

        wav_bytes = buf.getvalue()
        if not wav_bytes:
            raise DoruruException(
                message="Piper produced empty audio output.",
                code="TTS_SYNTHESIS_FAILED",
                status_code=500,
            )

        # Inspect generated WAV structure
        with wave.open(io.BytesIO(wav_bytes), "rb") as check_wf:
            channels = check_wf.getnchannels()
            sample_rate = check_wf.getframerate()
            n_frames = check_wf.getnframes()
            if channels <= 0 or sample_rate <= 0:
                raise ValueError("Invalid WAV header output parameters from Piper.")
            duration_ms = int((n_frames / sample_rate) * 1000)

        return wav_bytes, sample_rate, duration_ms

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
    ) -> Tuple[bytes, AudioDeliveryContract]:
        """Synthesize text into audio bytes and return an ESP32 audio delivery contract."""
        clean_text = text.strip()
        if not clean_text:
            raise DoruruException(
                message="Cannot synthesize empty text prompt.",
                code="EMPTY_TTS_TEXT",
                status_code=400,
            )

        if len(clean_text) > 2000:
            raise DoruruException(
                message=f"Text length ({len(clean_text)}) exceeds maximum allowed (2000 characters).",
                code="TTS_TEXT_TOO_LONG",
                status_code=400,
            )

        # Cache key based on voice and text content
        effective_voice = voice or "default"
        cache_key = hashlib.sha256(f"{effective_voice}:{clean_text}".encode("utf-8")).hexdigest()

        # Check in-memory cache for reusable phrases
        if cache_key in self._cache:
            wav_bytes, sample_rate, duration_ms = self._cache[cache_key]
            # Move to end (most recently used)
            self._cache.move_to_end(cache_key)
            audio_id = f"aud_{uuid.uuid4().hex[:12]}"
            delivery = AudioDeliveryContract(
                audio_id=audio_id,
                format="wav",
                sample_rate=sample_rate if sample_rate in (16000, 22050) else 22050,
                channels=1,
                bit_depth=16,
                duration_ms=duration_ms,
                size_bytes=len(wav_bytes),
                stream_url=f"/api/v1/audio/{audio_id}",
            )
            return wav_bytes, delivery

        # Concurrency control & timeout protection
        async with self._semaphore:
            try:
                wav_bytes, sample_rate, duration_ms = await asyncio.wait_for(
                    asyncio.to_thread(self._synthesize_sync, clean_text),
                    timeout=self.settings.TTS_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError as exc:
                raise DoruruException(
                    message=f"TTS synthesis timed out after {self.settings.TTS_TIMEOUT_SECONDS}s.",
                    code="TTS_TIMEOUT",
                    status_code=504,
                ) from exc

        # Store in bounded LRU cache
        if len(self._cache) >= self.max_cache_entries:
            self._cache.popitem(last=False)
        self._cache[cache_key] = (wav_bytes, sample_rate, duration_ms)

        audio_id = f"aud_{uuid.uuid4().hex[:12]}"
        delivery = AudioDeliveryContract(
            audio_id=audio_id,
            format="wav",
            sample_rate=sample_rate if sample_rate in (16000, 22050) else 22050,
            channels=1,
            bit_depth=16,
            duration_ms=duration_ms,
            size_bytes=len(wav_bytes),
            stream_url=f"/api/v1/audio/{audio_id}",
        )
        return wav_bytes, delivery
