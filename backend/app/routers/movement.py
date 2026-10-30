import contextlib
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from backend.app.schemas.movement import (
    MovementIntentRequest,
    MovementIntent,
    MovementCommandPacket,
    AutonomyCapabilities,
)
from backend.app.services.movement_intent_parser import (
    MovementIntentParser,
    UnsupportedAutonomyError,
    UnknownMovementIntentError,
    MovementIntentError,
)

router = APIRouter(prefix="/api/v1/movement", tags=["Movement & Autonomy"])

UINT32_MAX = 4294967295


class DeviceSyncRequest(BaseModel):
    """Handshake parameters reported by Seeed XIAO ESP32-S3 Sense."""
    device_millis: Optional[int] = Field(
        None, ge=0, le=UINT32_MAX, description="Current millis() timestamp from firmware (uint32)"
    )
    last_accepted_sequence_id: Optional[int] = Field(
        None, ge=0, le=UINT32_MAX, description="Highest sequence ID processed by firmware (uint32)"
    )
    reset_sequence: bool = Field(
        False, description="Set True to recover from sequence exhaustion by re-initializing sequence space to 0"
    )


class DeviceSyncResponse(BaseModel):
    status: str
    calibrated_device_timestamp_ms: int
    next_sequence_id: int


class SequencePersistenceError(RuntimeError):
    """Raised when sequence state cannot be allocated or persisted to shared storage."""
    pass


class SequenceExhaustedError(RuntimeError):
    """Raised when the 32-bit sequence ID space is exhausted (current >= UINT32_MAX)."""
    pass


@contextlib.contextmanager
def _interprocess_file_lock(lock_file_path: Path):
    """
    Cross-process file lock providing atomic access across multiple
    backend worker processes / uvicorn workers on Windows and POSIX.
    Converts lock-acquisition OSError failures into SequencePersistenceError.
    """
    try:
        lock_file_path.parent.mkdir(parents=True, exist_ok=True)
        f = open(lock_file_path, "a+b")
    except OSError as e:
        raise SequencePersistenceError(f"Failed to open lock file {lock_file_path}: {e}") from e

    try:
        f.seek(0, os.SEEK_END)
        if f.tell() == 0:
            f.write(b"\0")
            f.flush()
        f.seek(0)
        try:
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        except OSError as e:
            raise SequencePersistenceError(f"Failed to acquire file lock on {lock_file_path}: {e}") from e
        yield f
    finally:
        try:
            f.seek(0)
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        f.close()


class PersistentSequenceManager:
    """
    Sequence source shared across multiple backend worker processes and instances.
    Coordinates atomically via interprocess file locking and shared disk persistence,
    guaranteeing strictly increasing sequence IDs that survive restarts and advance
    above the firmware's last accepted ID to prevent replay attack rejection.
    """
    UINT32_MAX = 4294967295

    def __init__(self, persistence_path: Optional[Path] = None):
        if persistence_path is None:
            env_path = os.environ.get("DORURU_SEQUENCE_FILE")
            if env_path:
                self._path = Path(env_path)
            else:
                self._path = Path(__file__).resolve().parent.parent / "movement_sequence_state.json"
        else:
            self._path = persistence_path
        self._lock_path = self._path.with_suffix(".lock")
        self._thread_lock = threading.Lock()

    def _read_current(self) -> int:
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return int(data.get("last_sequence_id", 0))
            except Exception as e:
                raise SequencePersistenceError(f"Failed to read sequence file {self._path}: {e}") from e
        return 0

    def _write_current(self, seq: int) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self._path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump({"last_sequence_id": seq}, f)
            temp_path.replace(self._path)
        except Exception as e:
            raise SequencePersistenceError(f"Failed to persist sequence ID {seq} to {self._path}: {e}") from e

    def next_id(self) -> int:
        """
        Allocates the next sequence ID atomically from the shared file.
        Rejects allocation if sequence counter has reached UINT32_MAX.
        Propagates SequencePersistenceError on failure so no unsaved ID is issued.
        """
        with self._thread_lock:
            try:
                with _interprocess_file_lock(self._lock_path):
                    current_id = self._read_current()
                    if current_id >= self.UINT32_MAX:
                        raise SequenceExhaustedError(
                            f"Sequence ID exhausted: reached maximum uint32 value ({self.UINT32_MAX}). "
                            "Device re-pairing and sequence reset handshake required."
                        )
                    next_seq = current_id + 1
                    try:
                        self._write_current(next_seq)
                    except SequencePersistenceError:
                        raise
                    except Exception as e:
                        raise SequencePersistenceError(f"Failed to persist sequence ID {next_seq}: {e}") from e
                    return next_seq
            except (SequencePersistenceError, SequenceExhaustedError):
                raise
            except OSError as e:
                raise SequencePersistenceError(f"Lock acquisition failure during next_id: {e}") from e

    def sync_firmware_sequence(self, firmware_last_id: int) -> None:
        """
        Advances the shared sequence counter if the firmware reports a higher last-accepted ID.
        Rejects out-of-range values outside uint32 bounds [0..UINT32_MAX].
        """
        if not (0 <= firmware_last_id <= self.UINT32_MAX):
            raise ValueError(
                f"firmware_last_id {firmware_last_id} is out of uint32 bounds [0..{self.UINT32_MAX}]"
            )

        with self._thread_lock:
            try:
                with _interprocess_file_lock(self._lock_path):
                    current_id = self._read_current()
                    if firmware_last_id >= current_id:
                        self._write_current(firmware_last_id)
            except SequencePersistenceError:
                raise
            except OSError as e:
                raise SequencePersistenceError(f"Lock acquisition failure during sync_firmware_sequence: {e}") from e

    def current_id(self) -> int:
        with self._thread_lock:
            try:
                with _interprocess_file_lock(self._lock_path):
                    return self._read_current()
            except SequencePersistenceError:
                raise
            except OSError as e:
                raise SequencePersistenceError(f"Lock acquisition failure during current_id: {e}") from e

    def reset(self, initial_id: int = 0) -> None:
        with self._thread_lock:
            try:
                with _interprocess_file_lock(self._lock_path):
                    self._write_current(initial_id)
            except SequencePersistenceError:
                raise
            except OSError as e:
                raise SequencePersistenceError(f"Lock acquisition failure during reset: {e}") from e


