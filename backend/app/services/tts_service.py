"""
backend/app/services/tts_service.py - Text-to-Speech (TTS) Service Interface & Implementation
"""

import io
import math
import struct
import time
import wave
from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass
from .. import config
from ..logging_config import logger

@dataclass
class TTSResult:
    audio_bytes: bytes
    format: str
    sample_rate: int
    channels: int
    sample_width_bits: int
    duration_seconds: float
    voice_id: str

class BaseTTSService(ABC):
    @abstractmethod
    def synthesize(self, text: str, voice_id: Optional[str] = None) -> TTSResult:
        """Synthesize text into speech audio bytes conforming to the audio delivery contract."""
        pass

class PiperTTSService(BaseTTSService):
    def __init__(self):
        self.executable_path = config.PIPER_EXECUTABLE_PATH
        self.model_path = config.TTS_MODEL_PATH
        self.config_path = config.TTS_CONFIG_PATH
        self.default_voice = config.TTS_VOICE_ID
        self.sample_rate = 16000
        self.channels = 1
        self.sample_width_bits = 16

    def _generate_clean_wav_buffer(self, duration_s: float = 0.5) -> bytes:
        """Generates standard 16kHz 16-bit Mono WAV audio buffer for ESP32 MAX98357A playback."""
        num_samples = int(self.sample_rate * duration_s)
        bio = io.BytesIO()
        with wave.open(bio, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2) # 16-bit
            wf.setframerate(self.sample_rate)

            # Generate gentle synthesized tone envelope
            frames = bytearray()
            for i in range(num_samples):
                t = float(i) / self.sample_rate
                val = int(3000.0 * math.sin(2.0 * math.pi * 440.0 * t) * (1.0 - t / duration_s))
                frames.extend(struct.pack("<h", max(-32768, min(32767, val))))
            wf.writeframes(frames)
        return bio.getvalue()

    def synthesize(self, text: str, voice_id: Optional[str] = None) -> TTSResult:
        if not text or not text.strip():
            raise ValueError("Cannot synthesize speech from empty text.")

        active_voice = voice_id or self.default_voice
        duration_s = max(0.5, round(len(text.split()) * 0.35, 2))

        # Check for external Piper executable invocation if configured
        import shutil
        import subprocess
        if shutil.which(self.executable_path) and self.model_path and Path(self.model_path).exists():
            try:
                cmd = [
                    self.executable_path,
                    "--model", self.model_path,
                    "--config", self.config_path,
                    "--output_file", "-"
                ]
                proc = subprocess.run(cmd, input=text.encode("utf-8"), capture_output=True, check=True)
                if proc.stdout:
                    return TTSResult(
                        audio_bytes=proc.stdout,
                        format="audio/wav",
                        sample_rate=self.sample_rate,
                        channels=self.channels,
                        sample_width_bits=self.sample_width_bits,
                        duration_seconds=duration_s,
                        voice_id=active_voice
                    )
            except Exception as e:
                logger.warning(f"[TTS] Piper execution error ({e}); using internal audio synthesizer.")

        # Fallback synthesized 16kHz 16-bit Mono WAV buffer
        audio_data = self._generate_clean_wav_buffer(duration_s=min(2.0, duration_s))
        return TTSResult(
            audio_bytes=audio_data,
            format="audio/wav",
            sample_rate=self.sample_rate,
            channels=self.channels,
            sample_width_bits=self.sample_width_bits,
            duration_seconds=duration_s,
            voice_id=f"piper-{active_voice}-mock"
        )

# Global singleton
_tts_service: Optional[BaseTTSService] = None

def get_tts_service() -> BaseTTSService:
    global _tts_service
    if _tts_service is None:
        _tts_service = PiperTTSService()
    return _tts_service

