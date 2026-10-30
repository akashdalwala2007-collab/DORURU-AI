import pytest
from fastapi.testclient import TestClient
from pathlib import Path
from backend.app.main import app
from backend.app.schemas.movement import (
    MovementDirection,
    AutonomyLevel,
    MovementIntentRequest,
)
from backend.app.services.movement_intent_parser import (
    MovementIntentParser,
    UnsupportedAutonomyError,
    UnknownMovementIntentError,
    MovementIntentError,
)
from backend.app.routers.movement import (
    PersistentSequenceManager,
    DeviceClockReference,
    SequencePersistenceError,
    SequenceExhaustedError,
    sequence_manager,
    clock_reference,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolate_sequence_and_clock(tmp_path: Path):
    """
    Isolates the module-level sequence_manager by redirecting its state and
    lock paths to tmp_path, and resets clock_reference before and after each test.
    """
    test_state_file = tmp_path / "test_movement_sequence_state.json"
    test_lock_file = tmp_path / "test_movement_sequence_state.lock"

    orig_path = sequence_manager._path
    orig_lock = sequence_manager._lock_path

    sequence_manager._path = test_state_file
    sequence_manager._lock_path = test_lock_file
    clock_reference.reset()

    try:
        yield
    finally:
        clock_reference.reset()
        sequence_manager._path = orig_path
        sequence_manager._lock_path = orig_lock
        if test_state_file.exists():
            try:
                test_state_file.unlink()
            except Exception:
                pass
        if test_lock_file.exists():
            try:
                test_lock_file.unlink()
            except Exception:
                pass


def test_stop_phrases():
    for phrase in [
        "stop",
        "halt",
        "freeze",
        "emergency stop",
        "brake",
        "don't move",
        "do not move",
        "stop in 10 seconds",
        "don't move right now",
        "do not move right now",
        "stop patrol",
        "stop following me",
    ]:
        req = MovementIntentRequest(text=phrase)
        intent = MovementIntentParser.parse(req)
        assert intent.direction == MovementDirection.STOP
        assert intent.autonomy_level == AutonomyLevel.LEVEL_1_BOUNDED_TIMED


def test_forward_phrases():
    for phrase in ["forward", "go forward", "move forward", "drive forward"]:
        req = MovementIntentRequest(text=phrase)
        intent = MovementIntentParser.parse(req)
        assert intent.direction == MovementDirection.FORWARD
        assert intent.is_approximate_timed is True
        assert 60 <= intent.speed_pwm <= 220
        assert 50 <= intent.duration_ms <= 3000


def test_bare_direction_words_rejected():
    for bare_word in ["ahead", "straight", "left", "right"]:
        with pytest.raises(UnknownMovementIntentError):
            MovementIntentParser.parse(MovementIntentRequest(text=bare_word))


def test_negated_movement_commands_rejected():
    # Negated commands must not produce movement intents
    for negated in [
        "do not move forward",
        "don't go forward",
        "never turn left",
        "do not turn right",
        "don't go back",
        "cannot move forward",
        "no forward motion",
        "don't move right",
        "do not move right",
    ]:
        with pytest.raises(UnknownMovementIntentError):
            MovementIntentParser.parse(MovementIntentRequest(text=negated))


def test_come_here_disclaimer_and_no_localization():
    req = MovementIntentRequest(text="come here")
    intent = MovementIntentParser.parse(req)
    assert intent.direction == MovementDirection.FORWARD
    assert intent.user_localization_used is False
    assert intent.is_approximate_timed is True
    assert "does NOT locate user" in intent.safety_disclaimer
    assert "approximate" in intent.safety_disclaimer


def test_go_back_disclaimer():
    req = MovementIntentRequest(text="go back")
    intent = MovementIntentParser.parse(req)
    assert intent.direction == MovementDirection.REVERSE
    assert intent.is_approximate_timed is True
    assert "approximate" in intent.safety_disclaimer


def test_turning_phrases():
    req_left = MovementIntentRequest(text="turn left")
    intent_left = MovementIntentParser.parse(req_left)
    assert intent_left.direction == MovementDirection.TURN_LEFT

    req_right = MovementIntentRequest(text="turn right")
    intent_right = MovementIntentParser.parse(req_right)
    assert intent_right.direction == MovementDirection.TURN_RIGHT


def test_rejection_of_unsupported_autonomy():
    # User-following requests (Level 4 - disabled)
    for forbidden in ["follow me", "track person", "follow the user"]:
        with pytest.raises(UnsupportedAutonomyError):
            MovementIntentParser.parse(MovementIntentRequest(text=forbidden))

    # Autonomous roaming & SLAM (Level 2/3/4 - disabled)
    for forbidden in ["roam around", "patrol the hallway", "explore", "go to room 101"]:
        with pytest.raises(UnsupportedAutonomyError):
            MovementIntentParser.parse(MovementIntentRequest(text=forbidden))


def test_unknown_phrases_rejected():
    for unknown in ["sing a song", "make coffee", "do a flip", "xyz123"]:
        with pytest.raises(UnknownMovementIntentError):
            MovementIntentParser.parse(MovementIntentRequest(text=unknown))


def test_duration_parsing_and_bounds():
    # 2 seconds -> 2000ms
    req = MovementIntentRequest(text="move forward for 2 seconds")
    intent = MovementIntentParser.parse(req)
    assert intent.duration_ms == 2000

    # 500 ms -> 500ms
    req_ms = MovementIntentRequest(text="move forward for 500 ms")
    intent_ms = MovementIntentParser.parse(req_ms)
    assert intent_ms.duration_ms == 500

    # Exceeding 3000ms ceiling must be rejected
    req_excessive = MovementIntentRequest(text="move forward for 10 seconds")
    with pytest.raises(MovementIntentError):
        MovementIntentParser.parse(req_excessive)


def test_capabilities_api_endpoint():
    response = client.get("/api/v1/movement/capabilities")
    assert response.status_code == 200
    data = response.json()
    assert data["active_level"] == 1
    assert data["obstacle_avoidance_enabled"] is False
    assert data["wheel_odometry_enabled"] is False
    assert data["user_following_enabled"] is False
    assert data["slam_navigation_enabled"] is False
    assert "approximate and time-bounded only" in data["disclaimer"]


def test_intent_and_command_api_lifecycle():
    # 1. Parse "come here"
    intent_resp = client.post("/api/v1/movement/intent", json={"text": "come here"})
    assert intent_resp.status_code == 200
    intent_data = intent_resp.json()
    assert intent_data["direction"] == "FORWARD"
    assert intent_data["user_localization_used"] is False

    # 2. Synchronize device clock prior to issuing commands
    sync_resp = client.post(
        "/api/v1/movement/handshake",
        json={"device_millis": 12000, "last_accepted_sequence_id": 5},
    )
    assert sync_resp.status_code == 200

    # 3. Generate command packet from intent
    cmd_resp = client.post("/api/v1/movement/command", json=intent_data)
    assert cmd_resp.status_code == 200
    cmd_data = cmd_resp.json()
    assert cmd_data["sequence_id"] >= 6
    assert cmd_data["direction"] == "FORWARD"
    assert cmd_data["ttl_ms"] == 3000
    assert cmd_data["autonomy_level"] == 1
    assert cmd_data["timestamp_ms"] >= 12000

    # 4. Test forbidden autonomy rejection via API
    forbidden_resp = client.post("/api/v1/movement/intent", json={"text": "follow me"})
    assert forbidden_resp.status_code == 400
    assert "Autonomy request rejected" in forbidden_resp.json()["detail"]


def test_unsynchronized_clock_command_rejected():
    assert clock_reference.is_synchronized() is False

    intent = {
        "direction": "FORWARD",
        "speed_pwm": 150,
        "duration_ms": 1000,
        "autonomy_level": 1,
        "is_approximate_timed": True,
        "user_localization_used": False,
        "safety_disclaimer": "test",
        "original_text": "move forward",
    }
    # Command must be rejected when clock is not synchronized
    resp = client.post("/api/v1/movement/command", json=intent)
    assert resp.status_code == 400
    assert "clock is not synchronized" in resp.json()["detail"].lower()

    # Once synchronized, command succeeds
    clock_reference.sync(device_millis=5000)
    resp2 = client.post("/api/v1/movement/command", json=intent)
    assert resp2.status_code == 200


def test_shared_sequence_across_instances(tmp_path: Path):
    test_file = tmp_path / "shared_seq.json"
    mgr_worker1 = PersistentSequenceManager(persistence_path=test_file)
    mgr_worker2 = PersistentSequenceManager(persistence_path=test_file)

    id1 = mgr_worker1.next_id()
    id2 = mgr_worker2.next_id()
    id3 = mgr_worker1.next_id()
    id4 = mgr_worker2.next_id()

    assert [id1, id2, id3, id4] == [1, 2, 3, 4]


def test_sequence_persistence_across_restarts(tmp_path: Path):
    test_file = tmp_path / "test_seq.json"
    mgr1 = PersistentSequenceManager(persistence_path=test_file)
    id1 = mgr1.next_id()
    id2 = mgr1.next_id()
    assert id2 == id1 + 1

    # Simulate backend restart by creating a new manager reading the same file
    mgr2 = PersistentSequenceManager(persistence_path=test_file)
    id3 = mgr2.next_id()
    assert id3 == id2 + 1

    # Simulate firmware handshake reporting higher ID (e.g. 50)
    mgr2.sync_firmware_sequence(50)
    id4 = mgr2.next_id()
    assert id4 == 51


def test_persistence_error_propagation(tmp_path: Path, monkeypatch):
    test_file = tmp_path / "readonly_seq.json"
    mgr = PersistentSequenceManager(persistence_path=test_file)

    def failing_write(*args, **kwargs):
        raise OSError("Disk full / read-only filesystem simulation")

    monkeypatch.setattr(mgr, "_write_current", failing_write)

    with pytest.raises(SequencePersistenceError):
        mgr.next_id()


def test_lock_acquisition_oserror_converts_to_sequence_persistence_error(tmp_path: Path, monkeypatch):
    test_file = tmp_path / "lock_fail.json"
    mgr = PersistentSequenceManager(persistence_path=test_file)

    def failing_open(*args, **kwargs):
        raise OSError("Lock file permission denied")

    # Mock open when opening the lock file
    orig_open = open
    def mock_open(file, *args, **kwargs):
        if str(file).endswith(".lock"):
            raise OSError("Lock file permission denied")
        return orig_open(file, *args, **kwargs)

    monkeypatch.setattr("builtins.open", mock_open)

    with pytest.raises(SequencePersistenceError):
        mgr.next_id()

    with pytest.raises(SequencePersistenceError):
        mgr.sync_firmware_sequence(10)

    with pytest.raises(SequencePersistenceError):
        mgr.current_id()

    with pytest.raises(SequencePersistenceError):
        mgr.reset()


def test_sync_firmware_sequence_uint32_bounds(tmp_path: Path):
    test_file = tmp_path / "bounds_seq.json"
    mgr = PersistentSequenceManager(persistence_path=test_file)

    # Valid uint32 boundaries
    mgr.sync_firmware_sequence(0)
    assert mgr.current_id() == 0

    mgr.sync_firmware_sequence(4294967295)
    assert mgr.current_id() == 4294967295

    # Out of bounds (< 0 or > 4294967295) must be rejected
    with pytest.raises(ValueError):
        mgr.sync_firmware_sequence(-1)

    with pytest.raises(ValueError):
        mgr.sync_firmware_sequence(4294967296)


def test_handshake_uint32_bounds_validation():
    # Out of range device_millis (> uint32 max)
    resp1 = client.post("/api/v1/movement/handshake", json={"device_millis": 4294967296})
    assert resp1.status_code == 422

    # Out of range last_accepted_sequence_id (> uint32 max)
    resp2 = client.post("/api/v1/movement/handshake", json={"last_accepted_sequence_id": 4294967296})
    assert resp2.status_code == 422

    # Valid max uint32 boundary succeeds
    resp3 = client.post(
        "/api/v1/movement/handshake",
        json={"device_millis": 4294967295, "last_accepted_sequence_id": 4294967294},
    )
    assert resp3.status_code == 200


def test_handshake_sequence_persistence_error_returns_500(monkeypatch):
    def failing_sync(firmware_last_id: int):
        raise SequencePersistenceError("Storage locked")

    monkeypatch.setattr(sequence_manager, "sync_firmware_sequence", failing_sync)

    resp = client.post(
        "/api/v1/movement/handshake",
        json={"device_millis": 5000, "last_accepted_sequence_id": 10},
    )
    assert resp.status_code == 500
    assert "Sequence synchronization failure" in resp.json()["detail"]
    # Verify clock was NOT synchronized because sequence sync failed first
    assert clock_reference.is_synchronized() is False


def test_device_handshake_endpoint():
    response = client.post(
        "/api/v1/movement/handshake",
        json={"device_millis": 5000, "last_accepted_sequence_id": 10},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SYNCHRONIZED"
    assert data["next_sequence_id"] >= 11
    assert data["calibrated_device_timestamp_ms"] >= 5000


def test_sequence_exhaustion_rejected_before_persistence(tmp_path: Path):
    test_file = tmp_path / "exhaustion_seq.json"
    mgr = PersistentSequenceManager(persistence_path=test_file)

    # Set to uint32 max
    mgr.reset(PersistentSequenceManager.UINT32_MAX)
    assert mgr.current_id() == PersistentSequenceManager.UINT32_MAX

    # Allocating beyond uint32 max must raise SequenceExhaustedError
    with pytest.raises(SequenceExhaustedError):
        mgr.next_id()

    # Current ID must still be UINT32_MAX; nothing > UINT32_MAX persisted
    assert mgr.current_id() == PersistentSequenceManager.UINT32_MAX


def test_command_generation_sequence_exhaustion_returns_409():
    # Sync clock first
    clock_reference.sync(device_millis=1000)

    # Set sequence to uint32 max
    sequence_manager.reset(PersistentSequenceManager.UINT32_MAX)

    intent = {
        "direction": "FORWARD",
        "speed_pwm": 150,
        "duration_ms": 1000,
        "autonomy_level": 1,
        "is_approximate_timed": True,
        "user_localization_used": False,
        "safety_disclaimer": "test",
        "original_text": "move forward",
    }
    resp = client.post("/api/v1/movement/command", json=intent)
    assert resp.status_code == 409
    assert "sequence counter exhausted" in resp.json()["detail"].lower()


def test_sequence_exhaustion_recovery_handshake():
    # 1. Simulate exhaustion
    sequence_manager.reset(PersistentSequenceManager.UINT32_MAX)

    # 2. Perform recovery handshake with reset_sequence=True
    recovery_resp = client.post(
        "/api/v1/movement/handshake",
        json={"reset_sequence": True, "device_millis": 3000},
    )
    assert recovery_resp.status_code == 200
    assert recovery_resp.json()["status"] == "RECOVERED_SEQUENCE_RESET"
    assert recovery_resp.json()["next_sequence_id"] == 1
    assert sequence_manager.current_id() == 0

    # 3. Generating command now succeeds with sequence_id = 1
    intent = {
        "direction": "FORWARD",
        "speed_pwm": 150,
        "duration_ms": 1000,
        "autonomy_level": 1,
        "is_approximate_timed": True,
        "user_localization_used": False,
        "safety_disclaimer": "test",
        "original_text": "move forward",
    }
    cmd_resp = client.post("/api/v1/movement/command", json=intent)
    assert cmd_resp.status_code == 200
    assert cmd_resp.json()["sequence_id"] == 1