class DeviceClockReference:
    """
    Aligns packet timestamps with the firmware's millis() clock reference.
    Maintains synchronization via device handshakes or receive-relative age.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._sync_monotonic = time.monotonic()
        self._device_base_millis = 0
        self._is_synchronized = False

    def sync(self, device_millis: int) -> None:
        with self._lock:
            self._sync_monotonic = time.monotonic()
            self._device_base_millis = device_millis
            self._is_synchronized = True

    def get_device_timestamp_ms(self) -> int:
        with self._lock:
            elapsed_ms = int((time.monotonic() - self._sync_monotonic) * 1000)
            return (self._device_base_millis + elapsed_ms) & 0xFFFFFFFF

    def is_synchronized(self) -> bool:
        with self._lock:
            return self._is_synchronized

    def reset(self) -> None:
        with self._lock:
            self._sync_monotonic = time.monotonic()
            self._device_base_millis = 0
            self._is_synchronized = False


# Module singletons
sequence_manager = PersistentSequenceManager()
clock_reference = DeviceClockReference()


def _get_next_sequence_id() -> int:
    return sequence_manager.next_id()


@router.get("/capabilities", response_model=AutonomyCapabilities)
async def get_autonomy_capabilities():
    """
    Returns current active robot autonomy levels and sensor readiness.
    Enforces that Level 1 (bounded timed movement) is active, while
    Levels 2-4 (obstacle avoidance, odometry, user-following) remain disabled.
    """
    return AutonomyCapabilities()


@router.post("/intent", response_model=MovementIntent)
async def parse_movement_intent(request: MovementIntentRequest):
    """
    Translates a natural language phrase into a strictly validated movement intent.
    Rejects forbidden autonomy requests (user-following, roaming) and unverified commands.
    """
    try:
        intent = MovementIntentParser.parse(request)
        return intent
    except UnsupportedAutonomyError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Autonomy request rejected: {str(e)}",
        )
    except (UnknownMovementIntentError, MovementIntentError) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )


@router.post("/command", response_model=MovementCommandPacket)
async def generate_movement_command(intent: MovementIntent):
    """
    Transforms a validated MovementIntent into a sequenced, time-bounded
    command packet formatted for delivery to the Seeed XIAO ESP32-S3 Sense.
    Checks clock synchronization and allocates sequence IDs atomically from
    the shared persistent sequence source.
    """
    # 1. Enforce Level 1 autonomy restriction
    if intent.autonomy_level != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Commands requiring autonomy level > 1 cannot be dispatched to hardware.",
        )

    # 2. Enforce device clock synchronization precondition
    if not clock_reference.is_synchronized():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Device clock is not synchronized. Perform device handshake before generating movement commands.",
        )

    # 3. Allocate sequence ID from shared persistent source
    try:
        seq_id = _get_next_sequence_id()
    except SequenceExhaustedError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Sequence counter exhausted: {str(e)}",
        )
    except SequencePersistenceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sequence persistence failure: {str(e)}",
        )

    device_ts = clock_reference.get_device_timestamp_ms()
    packet = MovementCommandPacket(
        sequence_id=seq_id,
        direction=intent.direction,
        speed_pwm=intent.speed_pwm,
        duration_ms=intent.duration_ms,
        timestamp_ms=device_ts,
        ttl_ms=3000, # Aligned with firmware's MAX_ALLOWABLE_TTL_MS (3000ms)
        autonomy_level=1,
    )
    return packet


@router.post("/handshake", response_model=DeviceSyncResponse)
async def sync_device_state(handshake: DeviceSyncRequest):
    """
    Device clock and sequence handshake endpoint.
    Recovers from sequence exhaustion when reset_sequence=True by re-initializing
    sequence space to 0. Otherwise advances sequence counter above firmware's last ID.
    Synchronizes firmware sequence before clock.
    """
    # 1. Handle recovery reset if requested, or synchronize firmware sequence
    if handshake.reset_sequence:
        try:
            sequence_manager.reset(initial_id=0)
        except SequencePersistenceError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Sequence reset failure: {str(e)}",
            )
    elif handshake.last_accepted_sequence_id is not None:
        try:
            sequence_manager.sync_firmware_sequence(handshake.last_accepted_sequence_id)
        except SequencePersistenceError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Sequence synchronization failure: {str(e)}",
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )

    # 2. Synchronize clock only after successful sequence sync/reset
    if handshake.device_millis is not None:
        clock_reference.sync(handshake.device_millis)

    try:
        next_seq = sequence_manager.current_id() + 1
    except SequencePersistenceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sequence read failure: {str(e)}",
        )

    return DeviceSyncResponse(
        status="RECOVERED_SEQUENCE_RESET" if handshake.reset_sequence else "SYNCHRONIZED",
        calibrated_device_timestamp_ms=clock_reference.get_device_timestamp_ms(),
        next_sequence_id=next_seq,
    )
