"""
backend/app/vision/gemini_vision_service.py - Hybrid Vision Service with Google Gemini

Features:
- Uses the current official Google GenAI SDK (`google.genai`).
- Loads model dynamically from `config.GEMINI_MODEL` (never hardcodes model name).
- Keeps API keys strictly server-side.
- Voice-first, concise responses (1-3 sentences).
- Strictly disclaims continuous tracking, person following, or autonomous navigation.
- Handles rate limits, timeouts, quotas, and missing keys gracefully with mock fallback.
"""

import time
import os
from typing import Optional, Dict, Any
from google import genai
from google.genai import types
from google.genai.errors import APIError
from .image_processor import validate_and_process_image
from .schemas import VisionTriggerType, VisionAnalysisResponse
from .. import config

DORURU_VISION_SYSTEM_INSTRUCTION = """You are DORURU, a compact desktop AI companion robot.
You are looking at an image captured from your onboard camera.

CORE RESPONSE RULES:
1. VOICE-FIRST & CONCISE: Answer in 1 to 3 clear, natural sentences suitable for spoken text-to-speech audio.
2. ANSWER DIRECTLY: Directly answer the user's specific context question or describe the prominent objects in front of you.
3. NO FALSE AUTONOMY CLAIMS: You do NOT have continuous visual navigation, obstacle avoidance, person following, or real-time spatial mapping capabilities. Never claim you can follow someone or navigate autonomously based on this image.
4. HONESTY: If the image is blurry, poorly lit, or ambiguous, state what you can see honestly.
"""

class GeminiVisionService:
    def __init__(self,
                 api_key: Optional[str] = None,
                 model: Optional[str] = None,
                 test_mode: Optional[bool] = None,
                 mock_mode: Optional[bool] = None):
        self.api_key = api_key if api_key is not None else config.GEMINI_API_KEY
        self.model_name = model or config.GEMINI_MODEL
        opt_in = test_mode if test_mode is not None else mock_mode
        if opt_in is not None:
            self.test_mode = bool(opt_in)
        else:
            self.test_mode = getattr(config, "VISION_TEST_MODE", False) or (
                os.getenv("VISION_TEST_MODE", "false").lower() in ("true", "1", "yes")
            )
        self._client = None
        if self.api_key:
            try:
                timeout_ms = int(config.VISION_REQUEST_TIMEOUT_SECONDS * 1000)
                http_options = types.HttpOptions(timeout=timeout_ms)
                self._client = genai.Client(api_key=self.api_key, http_options=http_options)
            except Exception as e:
                print(f"[VisionService] Warning: Failed to initialize genai.Client: {e}")

    def analyze_frame(self,
                      image_bytes: bytes,
                      context_prompt: Optional[str] = None,
                      trigger_type: VisionTriggerType = VisionTriggerType.ON_DEMAND,
                      device_id: str = "DORURU-SENSE-01") -> VisionAnalysisResponse:
        """
        Processes an on-demand or event-triggered camera frame through Gemini Vision.
        """
        start_time = time.time()
        prompt = (context_prompt or "Describe what you see in front of you").strip()

        # 1. Validate & Optimize Image (in-memory)
        processed_bytes, metadata = validate_and_process_image(image_bytes)

        # 2. Check for Missing Credentials or Failed Client Initialization
        if not self.api_key or not self._client:
            latency_ms = round((time.time() - start_time) * 1000, 2)
            if self.test_mode:
                # Deterministic mock simulation for opt-in test mode
                mock_answer = (
                    f"I can see a clean workspace with development equipment in front of me. "
                    f"(Prompt: '{prompt}')."
                )
                return VisionAnalysisResponse(
                    status="success",
                    device_id=device_id,
                    trigger_type=trigger_type,
                    context_prompt=prompt,
                    answer=mock_answer,
                    latency_ms=latency_ms,
                    image_metadata=metadata,
                    ephemeral=not config.PERSIST_IMAGES,
                    model_used=f"{self.model_name} (mock_mode)"
                )
            else:
                err_msg = "Gemini API credentials not configured or client initialization failed."
                return VisionAnalysisResponse(
                    status="unavailable",
                    device_id=device_id,
                    trigger_type=trigger_type,
                    context_prompt=prompt,
                    answer="Vision analysis is currently unavailable because API credentials are not configured.",
                    latency_ms=latency_ms,
                    image_metadata=metadata,
                    ephemeral=not config.PERSIST_IMAGES,
                    model_used=self.model_name,
                    error=err_msg
                )

        # 3. Call Official Google GenAI SDK
        mime_type = "image/jpeg" if metadata.format.upper() in ("JPEG", "JPG") else f"image/{metadata.format.lower()}"
        image_part = types.Part.from_bytes(data=processed_bytes, mime_type=mime_type)

        try:
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=[
                    image_part,
                    prompt
                ],
                config=types.GenerateContentConfig(
                    system_instruction=DORURU_VISION_SYSTEM_INSTRUCTION,
                    max_output_tokens=150,
                    temperature=0.4
                )
            )

            latency_ms = round((time.time() - start_time) * 1000, 2)
            answer_text = response.text.strip() if response.text else "I looked, but could not discern anything clear."

            return VisionAnalysisResponse(
                status="success",
                device_id=device_id,
                trigger_type=trigger_type,
                context_prompt=prompt,
                answer=answer_text,
                latency_ms=latency_ms,
                image_metadata=metadata,
                ephemeral=not config.PERSIST_IMAGES,
                model_used=self.model_name
            )

        except APIError as e:
            latency_ms = round((time.time() - start_time) * 1000, 2)
            status_code = getattr(e, "code", 500)
            if status_code == 429:
                err_msg = "Gemini API quota exceeded or rate limit reached. Please try again shortly."
            else:
                err_msg = f"Gemini API error ({status_code}): {e.message}"

            return VisionAnalysisResponse(
                status="error",
                device_id=device_id,
                trigger_type=trigger_type,
                context_prompt=prompt,
                answer="Sorry, I encountered an issue analyzing that image.",
                latency_ms=latency_ms,
                image_metadata=metadata,
                ephemeral=True,
                model_used=self.model_name,
                error=err_msg
            )

        except Exception as e:
            latency_ms = round((time.time() - start_time) * 1000, 2)
            return VisionAnalysisResponse(
                status="error",
                device_id=device_id,
                trigger_type=trigger_type,
                context_prompt=prompt,
                answer="Vision processing timed out or failed to connect.",
                latency_ms=latency_ms,
                image_metadata=metadata,
                ephemeral=True,
                model_used=self.model_name,
                error=str(e)
            )

