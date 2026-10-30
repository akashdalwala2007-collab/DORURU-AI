"""
tests/test_session_recovery.py - Test Suite for Phase 13 Offline Fallback, Session Lifecycle & Recovery

Tests:
1. Session creation, activity touching, and conversation turn tracking.
2. Session expiry after inactivity with strict memory wiping.
3. Explicit session reset clearing all temporary context and conversation history.
4. Movement command validation: bounded speed and duration.
5. Stale command rejection based on timestamp age exceeding TTL.
6. Sequence replay rejection (monotonic sequence IDs).
7. Network recovery guarantee: old queued motor commands cannot be replayed.
8. Emergency stop priority: immediately halts and rejects any movement.
9. Offline fallback: motors stop on network drop, display updates to offline state.
10. Exponential backoff and in-flight request cancellation on network loss.
11. Full HTTP endpoints for session lifecycle, device heartbeat, and command dispatch.
12. Offline capabilities disclosure: disclaims cloud conversation/vision offline.
"""

import os
os.environ.setdefault("DORURU_DEVICE_TOKEN", "test_mock_device_token_12345")
os.environ.setdefault("VISION_TEST_MODE", "true")

import unittest
import time
import json
import subprocess
import concurrent.futures
from backend.app.main import app, server_device_state, device_command_lock
from backend.app import config
from backend.app.session.session_manager import SessionManager, Session
from backend.app.session.command_safety import (
    validate_movement_command,
    MovementCommand,
    MovementIntent
)
from tests.host_test_helper import ensure_compiled_host_firmware_test

