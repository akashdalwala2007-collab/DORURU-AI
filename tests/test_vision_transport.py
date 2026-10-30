"""
tests/test_vision_transport.py - Mock Test Suite for Phase 5 Camera & Vision Transport

Validates:
- Authenticated local API transport
- JPEG SOI/EOI payload verification
- Rejection of unauthenticated requests (401)
- Rejection of corrupt image payloads (400)
- Rejection of oversized payloads (413)
- Ephemeral image handling (no permanent file storage)
- Wi-Fi loss and network failure resilience
- Bounded burst capture limit (<= 3 frames)
- Framebuffer memory lifecycle and buffer release
"""

import os
os.environ.setdefault("DORURU_DEVICE_TOKEN", "test_mock_device_token_12345")
os.environ.setdefault("VISION_TEST_MODE", "true")

import unittest
import importlib
import json
import time
import io
import subprocess
from pathlib import Path
from PIL import Image
from backend.app.main import app
from backend.app import config
from tests.host_test_helper import ensure_compiled_host_firmware_test


def create_valid_mock_jpeg(width=640, height=480, size=None):
    """Generates a valid, decodable JPEG image."""
    img = Image.new("RGB", (width, height), color=(30, 144, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def create_corrupt_payload(size=1024):
    """Generates a non-JPEG byte buffer."""
    return bytes([0x00] * size)

class TestVisionTransport(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.valid_token = config.DEVICE_AUTH_TOKEN
        self.device_id = "DORURU-SENSE-01"

    def test_health_endpoint(self):
        """Verify local backend health check."""
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["status"], "online")
        self.assertTrue("telemetry" in data)

    def test_authenticated_upload_success(self):
        """Verify successful image transport with valid token and JPEG payload."""
        jpeg_data = create_valid_mock_jpeg(640, 480, 4096)
        headers = {
            "Content-Type": "image/jpeg",
            "X-Device-ID": self.device_id,
            "X-Device-Token": self.valid_token,
            "X-Trigger-Reason": "0", # On-demand
            "X-Context-Prompt": "What is in front of the robot?"
        }

        response = self.client.post("/api/v1/vision/upload", data=jpeg_data, headers=headers)
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.data)
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["device_id"], self.device_id)
        self.assertEqual(data["bytes_received"], len(jpeg_data))
        self.assertEqual(data["trigger_reason"], "on_demand")
        self.assertTrue(data["ephemeral"])
        self.assertTrue(data["vision_result"]["processed"])

    def test_missing_auth_token_rejected(self):
        """Verify rejection when X-Device-Token is missing."""
        jpeg_data = create_valid_mock_jpeg()
        headers = {
            "Content-Type": "image/jpeg",
            "X-Device-ID": self.device_id
            # Missing X-Device-Token
        }

        response = self.client.post("/api/v1/vision/upload", data=jpeg_data, headers=headers)
        self.assertEqual(response.status_code, 401)
        data = json.loads(response.data)
        self.assertEqual(data["error"], "Unauthorized")

    def test_invalid_auth_token_rejected(self):
        """Verify rejection when an invalid token is provided."""
        jpeg_data = create_valid_mock_jpeg()
        headers = {
            "Content-Type": "image/jpeg",
            "X-Device-ID": self.device_id,
            "X-Device-Token": "wrong_fake_token_12345"
        }

        response = self.client.post("/api/v1/vision/upload", data=jpeg_data, headers=headers)
        self.assertEqual(response.status_code, 401)

    def test_device_auth_token_required_in_config(self):
        """Verify DEVICE_AUTH_TOKEN requires DORURU_DEVICE_TOKEN and fails startup if unset or empty."""
        original_token = os.environ.get("DORURU_DEVICE_TOKEN")
        try:
            # 1. Test unset fails startup with ValueError
            if "DORURU_DEVICE_TOKEN" in os.environ:
                del os.environ["DORURU_DEVICE_TOKEN"]
            with self.assertRaises(ValueError) as ctx_unset:
                importlib.reload(config)
            self.assertIn("DORURU_DEVICE_TOKEN", str(ctx_unset.exception))

            # 2. Test empty string fails startup with ValueError
            os.environ["DORURU_DEVICE_TOKEN"] = ""
            with self.assertRaises(ValueError) as ctx_empty:
                importlib.reload(config)
            self.assertIn("DORURU_DEVICE_TOKEN", str(ctx_empty.exception))

            # 3. Test whitespace-only string fails startup with ValueError
            os.environ["DORURU_DEVICE_TOKEN"] = "   "
            with self.assertRaises(ValueError) as ctx_ws:
                importlib.reload(config)
            self.assertIn("DORURU_DEVICE_TOKEN", str(ctx_ws.exception))

            # 4. Test valid non-empty token succeeds
            os.environ["DORURU_DEVICE_TOKEN"] = "verified_test_token_ok"
            importlib.reload(config)
            self.assertEqual(config.DEVICE_AUTH_TOKEN, "verified_test_token_ok")
        finally:
            # Restore environment and config state
            if original_token is not None:
                os.environ["DORURU_DEVICE_TOKEN"] = original_token
            else:
                os.environ["DORURU_DEVICE_TOKEN"] = "test_mock_device_token_12345"
            importlib.reload(config)

    def test_corrupt_non_jpeg_payload_rejected(self):
        """Verify rejection of non-JPEG or corrupted buffer."""
        bad_data = create_corrupt_payload()
        headers = {
            "Content-Type": "image/jpeg",
            "X-Device-ID": self.device_id,
            "X-Device-Token": self.valid_token
        }

        response = self.client.post("/api/v1/vision/upload", data=bad_data, headers=headers)
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertTrue("Missing SOI marker" in data["message"] or
                        "Unsupported image format" in data["message"] or
                        "invalid" in data["message"].lower())


    def test_oversized_payload_rejected(self):
        """Verify rejection when payload exceeds MAX_IMAGE_PAYLOAD_BYTES."""
        oversized_len = config.MAX_IMAGE_PAYLOAD_BYTES + 1024
        oversized_data = bytearray(oversized_len)
        oversized_data[0] = 0xFF
        oversized_data[1] = 0xD8
        headers = {
            "Content-Type": "image/jpeg",
            "X-Device-ID": self.device_id,
            "X-Device-Token": self.valid_token,
            "Content-Length": str(oversized_len)
        }

        response = self.client.post("/api/v1/vision/upload", data=bytes(oversized_data), headers=headers)
        self.assertEqual(response.status_code, 413)

    def test_ephemeral_storage_policy(self):
        """Verify that uploaded images are NOT written to disk permanently by default."""
        import os
        debug_dir = "debug_captures"
        if os.path.exists(debug_dir):
            initial_files = set(os.listdir(debug_dir))
        else:
            initial_files = set()

        jpeg_data = create_valid_mock_jpeg(size=1024)
        headers = {
            "Content-Type": "image/jpeg",
            "X-Device-ID": self.device_id,
            "X-Device-Token": self.valid_token
        }

        response = self.client.post("/api/v1/vision/upload", data=jpeg_data, headers=headers)
        self.assertEqual(response.status_code, 200)

        # Check that no new files were created
        if os.path.exists(debug_dir):
            current_files = set(os.listdir(debug_dir))
            self.assertEqual(current_files, initial_files)

    def test_bounded_burst_control(self):
        """
        Executes host firmware tests exercising camera_manager_capture_burst in camera_manager.cpp,
        verifying that bursts are strictly clamped to MAX_BURST_FRAMES_LIMIT (3).
        """
        exe_path = ensure_compiled_host_firmware_test()
        proc = subprocess.run([str(exe_path)], capture_output=True, text=True, check=True)
        self.assertIn("[PASS] camera_manager_capture_burst (clamped to max 3 frames)", proc.stdout)

    def test_framebuffer_lifecycle_simulation(self):
        """
        Executes host firmware tests exercising camera_manager_capture_single,
        camera_manager_release_frame, and slot recovery in camera_manager.cpp.
        """
        exe_path = ensure_compiled_host_firmware_test()
        proc = subprocess.run([str(exe_path)], capture_output=True, text=True, check=True)
        self.assertIn("[PASS] camera_manager_capture_single & camera_manager_release_frame", proc.stdout)
        self.assertIn("[PASS] Framebuffer slot exhaustion and recovery", proc.stdout)

    def test_network_loss_graceful_handling(self):
        """
        Executes host firmware tests exercising vision_transport_capture_and_send in
        vision_transport.cpp under offline conditions, verifying fail-fast and zero leaks.
        """
        exe_path = ensure_compiled_host_firmware_test()
        proc = subprocess.run([str(exe_path)], capture_output=True, text=True, check=True)
        self.assertIn("[PASS] vision_transport_capture_and_send (network loss graceful recovery)", proc.stdout)


if __name__ == "__main__":
    unittest.main()

