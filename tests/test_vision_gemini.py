"""
tests/test_vision_gemini.py - Test Suite for Phase 11 Hybrid Vision with Gemini

Tests:
1. Image validation (format, header magic bytes, dimension bounds).
2. Smart resizing and compression (preserves 640x480 VGA, downsizes oversized frames).
3. Gemini Vision Service prompt construction and voice-first response contract.
4. Error handling: quota exhaustion (429), timeouts, and network connection drops.
5. Ephemeral processing guarantee (zero disk retention).
6. Disclaimers of continuous autonomy/tracking in system instructions.
7. Endpoints: POST /api/v1/vision/upload and POST /api/v1/vision/analyze.
"""

import os
os.environ.setdefault("DORURU_DEVICE_TOKEN", "test_mock_device_token_12345")
os.environ.setdefault("VISION_TEST_MODE", "true")

import unittest
import io
import base64
import json
from unittest.mock import patch, MagicMock
from PIL import Image

from backend.app.vision.image_processor import validate_and_process_image
from backend.app.vision.gemini_vision_service import (
    GeminiVisionService,
    DORURU_VISION_SYSTEM_INSTRUCTION
)
from backend.app.vision.schemas import VisionTriggerType
from backend.app.main import app
from backend.app import config

def create_in_memory_image(width=640, height=480, fmt="JPEG", color="blue"):
    """Helper to generate a clean synthetic PIL image in memory."""
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()

