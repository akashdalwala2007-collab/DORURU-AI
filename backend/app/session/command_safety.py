"""
backend/app/session/command_safety.py - Movement Intent Validation and Stale Command Rejection

Security & Safety Rules:
- Commands are strictly validated: speed and duration bounds enforced.
- Monotonic sequence numbers prevent replay attacks.
- Timestamps and TTL ensure stale commands are discarded.
- Emergency stop always supersedes any movement command.
- When offline, movement is blocked unless explicitly enabled by safe configuration.
"""

from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class MovementIntent(str, Enum):
    STOP = "STOP"
    FORWARD = "FORWARD"
    REVERSE = "REVERSE"
    TURN_LEFT = "TURN_LEFT"
    TURN_RIGHT = "TURN_RIGHT"
    EMERGENCY_STOP = "EMERGENCY_STOP"

MAX_ALLOWED_DURATION_MS = 2000 # Max 2.0s bounded movement
MIN_ALLOWED_DURATION_MS = 50
MAX_ALLOWED_SPEED = 255
DEFAULT_COMMAND_TTL_MS = 1000  # Stale after 1.0 second

class MovementCommand(BaseModel):
    command_id: int = Field(..., description="Monotonically increasing sequence number")
    intent: MovementIntent
    speed: int = Field(default=150, description="Motor PWM speed [0, 255]")
    duration_ms: int = Field(default=500, description="Movement duration in ms [50, 2000]")
    timestamp_ms: int = Field(..., description="Timestamp in milliseconds when command was issued")
    ttl_ms: int = Field(default=DEFAULT_COMMAND_TTL_MS, ge=100, le=5000)

class CommandValidationResult(BaseModel):
    valid: bool
    reason: str
    command: Optional[MovementCommand] = None

def validate_movement_command(
    command_dict: Dict[str, Any],
    current_time_ms: int,
    last_sequence_id: int,
    is_online: bool = True,
    allow_offline_movement: bool = False,
    is_emergency_stop_active: bool = False
) -> CommandValidationResult:
    """
    Validates a movement command against safety, replay, staleness, and offline constraints.
    """
    # 1. Emergency stop check
    if is_emergency_stop_active:
        return CommandValidationResult(
            valid=False,
            reason="Emergency stop is currently engaged. All movement commands rejected."
        )

    # 2. Schema parse & validation
    try:
        cmd = MovementCommand(**command_dict)
    except Exception as e:
        return CommandValidationResult(
            valid=False,
            reason=f"Invalid command schema: {str(e)}"
        )

    # 3. Emergency stop command always succeeds in stopping
    if cmd.intent == MovementIntent.EMERGENCY_STOP or cmd.intent == MovementIntent.STOP:
        return CommandValidationResult(valid=True, reason="Stop intent accepted", command=cmd)

    # 4. Monotonic sequence check (Replay Prevention)
    if cmd.command_id <= last_sequence_id:
        return CommandValidationResult(
            valid=False,
            reason=f"Stale or duplicate sequence ID {cmd.command_id} <= {last_sequence_id}. Replay rejected."
        )

    # 5. Staleness check (Timestamp + TTL)
    elapsed_ms = current_time_ms - cmd.timestamp_ms
    if elapsed_ms > cmd.ttl_ms:
        return CommandValidationResult(
            valid=False,
            reason=f"Command expired: issued {elapsed_ms}ms ago, TTL is {cmd.ttl_ms}ms. Stale command rejected."
        )
    if elapsed_ms < -2000:
        return CommandValidationResult(
            valid=False,
            reason="Command has future timestamp exceeding clock skew tolerance. Rejected."
        )

    # 6. Offline movement safety check
    if not is_online and not allow_offline_movement:
        return CommandValidationResult(
            valid=False,
            reason="Device is currently offline. Remote movement commands are disabled."
        )

    # 7. Clamping bounds
    clamped_speed = max(0, min(MAX_ALLOWED_SPEED, cmd.speed))
    clamped_duration = max(MIN_ALLOWED_DURATION_MS, min(MAX_ALLOWED_DURATION_MS, cmd.duration_ms))
    sanitized = MovementCommand(
        command_id=cmd.command_id,
        intent=cmd.intent,
        speed=clamped_speed,
        duration_ms=clamped_duration,
        timestamp_ms=cmd.timestamp_ms,
        ttl_ms=cmd.ttl_ms
    )

    return CommandValidationResult(valid=True, reason="Command validated successfully", command=sanitized)
