"""
backend/app/routers/deps.py - Shared Dependencies and Authentication for FastAPI Routers
"""

import hmac
from fastapi import Request, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .. import config

security_bearer = HTTPBearer(auto_error=False)

def verify_device_token(request: Request) -> str:
    """
    Validates X-Device-Token or Authorization Bearer header against config.DEVICE_AUTH_TOKEN.
    Raises HTTP 401 Unauthorized if missing or invalid.
    """
    token = request.headers.get("X-Device-Token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]

    if not token or not hmac.compare_digest(token.strip(), config.DEVICE_AUTH_TOKEN):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid local device token"
        )
    return token

