"""
backend/app/vision/schemas.py - Pydantic Request & Response Models for Vision Pipeline
"""

from typing import Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field

class VisionTriggerType(str, Enum):
    ON_DEMAND = "on_demand"
    SELECTED_EVENT = "selected_event"

class VisionImageMetadata(BaseModel):
    width: int
    height: int
    format: str
    original_bytes: int
    processed_bytes: int
    was_resized: bool
    was_compressed: bool

class VisionAnalysisResponse(BaseModel):
    status: str
    device_id: str
    trigger_type: VisionTriggerType
    context_prompt: str
    answer: str
    latency_ms: float
    image_metadata: VisionImageMetadata
    ephemeral: bool = True
    model_used: str
    error: Optional[str] = None

