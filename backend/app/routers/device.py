"""
backend/app/routers/device.py - Device Identity, Registration, and Telemetry
"""

import time
import uuid
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from .. import config
from ..schemas.device import (
    DeviceRegisterRequest,
    DeviceRegisterResponse,
    DeviceStatusRequest,
    DeviceStatusResponse,
)
from .deps import verify_device_token

router = APIRouter(prefix="/api/v1/device", tags=["Device Management"])

# In-memory registry of validated devices
_registered_devices: Dict[str, Dict[str, Any]] = {}

@router.post("/register", response_model=DeviceRegisterResponse)
async def register_device(
    payload: DeviceRegisterRequest,
    token: str = Depends(verify_device_token)
):
    """
    Registers a Seeed XIAO ESP32-S3 Sense robot device using verified local credentials.
    Generates an active per-device session token.
    """
    # Enforce device ID allowlist check
    if config.DEVICE_ID_ALLOWLIST and payload.device_id not in config.DEVICE_ID_ALLOWLIST:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Device '{payload.device_id}' is not in the allowed devices registry."
        )

    session_token = str(uuid.uuid4())
    _registered_devices[payload.device_id] = {
        "hardware_version": payload.hardware_version,
        "firmware_version": payload.firmware_version,
        "mac_address": payload.mac_address,
        "capabilities": payload.capabilities,
        "session_token": session_token,
        "registered_at": time.time(),
        "last_seen_at": time.time()
    }

    return DeviceRegisterResponse(
        status="registered",
        device_id=payload.device_id,
        session_token=session_token,
        server_timestamp=time.time(),
        message="Device identity registered successfully"
    )

@router.get("/registered")
async def list_registered_devices(token: str = Depends(verify_device_token)):
    """List registered devices in active memory."""
    return {
        "count": len(_registered_devices),
        "devices": [
            {
                "device_id": did,
                "hardware_version": info["hardware_version"],
                "firmware_version": info["firmware_version"],
                "registered_at": info["registered_at"],
                "last_seen_at": info["last_seen_at"]
            }
            for did, info in _registered_devices.items()
        ]
    }