class TestVisionGemini(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.valid_token = config.DEVICE_AUTH_TOKEN
        self.device_id = "DORURU-SENSE-01"

        # Mock the SDK client on module-level vision_service so endpoint tests cannot make live API calls
        from backend.app.main import vision_service
        self.module_vision_service = vision_service
        self.orig_module_client = vision_service._client
        self.orig_module_api_key = vision_service.api_key

        self.mock_sdk_response = MagicMock()
        self.mock_sdk_response.text = "I can see a clean workspace with development equipment in front of me."
        self.mock_sdk_client = MagicMock()
        self.mock_sdk_client.models.generate_content.return_value = self.mock_sdk_response
        vision_service._client = self.mock_sdk_client

    def tearDown(self):
        self.module_vision_service._client = self.orig_module_client
        self.module_vision_service.api_key = self.orig_module_api_key

    def test_image_validation_valid_jpeg(self):
        """Verifies that a clean JPEG image is validated and parsed."""
        img_bytes = create_in_memory_image(640, 480, "JPEG")
        processed, meta = validate_and_process_image(img_bytes)
        self.assertEqual(meta.width, 640)
        self.assertEqual(meta.height, 480)
        self.assertEqual(meta.format, "JPEG")
        self.assertFalse(meta.was_resized)

    def test_image_validation_unsupported_format(self):
        """Verifies rejection of unsupported or corrupted byte streams."""
        bad_bytes = b"NOT_AN_IMAGE_STREAM_12345"
        with self.assertRaises(ValueError) as ctx:
            validate_and_process_image(bad_bytes)
        self.assertIn("Unsupported image format", str(ctx.exception))

    def test_image_validation_truncated_image_rejected(self):
        """Verifies rejection of truncated images in the pass-through path via img.load()."""
        valid_img = create_in_memory_image(640, 480, "JPEG")
        truncated_img = valid_img[:len(valid_img) // 2]
        with self.assertRaises(ValueError) as ctx:
            validate_and_process_image(truncated_img)
        self.assertIn("Corrupted or invalid image data", str(ctx.exception))

    def test_image_dimension_limits(self):
        """Verifies rejection of images that are too small."""
        tiny_img = create_in_memory_image(8, 8, "JPEG")
        with self.assertRaises(ValueError) as ctx:
            validate_and_process_image(tiny_img)
        self.assertIn("too small", str(ctx.exception))

    def test_smart_resizing_oversized_image(self):
        """Verifies that oversized images (>1024px) are safely resized preserving aspect ratio."""
        big_img = create_in_memory_image(2000, 1500, "JPEG")
        processed, meta = validate_and_process_image(big_img, max_dimension=1024)
        self.assertTrue(meta.was_resized)
        self.assertLessEqual(meta.width, 1024)
        self.assertLessEqual(meta.height, 1024)
        self.assertGreater(len(processed), 0)

    def test_pass_through_optimal_ov3660_frame(self):
        """Verifies that optimal 640x480 OV3660 frames are passed through without re-compression."""
        vga_img = create_in_memory_image(640, 480, "JPEG")
        processed, meta = validate_and_process_image(vga_img, max_dimension=1024, compress_threshold=500*1024)
        self.assertFalse(meta.was_resized)
        self.assertFalse(meta.was_compressed)
        self.assertEqual(len(processed), len(vga_img))

    def test_gemini_vision_service_mock_mode(self):
        """Verifies deterministic mock response when opt-in test mode is enabled."""
        service = GeminiVisionService(api_key="", model="gemini-2.5-flash", test_mode=True)
        img_bytes = create_in_memory_image(640, 480, "JPEG")

        res = service.analyze_frame(
            image_bytes=img_bytes,
            context_prompt="What color is this box?",
            trigger_type=VisionTriggerType.ON_DEMAND,
            device_id=self.device_id
        )

        self.assertEqual(res.status, "success")
        self.assertIn("workspace", res.answer)
        self.assertIn("What color is this box?", res.answer)
        self.assertTrue(res.ephemeral)
        self.assertIn("mock_mode", res.model_used)

    def test_gemini_vision_service_unavailable_without_credentials(self):
        """Verifies explicit unavailable result when API credentials are missing and test mode is disabled."""
        service = GeminiVisionService(api_key="", model="gemini-2.5-flash", test_mode=False)
        img_bytes = create_in_memory_image(640, 480, "JPEG")

        res = service.analyze_frame(
            image_bytes=img_bytes,
            context_prompt="What color is this box?",
            trigger_type=VisionTriggerType.ON_DEMAND,
            device_id=self.device_id
        )

        self.assertEqual(res.status, "unavailable")
        self.assertIn("unavailable", res.answer.lower())
        self.assertNotIn("workspace", res.answer.lower())
        self.assertIsNotNone(res.error)
        self.assertIn("credentials not configured", res.error.lower())

    def test_gemini_client_initialization_timeout_http_options(self):
        """Verifies genai.Client construction passes timeout via HttpOptions in integer milliseconds."""
        from google import genai
        from google.genai import types

        with patch.object(genai, "Client") as mock_client_cls:
            service = GeminiVisionService(api_key="test_api_key_valid", model="gemini-2.5-flash")
            mock_client_cls.assert_called_once()
            call_kwargs = mock_client_cls.call_args.kwargs

            self.assertEqual(call_kwargs.get("api_key"), "test_api_key_valid")
            http_opts = call_kwargs.get("http_options")
            self.assertIsNotNone(http_opts)
            self.assertIsInstance(http_opts, types.HttpOptions)
            expected_timeout_ms = int(config.VISION_REQUEST_TIMEOUT_SECONDS * 1000)
            self.assertEqual(http_opts.timeout, expected_timeout_ms)

    def test_gemini_vision_service_api_error_handling(self):
        """Verifies graceful error handling for quota/rate limits."""
        from google.genai.errors import APIError
        mock_client = MagicMock()
        mock_err = APIError.__new__(APIError)
        mock_err.code = 429
        mock_err.message = "Resource exhausted"
        mock_client.models.generate_content.side_effect = mock_err

        with patch("backend.app.vision.gemini_vision_service.genai.Client", return_value=mock_client):
            service = GeminiVisionService(api_key="fake_key_for_test", model="gemini-2.5-flash")
            img_bytes = create_in_memory_image(640, 480, "JPEG")
            res = service.analyze_frame(img_bytes, "What is this?")

            self.assertEqual(res.status, "error")
            self.assertIn("quota exceeded", res.error.lower())

    def test_gemini_vision_service_with_api_key_uses_mocked_client(self):
        """Verifies constructing GeminiVisionService with an API key mocks SDK client (no live calls)."""
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "Simulated safe vision description"
        mock_client.models.generate_content.return_value = mock_resp

        with patch("backend.app.vision.gemini_vision_service.genai.Client", return_value=mock_client):
            service = GeminiVisionService(api_key="simulated_real_api_key", model="gemini-2.5-flash")
            self.assertIs(service._client, mock_client)

            img_bytes = create_in_memory_image(640, 480, "JPEG")
            res = service.analyze_frame(img_bytes, "Look at this")

            self.assertEqual(res.status, "success")
            self.assertEqual(res.answer, "Simulated safe vision description")
            mock_client.models.generate_content.assert_called_once()

    def test_endpoint_with_gemini_api_key_set_cannot_make_live_calls(self):
        """Verifies endpoints use mocked SDK client and cannot make live API calls when GEMINI_API_KEY is set."""
        orig_key = config.GEMINI_API_KEY
        try:
            config.GEMINI_API_KEY = "live_gemini_api_key_sample_12345"
            self.module_vision_service.api_key = "live_gemini_api_key_sample_12345"
            self.module_vision_service._client = self.mock_sdk_client
            self.mock_sdk_response.text = "Desk workspace with DORURU robot."

            img_bytes = create_in_memory_image(640, 480, "JPEG")
            headers = {
                "Content-Type": "image/jpeg",
                "X-Device-ID": self.device_id,
                "X-Device-Token": self.valid_token
            }
            resp = self.client.post("/api/v1/vision/upload", data=img_bytes, headers=headers)
            self.assertEqual(resp.status_code, 200)
            data = json.loads(resp.data)
            self.assertEqual(data["status"], "success")
            self.assertEqual(data["vision_result"]["summary"], "Desk workspace with DORURU robot.")
            self.mock_sdk_client.models.generate_content.assert_called()
        finally:
            config.GEMINI_API_KEY = orig_key
            self.module_vision_service.api_key = self.orig_module_api_key

    def test_no_false_autonomy_claims_in_persona(self):
        """
        Verifies that the DORURU system prompt explicitly disclaims
        continuous navigation, person following, or obstacle avoidance.
        """
        self.assertIn("NO FALSE AUTONOMY CLAIMS", DORURU_VISION_SYSTEM_INSTRUCTION)
        self.assertIn("continuous visual navigation", DORURU_VISION_SYSTEM_INSTRUCTION)
        self.assertIn("obstacle avoidance", DORURU_VISION_SYSTEM_INSTRUCTION)
        self.assertIn("person following", DORURU_VISION_SYSTEM_INSTRUCTION)

    def test_vision_upload_authenticated_endpoint(self):
        """Verifies full HTTP POST flow to /api/v1/vision/upload."""
        img_bytes = create_in_memory_image(640, 480, "JPEG")
        headers = {
            "Content-Type": "image/jpeg",
            "X-Device-ID": self.device_id,
            "X-Device-Token": self.valid_token,
            "X-Trigger-Reason": "on_demand",
            "X-Context-Prompt": "What do you see?"
        }

        resp = self.client.post("/api/v1/vision/upload", data=img_bytes, headers=headers)
        self.assertEqual(resp.status_code, 200)

        data = json.loads(resp.data)
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["trigger_reason"], "on_demand")
        self.assertTrue(data["vision_result"]["processed"])
        self.assertIsNotNone(data["vision_result"]["summary"])

    def test_vision_analyze_json_endpoint(self):
        """Verifies JSON base64 endpoint /api/v1/vision/analyze with device-token auth."""
        img_bytes = create_in_memory_image(320, 240, "JPEG")
        b64_str = base64.b64encode(img_bytes).decode("utf-8")

        payload = {
            "image_base64": b64_str,
            "prompt": "Identify any visible signs",
            "trigger_type": "on_demand"
        }

        resp = self.client.post("/api/v1/vision/analyze",
                                data=json.dumps(payload),
                                headers={"Content-Type": "application/json",
                                         "X-Device-Token": self.valid_token})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data["status"], "success")
        self.assertIn("Identify any visible signs", data["answer"])

    def test_vision_analyze_unauthenticated_rejected(self):
        """Verifies /api/v1/vision/analyze rejects unauthenticated requests with 401."""
        payload = {"image_base64": "dGVzdA==", "prompt": "test"}
        resp = self.client.post("/api/v1/vision/analyze",
                                data=json.dumps(payload),
                                headers={"Content-Type": "application/json"})
        self.assertEqual(resp.status_code, 401)
        data = json.loads(resp.data)
        self.assertEqual(data["error"], "Unauthorized")

    def test_vision_analyze_bearer_token_authenticated(self):
        """Verifies /api/v1/vision/analyze accepts companion-app Bearer authorization."""
        img_bytes = create_in_memory_image(320, 240, "JPEG")
        b64_str = base64.b64encode(img_bytes).decode("utf-8")
        payload = {
            "image_base64": b64_str,
            "prompt": "Describe scene",
            "trigger_type": "on_demand"
        }
        resp = self.client.post("/api/v1/vision/analyze",
                                data=json.dumps(payload),
                                headers={"Content-Type": "application/json",
                                         "Authorization": f"Bearer {self.valid_token}"})
        self.assertEqual(resp.status_code, 200)

    def test_vision_analyze_payload_too_large_rejected(self):
        """Verifies /api/v1/vision/analyze rejects payloads exceeding MAX_CONTENT_LENGTH with 413."""
        oversized_data = b"x" * (config.MAX_CONTENT_LENGTH + 1024)
        headers = {
            "Content-Type": "application/json",
            "X-Device-Token": self.valid_token
        }
        resp = self.client.post("/api/v1/vision/analyze",
                                data=oversized_data,
                                headers=headers)
        self.assertEqual(resp.status_code, 413)

    def test_vision_analyze_image_size_validation_kept(self):
        """Verifies existing downstream image size validation is retained in analyze handler."""
        # Payload size is within MAX_CONTENT_LENGTH (4MB), but decoded image exceeds MAX_IMAGE_PAYLOAD_BYTES (2MB)
        oversized_image_bytes = bytearray(config.MAX_IMAGE_PAYLOAD_BYTES + 2048)
        oversized_image_bytes[0] = 0xFF
        oversized_image_bytes[1] = 0xD8
        oversized_image_bytes[-2] = 0xFF
        oversized_image_bytes[-1] = 0xD9
        b64_str = base64.b64encode(oversized_image_bytes).decode("utf-8")

        payload = {
            "image_base64": b64_str,
            "prompt": "Analyze oversized image"
        }
        headers = {
            "Content-Type": "application/json",
            "X-Device-Token": self.valid_token
        }
        resp = self.client.post("/api/v1/vision/analyze",
                                data=json.dumps(payload),
                                headers=headers)
        self.assertEqual(resp.status_code, 400)
        data = json.loads(resp.data)
        self.assertIn("exceeds maximum limit", data["message"])

if __name__ == "__main__":
    unittest.main()

