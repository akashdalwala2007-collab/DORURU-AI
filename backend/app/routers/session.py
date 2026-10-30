"""
backend/app/routers/session.py - FastAPI Router for Ephemeral Session Lifecycle
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from .. import config
from ..schemas.session import (
    SessionCreateRequest,
    SessionCreateResponse,
    SessionStatusResponse,
    SessionResetRequest,
    SessionResetResponse,
)
from ..session.session_manager import (
    SessionManager,
    MIN_SESSION_TTL_SECONDS,
    MAX_SESSION_TTL_SECONDS,
)
from .deps import verify_device_token

router = APIRouter(prefix="/api/v1/session", tags=["Session Lifecycle"])

# Shared Session Manager singleton
_session_manager = SessionManager(default_ttl_seconds=config.SESSION_EXPIRY_SECONDS)

@router.post("/new", response_model=SessionCreateResponse)
async def create_session(
    payload: SessionCreateRequest = SessionCreateRequest(),
    token: str = Depends(verify_device_token)
):
    """Creates a new ephemeral session with configured or custom TTL."""
    if payload.ttl_seconds is not None:
        if not isinstance(payload.ttl_seconds, int) or isinstance(payload.ttl_seconds, bool):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ttl_seconds must be a valid integer"
            )
        if payload.ttl_seconds < MIN_SESSION_TTL_SECONDS or payload.ttl_seconds > MAX_SESSION_TTL_SECONDS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"ttl_seconds must be between {MIN_SESSION_TTL_SECONDS} and {MAX_SESSION_TTL_SECONDS}"
            )

    try:
        session = _session_manager.create_session(ttl_seconds=payload.ttl_seconds)
        return SessionCreateResponse(
            status="created",
            session_id=session.session_id,
            created_at=session.created_at,
            ttl_seconds=session.ttl_seconds
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/status", response_model=SessionStatusResponse)
async def get_session_status(
    session_id: str = Query(..., description="Active session ID"),
    token: str = Depends(verify_device_token)
):
    """Retrieves session state, active turns count, and expiration info."""
    session = _session_manager.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or has expired"
        )

    session.touch()
    return SessionStatusResponse(
        session_id=session.session_id,
        created_at=session.created_at,
        last_activity_at=session.last_activity_at,
        ttl_seconds=session.ttl_seconds,
        turns_count=len(session.conversation_history),
        is_expired=session.is_expired(),
        active_sessions_count=_session_manager.active_count()
    )

@router.post("/reset", response_model=SessionResetResponse)
async def reset_session(
    payload: SessionResetRequest,
    token: str = Depends(verify_device_token)
):
    """Explicitly wipes all temporary conversation context and history."""
    ok = _session_manager.reset_session(payload.session_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or already purged"
        )

    return SessionResetResponse(
        status="reset",
        session_id=payload.session_id,
        message="Session memory wiped cleanly"
    )

