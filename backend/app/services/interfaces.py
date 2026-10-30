"""Abstract service interfaces for STT, TTS, Gemini LLM, College Retrieval, and Vision.

These abstract definitions guarantee decoupling: future phases (e.g. Phase 7 faster-whisper/Piper,
Phase 8 Gemini, Phase 9 College RAG, Phase 11 Vision) implement these interfaces without modifying
the core API contracts.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.audio import AudioDeliveryContract, AudioTranscribeResponse
try:
    from app.schemas.query import SourceCitation
except ImportError:
    SourceCitation = Any
try:
    from app.schemas.vision import VisionAnalyzeResponse
except ImportError:
    VisionAnalyzeResponse = Any


class STTService(ABC):
    """Abstract interface for Speech-to-Text inference."""

    @abstractmethod
    async def transcribe(
        self,
        audio_bytes: bytes,
        content_type: str,
        language: Optional[str] = None,
    ) -> AudioTranscribeResponse:
        """Transcribe speech audio bytes into text."""
        pass


class TTSService(ABC):
    """Abstract interface for Text-to-Speech synthesis."""

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
    ) -> Tuple[bytes, AudioDeliveryContract]:
        """Synthesize text into audio bytes and return an ESP32 audio delivery contract."""
        pass


class LLMService(ABC):
    """Abstract interface for conversational intelligence (Gemini)."""

    @abstractmethod
    async def generate_response(
        self,
        prompt: str,
        conversation_history: List[Dict[str, str]],
        retrieved_context: Optional[List[SourceCitation]] = None,
        system_instruction: Optional[str] = None,
    ) -> str:
        """Generate response given user prompt, session history, and optional RAG context."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the environment-configured model identifier (never hardcoded)."""
        pass


class CollegeRetrievalService(ABC):
    """Abstract interface for college knowledge base retrieval (RAG)."""

    @abstractmethod
    async def retrieve(
        self,
        query: str,
        top_k: int = 3,
    ) -> List[SourceCitation]:
        """Search knowledge base and return source-attributed relevant context."""
        pass


class VisionService(ABC):
    """Abstract interface for image analysis and visual understanding."""

    @abstractmethod
    async def analyze_image(
        self,
        image_bytes: bytes,
        prompt: Optional[str] = None,
        content_type: str = "image/jpeg",
    ) -> VisionAnalyzeResponse:
        """Analyze image captured by camera sensor with optional user question."""
        pass
