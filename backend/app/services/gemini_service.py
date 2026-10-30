"""
backend/app/services/gemini_service.py - Conversational AI Reasoning with Google Gemini

Rules:
- Never hardcode Gemini model name; always read from config.GEMINI_MODEL.
- Keep API key strictly server-side.
- Ensure DORURU persona consistency without false autonomy claims.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from .. import config
from ..logging_config import logger

DORURU_SYSTEM_PERSONA = (
    "You are DORURU, a friendly, helpful, and inquisitive educational robot and lab assistant. "
    "Your responses must be concise, conversational, and direct, suitable for voice playback over a speaker. "
    "Never call yourself WALL-E. "
    "Do not claim autonomous capabilities such as self-driving, obstacle avoidance, person-tracking, "
    "or automatic localization unless explicitly instructed with verified sensor data."
)

@dataclass
class GeminiResponse:
    text: str
    model_used: str
    tokens_used: int = 0
    grounded: bool = False

class BaseGeminiService(ABC):
    @abstractmethod
    def generate_response(
        self,
        prompt: str,
        context: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None
    ) -> GeminiResponse:
        """Generate conversational reasoning response."""
        pass

class GeminiChatService(BaseGeminiService):
    def __init__(self):
        self.api_key = config.GEMINI_API_KEY
        self.model_name = config.GEMINI_MODEL
        self.client = None
        self._init_client()

    def _init_client(self):
        if not self.api_key or config.VISION_TEST_MODE:
            logger.info(f"[GEMINI] Operating in mock/test mode with model '{self.model_name}'.")
            return

        try:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
            logger.info(f"[GEMINI] Initialized Google GenAI client with model '{self.model_name}'.")
        except Exception as e:
            logger.info(f"[GEMINI] SDK client not loaded ({e}); operating in fallback mode.")

    def generate_response(
        self,
        prompt: str,
        context: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None
    ) -> GeminiResponse:
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty.")

        # Build combined prompt with grounding context if provided
        final_prompt = prompt
        if context:
            final_prompt = f"Context from Verified College Documents:\n{context}\n\nUser Question:\n{prompt}"

        # Real Gemini API call if client is configured
        if self.client is not None:
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=final_prompt,
                    config={
                        "system_instruction": DORURU_SYSTEM_PERSONA,
                        "temperature": 0.4,
                        "max_output_tokens": 300,
                    }
                )
                if response and hasattr(response, "text") and response.text:
                    return GeminiResponse(
                        text=response.text.strip(),
                        model_used=self.model_name,
                        grounded=bool(context)
                    )
            except Exception as e:
                logger.warning(f"[GEMINI] API request error ({e}); using local conversational fallback.")

        # Safe mock / conversational fallback
        if context:
            fallback_text = f"According to verified college records: {context[:200]}..."
        else:
            fallback_text = f"Hello! I am DORURU, your lab assistant. How can I help you today?"

        return GeminiResponse(
            text=fallback_text,
            model_used=f"{self.model_name}-fallback",
            grounded=bool(context)
        )

# Global singleton
_gemini_service: Optional[BaseGeminiService] = None

def get_gemini_service() -> BaseGeminiService:
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiChatService()
    return _gemini_service