class TestSessionLifecycleAndRecovery(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.valid_token = config.DEVICE_AUTH_TOKEN
        self.device_id = "DORURU-SENSE-01"
        self.auth_headers = {
            "Content-Type": "application/json",
            "X-Device-ID": self.device_id,
            "X-Device-Token": self.valid_token
        }
        # Reset server device state
        server_device_state["is_emergency_stop"] = False
        server_device_state["last_sequence_id"] = 0
        server_device_state["allow_offline_movement"] = False

    # =========================================================================
    # 1. SESSION LIFECYCLE & EPHEMERAL MEMORY TESTS
    # =========================================================================

    def test_session_creation_and_turn_tracking(self):
        """Verifies session initializes and tracks conversation turns."""
        sm = SessionManager(default_ttl_seconds=60)
        session = sm.create_session()
        self.assertIsNotNone(session.session_id)
        self.assertFalse(session.is_expired())

        session.add_message("user", "Hello DORURU")
        session.add_message("assistant", "Hello! I am ready to help.")
        self.assertEqual(len(session.conversation_history), 2)
        self.assertEqual(session.conversation_history[0]["content"], "Hello DORURU")

    def test_session_expiry_clears_memory(self):
        """Verifies that an expired session strictly purges its memory and cannot be accessed."""
        sm = SessionManager(default_ttl_seconds=10) # 10 second TTL
        session = sm.create_session()
        session.add_message("user", "Secret temporary context")
        session_id = session.session_id

        # Simulate 15 seconds passing (exceeding 10s TTL)
        future_time = session.last_activity_at + 15.0
        self.assertTrue(session.is_expired(current_time=future_time))

        # Cleanup expired sessions
        purged = sm.cleanup_expired(current_time=future_time)
        self.assertEqual(purged, 1)

        # Getting session after expiry must return None and memory must be cleared
        retrieved = sm.get_session(session_id)
        self.assertIsNone(retrieved)
        self.assertEqual(len(session.conversation_history), 0)

    def test_session_reset_wipes_context_completely(self):
        """Verifies explicit session reset wipes memory and issues a clean session."""
        sm = SessionManager(default_ttl_seconds=60)
        session = sm.create_session()
        session.add_message("user", "Campus question details")
        session.context["topic"] = "Admissions"
        old_id = session.session_id

        fresh = sm.reset_session(old_id)
        self.assertNotEqual(fresh.session_id, old_id)
        self.assertEqual(len(fresh.conversation_history), 0)
        self.assertEqual(len(fresh.context), 0)
        # Old session should no longer exist
        self.assertIsNone(sm.get_session(old_id))

    def test_session_manager_purges_expired_before_adding_new_and_caps_size(self):
        """Verifies create_session purges expired sessions under lock and enforces max size."""
        sm = SessionManager(default_ttl_seconds=10, max_sessions=2)
        s1 = sm.create_session()
        s2 = sm.create_session()
        self.assertEqual(len(sm._sessions), 2)

        # Expire s1
        s1.last_activity_at = time.time() - 20

        # Creating s3 should purge expired s1 and succeed without exceeding capacity
        s3 = sm.create_session()
        self.assertNotIn(s1.session_id, sm._sessions)
        self.assertIn(s2.session_id, sm._sessions)
        self.assertIn(s3.session_id, sm._sessions)
        self.assertEqual(len(sm._sessions), 2)

        # Creating s4 when capacity is full of active sessions should raise RuntimeError
        with self.assertRaises(RuntimeError):
            sm.create_session()

        # Reject invalid TTLs in SessionManager.create_session
        with self.assertRaises(ValueError):
            sm.create_session(ttl_seconds=-5)
        with self.assertRaises(ValueError):
            sm.create_session(ttl_seconds=0)
        with self.assertRaises(ValueError):
            sm.create_session(ttl_seconds="invalid")
        with self.assertRaises(ValueError):
            sm.create_session(ttl_seconds=True)
        with self.assertRaises(ValueError):
            sm.create_session(ttl_seconds=99999999)

    def test_session_new_invalid_ttl_returns_400(self):
        """Verifies POST /api/v1/session/new returns 400 for invalid TTLs."""
        invalid_ttls = [-10, 0, "not_an_int", 12.5, True, 99999999]
        for bad_ttl in invalid_ttls:
            resp = self.client.post("/api/v1/session/new",
                                    data=json.dumps({"ttl_seconds": bad_ttl}),
                                    headers={"Content-Type": "application/json"})
            self.assertEqual(resp.status_code, 400, f"Expected 400 for ttl={bad_ttl}")
            data = json.loads(resp.data)
            self.assertEqual(data["error"], "Bad Request")

    # =========================================================================
    # 2. MOVEMENT COMMAND SAFETY & STALE-COMMAND REJECTION
    # =========================================================================

    def test_command_validation_bounds_and_clamping(self):
        """Verifies valid commands are accepted and speed/duration are clamped."""
        now_ms = 10000
        cmd_dict = {
            "command_id": 1,
            "intent": "FORWARD",
            "speed": 300,        # Exceeds max 255 -> clamped to 255
            "duration_ms": 3000, # Exceeds max 2000 -> clamped to 2000
            "timestamp_ms": now_ms,
            "ttl_ms": 1000
        }
        res = validate_movement_command(
            command_dict=cmd_dict,
            current_time_ms=now_ms + 100,
            last_sequence_id=0,
            is_online=True
        )
        self.assertTrue(res.valid)
        self.assertEqual(res.command.speed, 255)
        self.assertEqual(res.command.duration_ms, 2000)

    def test_stale_command_rejection_via_ttl(self):
        """Verifies commands older than their TTL are strictly rejected."""
        issue_time_ms = 10000
        cmd_dict = {
            "command_id": 2,
            "intent": "FORWARD",
            "speed": 150,
            "duration_ms": 500,
            "timestamp_ms": issue_time_ms,
            "ttl_ms": 500 # 500ms TTL
        }
        # Processed 800ms later (> 500ms TTL)
        res = validate_movement_command(
            command_dict=cmd_dict,
            current_time_ms=issue_time_ms + 800,
            last_sequence_id=1,
            is_online=True
        )
        self.assertFalse(res.valid)
        self.assertIn("expired", res.reason.lower())
        self.assertIn("stale", res.reason.lower())

    def test_sequence_replay_rejection(self):
        """Verifies sequence numbers <= last_sequence_id are rejected to prevent replay."""
        now_ms = 10000
        cmd_dict = {
            "command_id": 5, # Sequence 5
            "intent": "TURN_LEFT",
            "speed": 120,
            "duration_ms": 300,
            "timestamp_ms": now_ms,
            "ttl_ms": 1000
        }
        # Last processed sequence is already 5
        res = validate_movement_command(
            command_dict=cmd_dict,
            current_time_ms=now_ms + 50,
            last_sequence_id=5,
            is_online=True
        )
        self.assertFalse(res.valid)
        self.assertIn("replay", res.reason.lower())

    def test_emergency_stop_priority_rejects_movement(self):
        """Verifies that an active emergency stop rejects all movement commands."""
        now_ms = 10000
        cmd_dict = {
            "command_id": 10,
            "intent": "FORWARD",
            "speed": 150,
            "duration_ms": 500,
            "timestamp_ms": now_ms,
            "ttl_ms": 1000
        }
        res = validate_movement_command(
            command_dict=cmd_dict,
            current_time_ms=now_ms + 50,
            last_sequence_id=9,
            is_online=True,
            is_emergency_stop_active=True
        )
        self.assertFalse(res.valid)
        self.assertIn("emergency stop", res.reason.lower())

    def test_offline_movement_disabled_by_default(self):
        """Verifies movement is blocked while offline unless explicitly enabled."""
        now_ms = 10000
        cmd_dict = {
            "command_id": 15,
            "intent": "FORWARD",
            "speed": 150,
            "duration_ms": 500,
            "timestamp_ms": now_ms,
            "ttl_ms": 1000
        }
        # 1. Offline and allow_offline_movement = False -> Rejected
        res_blocked = validate_movement_command(
            command_dict=cmd_dict,
            current_time_ms=now_ms + 50,
            last_sequence_id=14,
            is_online=False,
            allow_offline_movement=False
        )
        self.assertFalse(res_blocked.valid)
        self.assertIn("offline", res_blocked.reason.lower())

        # 2. Offline and allow_offline_movement = True -> Accepted
        res_allowed = validate_movement_command(
            command_dict=cmd_dict,
            current_time_ms=now_ms + 50,
            last_sequence_id=14,
            is_online=False,
            allow_offline_movement=True
        )
        self.assertTrue(res_allowed.valid)

    # =========================================================================
    # 3. FIRMWARE HOST TESTS: NETWORK LOSS, RECONNECT, NO REPLAY
    # =========================================================================

    def test_host_firmware_safety_and_network_recovery(self):
        """
        Executes host C++ binary verifying:
        - Network loss causes immediate motor stop and display offline state.
        - Network reconnect cannot replay old pre-disconnect commands.
        - Command timeout watchdog halts motors.
        - Exponential backoff doubles reconnect delays.
        - In-flight requests are cancelled on network drop.
        """
        exe_path = ensure_compiled_host_firmware_test()
        proc = subprocess.run([str(exe_path)], capture_output=True, text=True, check=True)

        self.assertIn("[PASS] Motor safety, watchdog, stale-rejection & e-stop verified", proc.stdout)
        self.assertIn("[PASS] Connectivity manager, exponential backoff & cancellation verified", proc.stdout)
        self.assertIn("Network loss detected! Motors immediately halted", proc.stdout)
        self.assertEqual(proc.returncode, 0)

    # =========================================================================
    # 4. HTTP API ENDPOINTS VERIFICATION
    # =========================================================================

    def test_session_endpoints_lifecycle(self):
        """Verifies /api/v1/session/new, /status, and /reset endpoints."""
        # Create session
        resp_new = self.client.post("/api/v1/session/new",
                                    data=json.dumps({"ttl_seconds": 120}),
                                    headers={"Content-Type": "application/json"})
        self.assertEqual(resp_new.status_code, 201)
        data_new = json.loads(resp_new.data)
        sid = data_new["session"]["session_id"]

        # Check status
        resp_status = self.client.get(f"/api/v1/session/status?session_id={sid}")
        self.assertEqual(resp_status.status_code, 200)
        data_status = json.loads(resp_status.data)
        self.assertEqual(data_status["session"]["session_id"], sid)

        # Reset session
        resp_reset = self.client.post("/api/v1/session/reset",
                                     data=json.dumps({"session_id": sid}),
                                     headers={"Content-Type": "application/json"})
        self.assertEqual(resp_reset.status_code, 200)
        data_reset = json.loads(resp_reset.data)
        self.assertEqual(data_reset["status"], "reset_successful")
        self.assertNotEqual(data_reset["session"]["session_id"], sid)

    def test_device_status_heartbeat_exchange(self):
        """Verifies /api/v1/device/status exchanges telemetry and updates heartbeat."""
        payload = {
            "device_id": self.device_id,
            "state": "IDLE_READY",
            "battery_pct": 95,
            "is_online": True,
            "last_command_id": 0
        }
        resp = self.client.post("/api/v1/device/status",
                                data=json.dumps(payload),
                                headers=self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data["status"], "online")
        self.assertIn("server_time", data)
        self.assertIn("emergency_stop_active", data)

    def test_device_movement_command_endpoint(self):
        """Verifies /api/v1/device/command validates commands and advances sequence."""
        now_ms = int(time.time() * 1000)
        cmd_payload = {
            "command_id": 1,
            "intent": "FORWARD",
            "speed": 180,
            "duration_ms": 600,
            "timestamp_ms": now_ms,
            "ttl_ms": 1000
        }
        # 1. Valid command accepted
        resp1 = self.client.post("/api/v1/device/command",
                                 data=json.dumps(cmd_payload),
                                 headers=self.auth_headers)
        self.assertEqual(resp1.status_code, 200)
        data1 = json.loads(resp1.data)
        self.assertEqual(data1["status"], "accepted")
        self.assertEqual(data1["command"]["command_id"], 1)

        # 2. Replay of same sequence ID rejected
        resp_replay = self.client.post("/api/v1/device/command",
                                       data=json.dumps(cmd_payload),
                                       headers=self.auth_headers)
        self.assertEqual(resp_replay.status_code, 400)
        data_replay = json.loads(resp_replay.data)
        self.assertIn("Replay rejected", data_replay["reason"])

    def test_device_emergency_stop_endpoints(self):
        """Verifies /api/v1/device/emergency_stop engages and resets e-stop."""
        # 1. Engage Emergency Stop
        resp_stop = self.client.post("/api/v1/device/emergency_stop",
                                     headers=self.auth_headers)
        self.assertEqual(resp_stop.status_code, 200)
        self.assertTrue(server_device_state["is_emergency_stop"])

        # 2. Movement command must now be rejected
        now_ms = int(time.time() * 1000)
        cmd_payload = {
            "command_id": 99,
            "intent": "FORWARD",
            "speed": 180,
            "duration_ms": 600,
            "timestamp_ms": now_ms,
            "ttl_ms": 1000
        }
        resp_cmd = self.client.post("/api/v1/device/command",
                                    data=json.dumps(cmd_payload),
                                    headers=self.auth_headers)
        self.assertEqual(resp_cmd.status_code, 400)
        data_cmd = json.loads(resp_cmd.data)
        self.assertIn("Emergency stop", data_cmd["reason"])

        # 3. Clear Emergency Stop
        resp_clear = self.client.post("/api/v1/device/emergency_stop/reset",
                                      headers=self.auth_headers)
        self.assertEqual(resp_clear.status_code, 200)
        self.assertFalse(server_device_state["is_emergency_stop"])

    def test_stop_command_does_not_advance_sequence_id(self):
        """Verifies STOP command does not advance or modify last_sequence_id."""
        now_ms = int(time.time() * 1000)
        # 1. Advance sequence to 5 with FORWARD
        forward_cmd = {
            "command_id": 5,
            "intent": "FORWARD",
            "speed": 150,
            "duration_ms": 500,
            "timestamp_ms": now_ms,
            "ttl_ms": 1000
        }
        res_fwd = self.client.post("/api/v1/device/command",
                                   data=json.dumps(forward_cmd),
                                   headers=self.auth_headers)
        self.assertEqual(res_fwd.status_code, 200)
        self.assertEqual(server_device_state["last_sequence_id"], 5)

        # 2. Send STOP command with command_id 1 (lower than 5)
        stop_cmd = {
            "command_id": 1,
            "intent": "STOP",
            "speed": 0,
            "duration_ms": 50,
            "timestamp_ms": now_ms,
            "ttl_ms": 1000
        }
        res_stop = self.client.post("/api/v1/device/command",
                                    data=json.dumps(stop_cmd),
                                    headers=self.auth_headers)
        self.assertEqual(res_stop.status_code, 200)
        # Sequence watermark must STILL be 5 (not overwritten to 1)
        self.assertEqual(server_device_state["last_sequence_id"], 5)

        # 3. Next FORWARD command with command_id 6 succeeds
        fwd_6 = {
            "command_id": 6,
            "intent": "FORWARD",
            "speed": 150,
            "duration_ms": 500,
            "timestamp_ms": now_ms,
            "ttl_ms": 1000
        }
        res_fwd6 = self.client.post("/api/v1/device/command",
                                    data=json.dumps(fwd_6),
                                    headers=self.auth_headers)
        self.assertEqual(res_fwd6.status_code, 200)
        self.assertEqual(server_device_state["last_sequence_id"], 6)

    def test_emergency_stop_command_sets_flag_and_does_not_advance_sequence_id(self):
        """Verifies EMERGENCY_STOP intent sets is_emergency_stop and leaves sequence unchanged."""
        now_ms = int(time.time() * 1000)
        # 1. Advance sequence to 10
        fwd_cmd = {
            "command_id": 10,
            "intent": "FORWARD",
            "speed": 150,
            "duration_ms": 500,
            "timestamp_ms": now_ms,
            "ttl_ms": 1000
        }
        res_fwd = self.client.post("/api/v1/device/command",
                                   data=json.dumps(fwd_cmd),
                                   headers=self.auth_headers)
        self.assertEqual(res_fwd.status_code, 200)
        self.assertEqual(server_device_state["last_sequence_id"], 10)
        self.assertFalse(server_device_state["is_emergency_stop"])

        # 2. Send EMERGENCY_STOP intent via /api/v1/device/command
        estop_cmd = {
            "command_id": 2,
            "intent": "EMERGENCY_STOP",
            "speed": 0,
            "duration_ms": 50,
            "timestamp_ms": now_ms,
            "ttl_ms": 1000
        }
        res_estop = self.client.post("/api/v1/device/command",
                                     data=json.dumps(estop_cmd),
                                     headers=self.auth_headers)
        self.assertEqual(res_estop.status_code, 200)
        # Must engage e-stop flag and preserve sequence watermark at 10
        self.assertTrue(server_device_state["is_emergency_stop"])
        self.assertEqual(server_device_state["last_sequence_id"], 10)

    def test_concurrent_movement_commands_same_sequence_id_strictly_one_passes(self):
        """Verifies device_command_lock prevents race conditions: only 1 concurrent request passes for a given command_id."""
        now_ms = int(time.time() * 1000)
        target_seq = 25
        cmd = {
            "command_id": target_seq,
            "intent": "FORWARD",
            "speed": 150,
            "duration_ms": 500,
            "timestamp_ms": now_ms,
            "ttl_ms": 2000
        }

        results = []
        def send_request():
            with app.test_client() as client:
                resp = client.post(
                    "/api/v1/device/command",
                    data=json.dumps(cmd),
                    headers=self.auth_headers
                )
                return resp.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(send_request) for _ in range(5)]
            for f in concurrent.futures.as_completed(futures):
                results.append(f.result())

        # Exactly one request must succeed (200 OK), and all other 4 must be rejected (400 Bad Request)
        self.assertEqual(results.count(200), 1)
        self.assertEqual(results.count(400), 4)
        self.assertEqual(server_device_state["last_sequence_id"], target_seq)

    def test_offline_capabilities_disclosure(self):
        """Verifies /api/v1/device/capabilities disclaims that cloud features work offline."""
        resp = self.client.get("/api/v1/device/capabilities")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)

        # Must disclaim cloud features
        disclaimers = " ".join(data["offline_disclaimers"]).lower()
        self.assertIn("not available offline", disclaimers)
        self.assertIn("not function offline", disclaimers)
        self.assertIn("gemini", disclaimers)
        self.assertIn("cloud vision", disclaimers)

if __name__ == "__main__":
    unittest.main()

