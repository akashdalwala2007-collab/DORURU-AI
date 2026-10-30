"""Speech Processing Latency Benchmark for DORURU.

Measures cold-start and warm inference latency for:
1. Faster-Whisper STT (transcription on CUDA/CPU)
2. Piper TTS (synthesis on ONNX)
3. In-memory speech caching

Logs empirical timings on the local ASUS TUF A15 development host.
"""

import asyncio
import io
import math
import os
import platform
import struct
import sys
import time
import wave
from pathlib import Path
from typing import List

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DORURU_DEVICE_TOKEN", "benchmark_token")

from app.config import get_settings
from app.services.stt_service import FasterWhisperSTTService
from app.services.tts_service import PiperTTSService


def generate_synthetic_audio(duration_ms: int = 2000, sample_rate: int = 16000) -> bytes:
    """Generate a clean synthetic 16-bit mono PCM audio buffer."""
    num_samples = int(sample_rate * (duration_ms / 1000.0))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        # Synthetic low-amplitude sine tone
        raw_samples = [
            int(3000 * math.sin(2 * math.pi * 440 * i / sample_rate))
            for i in range(num_samples)
        ]
        wf.writeframes(struct.pack(f"<{num_samples}h", *raw_samples))
    return buf.getvalue()


async def run_benchmark():
    settings = get_settings()

    print("=" * 65)
    print("       DORURU LOCAL SPEECH BENCHMARK REPORT (PHASE 7)")
    print("=" * 65)
    print(f"OS: {platform.system()} {platform.release()} ({platform.version()})")
    print(f"Python: {platform.python_version()}")
    print(f"Processor: {platform.processor()} ({os.cpu_count()} logical threads)")
    print(f"Configured STT Model: {settings.STT_MODEL_PATH}")
    print(f"Configured TTS Model: {settings.TTS_MODEL_PATH}")
    print(f"Target Compute Device: {settings.COMPUTE_DEVICE}")
    print("=" * 65)

    # ---------------------------------------------------------------------------
    # 1. PIPER TTS BENCHMARK
    # ---------------------------------------------------------------------------
    print("\n--- [1] PIPER TTS (Text-to-Speech) ---")
    tts_service = PiperTTSService(settings)
    if not tts_service.is_available():
        print(f"ERROR: Piper voice model not found at {settings.TTS_MODEL_PATH}")
        return

    # Cold Start
    t_start = time.perf_counter()
    tts_service._ensure_initialized()
    tts_cold_start_ms = (time.perf_counter() - t_start) * 1000
    print(f"Cold Start (Model Load from Disk): {tts_cold_start_ms:.2f} ms")

    test_phrases = [
        ("Short (4 words)", "Hello, I am DORURU."),
        ("Medium (10 words)", "The autonomous robotics team is working in the innovation lab."),
        ("Long (20 words)", "DORURU is an autonomous companion robot designed to assist campus visitors, navigate corridors safely, and provide interactive college information."),
    ]

    for label, phrase in test_phrases:
        print(f"\n  Testing {label}: \"{phrase[:35]}...\"")
        latencies: List[float] = []
        audio_durations: List[float] = []

        # 5 iterations
        for i in range(5):
            t0 = time.perf_counter()
            wav_bytes, delivery = await tts_service.synthesize(phrase, voice=f"bench_run_{i}")
            lat_ms = (time.perf_counter() - t0) * 1000
            latencies.append(lat_ms)
            audio_durations.append(delivery.duration_ms)

        avg_lat = sum(latencies) / len(latencies)
        min_lat = min(latencies)
        max_lat = max(latencies)
        avg_audio_ms = sum(audio_durations) / len(audio_durations)
        rtf = (avg_lat / avg_audio_ms) if avg_audio_ms > 0 else 0

        print(f"    - Avg Latency: {avg_lat:.2f} ms (Min: {min_lat:.2f} ms, Max: {max_lat:.2f} ms)")
        print(f"    - Audio Length: {avg_audio_ms:.0f} ms | Real-Time Factor (RTF): {rtf:.3f}x (synthesis/audio)")

    # Cache Performance
    cache_phrase = "Emergency stop activated immediately."
    await tts_service.synthesize(cache_phrase)  # Prime cache
    t_cache = time.perf_counter()
    await tts_service.synthesize(cache_phrase)  # Fetch from cache
    cache_hit_ms = (time.perf_counter() - t_cache) * 1000
    print(f"\n  Cached Phrase Hit Latency: {cache_hit_ms:.3f} ms")

    # ---------------------------------------------------------------------------
    # 2. FASTER-WHISPER STT BENCHMARK
    # ---------------------------------------------------------------------------
    print("\n--- [2] FASTER-WHISPER STT (Speech-to-Text) ---")
    stt_service = FasterWhisperSTTService(settings)
    if not stt_service.is_available():
        print("ERROR: faster-whisper package is not available.")
        return

    # Cold Start
    t_start = time.perf_counter()
    stt_service._ensure_initialized()
    stt_cold_start_ms = (time.perf_counter() - t_start) * 1000
    print(f"Cold Start (Model Load from Disk/Cache): {stt_cold_start_ms:.2f} ms")
    print(f"Active Compute Device: {stt_service.actual_device.upper()} ({stt_service.actual_compute_type})")

    # Audio input test clips: 1.0s, 2.0s, 4.0s
    audio_durations_ms = [1000, 2000, 4000]

    for clip_ms in audio_durations_ms:
        print(f"\n  Testing Audio Clip: {clip_ms} ms ({clip_ms/1000:.1f}s)")
        raw_wav = generate_synthetic_audio(duration_ms=clip_ms)
        latencies: List[float] = []

        for _ in range(5):
            t0 = time.perf_counter()
            _resp = await stt_service.transcribe(raw_wav, "audio/wav", language="en")
            lat_ms = (time.perf_counter() - t0) * 1000
            latencies.append(lat_ms)

        avg_lat = sum(latencies) / len(latencies)
        min_lat = min(latencies)
        max_lat = max(latencies)
        rtf = avg_lat / clip_ms

        print(f"    - Avg Latency: {avg_lat:.2f} ms (Min: {min_lat:.2f} ms, Max: {max_lat:.2f} ms)")
        print(f"    - Real-Time Factor (RTF): {rtf:.3f}x (inference/audio)")

    print("\n" + "=" * 65)
    print("                      BENCHMARK COMPLETE")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(run_benchmark())
