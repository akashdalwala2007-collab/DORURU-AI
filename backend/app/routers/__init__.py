from .movement import router as movement_router
from .health import router as health_router
from .device import router as device_router
from .voice import router as voice_router
from .session import router as session_router

__all__ = [
    "movement_router",
    "health_router",
    "device_router",
    "voice_router",
    "session_router",
]
