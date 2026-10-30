"""
backend/app/schemas/session.py - Pydantic Schemas for Ephemeral Session Lifecycle
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator

class SessionCreateRequest(BaseModel):
    """Session creation parameters."""
    ttl_seconds: Optional[int] = Field(None, ge=1, le=86400, description="Optional custom TTL (1 to 86400s)")
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("ttl_seconds", mode="before")
    @classmethod
    def validate_ttl_seconds(cls, v):
        if v is not None and isinstance(v, bool):
            raise ValueError("ttl_seconds must be an integer, not a boolean")
        return v

class SessionCreateResponse(BaseModel):
    """Session creation confirmation."""
    status: str
    session_id: str
    created_at: float
    ttl_seconds: int

class SessionStatusResponse(BaseModel):
    """Active session status report."""
    session_id: str
    created_at: float
    last_activity_at: float
    ttl_seconds: int
    turns_count: int
    is_expired: bool
    active_sessions_count: int

class SessionResetRequest(BaseModel):
    """Session wipe request."""
    session_id: str

class SessionResetResponse(BaseModel):
    """Session wipe confirmation."""
    status: str
    session_id: str
    message: str
