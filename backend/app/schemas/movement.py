from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class MovementDirection(str, Enum):
    """Strictly bounded movement directions supported by DORURU."""
    STOP = "STOP"
    FORWARD = "FORWARD"
    REVERSE = "REVERSE"
    TURN_LEFT = "TURN_LEFT"
    TURN_RIGHT = "TURN_RIGHT"


class AutonomyLevel(int, Enum):
    """
    DORURU 4-Level Autonomy Capability Framework:
    Level 1: Bounded timed movement using current motors; distance is approximate (ACTIVE).
    Level 2: Obstacle-aware movement requiring distance sensors (DISABLED / UNCONFIRMED).
    Level 3: Odometry-based positioning requiring wheel encoders (DISABLED / UNCONFIRMED).
    Level 4: User-following or destination SLAM requiring tracking sensors (DISABLED / OUT OF SCOPE).
    """
    LEVEL_1_BOUNDED_TIMED = 1
    LEVEL_2_OBSTACLE_AWARE = 2
    LEVEL_3_ODOMETRY_BOUNDED = 3
    LEVEL_4_FULL_AUTONOMOUS = 4


class AutonomyCapabilities(BaseModel):
    """Current hardware capability report and feature flags."""
    active_level: AutonomyLevel = AutonomyLevel.LEVEL_1_BOUNDED_TIMED
    level_name: str = "Level 1: Bounded Timed Movement"
    obstacle_avoidance_enabled: bool = False
    wheel_odometry_enabled: bool = False
    user_following_enabled: bool = False
    slam_navigation_enabled: bool = False
    disclaimer: str = (
        "Without verified wheel encoders and distance sensors, DORURU movements are approximate "
        "and time-bounded only. Autonomous roaming, obstacle avoidance, and user localization are strictly disabled."
    )


class MovementIntentRequest(BaseModel):
    """Natural language or high-level motion command input."""
    text: str = Field(..., min_length=1, max_length=200, description="Spoken or typed user phrase")
    session_id: Optional[str] = Field(None, description="Optional ephemeral session ID")
    speed_override: Optional[int] = Field(None, ge=60, le=220, description="Optional speed clamp [60..220]")
    duration_override_ms: Optional[int] = Field(None, ge=50, le=3000, description="Optional duration clamp [50..3000ms]")


class MovementIntent(BaseModel):
    """Validated structured movement intent."""
    direction: MovementDirection
    speed_pwm: int = Field(150, ge=60, le=220)
    duration_ms: int = Field(1000, ge=50, le=3000)
    autonomy_level: AutonomyLevel = AutonomyLevel.LEVEL_1_BOUNDED_TIMED
    is_approximate_timed: bool = True
    user_localization_used: bool = False
    safety_disclaimer: str
    original_text: str


class MovementCommandPacket(BaseModel):
    """
    Structured, signed/sequenced command packet formatted for transmission
    to Seeed XIAO ESP32-S3 Sense.
    """
    sequence_id: int = Field(..., ge=1, description="Strictly monotonically increasing command counter")
    direction: MovementDirection
    speed_pwm: int = Field(..., ge=0, le=220)
    duration_ms: int = Field(..., ge=0, le=3000)
    timestamp_ms: int = Field(..., ge=0, description="Timestamp in milliseconds when packet was issued (device clock aligned)")
    ttl_ms: int = Field(3000, ge=100, le=3000, description="Packet validity lifetime in milliseconds (aligned with firmware 3000ms max)")
    autonomy_level: int = Field(1, ge=1, le=1, description="Strictly Level 1 (higher levels rejected)")

