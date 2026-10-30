"""
backend/app/schemas/device.py - Pydantic Schemas for Device Management & Identity
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class DeviceRegisterRequest(BaseModel):
    """Registration and identity envelope from Seeed XIAO ESP32-S3 Sense."""
    device_id: str = Field(..., min_length=3, max_length=64, description="Unique device identifier (e.g. DORURU-SENSE-01)")
    hardware_version: str = Field(default="XIAO-ESP32-S3-Sense", max_length=64)
    firmware_version: str = Field(default="1.0.0", max_length=32)
    mac_address: Optional[str] = Field(None, max_length=32)
    capabilities: List[str] = Field(default_factory=lambda: ["camera", "display", "motor", "audio_out", "pdm_mic"])

class DeviceRegisterResponse(BaseModel):
    """Device registration confirmation and session authorization."""
    status: str
    device_id: str
    session_token: str
    server_timestamp: float
    message: str

class DeviceStatusRequest(BaseModel):
    """Telemetry report and heartbeat payload."""
    device_id: str = Field(..., max_length=64)
    is_emergency_stop: bool = False
    last_sequence_id: int = Field(0, ge=0)
    free_heap_bytes: Optional[int] = None
    free_psram_bytes: Optional[int] = None
    wifi_rssi: Optional[int] = None

class DeviceStatusResponse(BaseModel):
    """Server status exchange and heartbeat confirmation."""
    status: str
    server_timestamp: float
    last_heartbeat_time: float
    is_emergency_stop: bool
    last_sequence_id: int
    online_features: List[str]
    offline_features: List[str]
    offline_disclaimers: List[str]

