# DORURU — Phase 11: Hybrid Vision with Gemini Documentation

## 1. System Architecture Overview
Phase 11 connects DORURU's **Phase 5 OV3660 camera capture flow** on the Seeed Studio XIAO ESP32-S3 Sense to the local backend vision service and **Google Gemini** multimodal orchestration layer.

```
┌─────────────────────────────────────────────────────────────┐
│                 DORURU Robot (XIAO ESP32-S3 Sense)          │
│                                                             │
│  [User Voice / Event] ──► OV3660 Camera Capture (VGA 640x480)│
│                                 │                           │
│                          TFT Status: "Looking..."           │
│                                 │                           │
│                     Authenticated HTTP POST                 │
└─────────────────────────────────┼───────────────────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────┐
│                 Local Backend Server (FastAPI / Flask)      │
│                                                             │
│  1. Authenticate Request (X-Device-Token)                   │
│  2. Validate & Smart-Resize Image (Pillow in-memory)        │
│  3. Ephemeral Buffer (Zero disk writes by default)          │
│  4. Multimodal Request via official google.genai SDK        │
│                                 │                           │
│                    Server-side GEMINI_API_KEY               │
└─────────────────────────────────┼───────────────────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────┐
│                     Google Gemini API                       │
│                                                             │
│  Model: Configured via GEMINI_MODEL (e.g. gemini-2.5-flash) │
│  System Instruction: Concise voice-first answer (1-3 sent.) │
│  Safety: Strict disclaimer of person-following & navigation │
└─────────────────────────────────┼───────────────────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────┐
│                 Spoken / Visual Feedback                    │
│                                                             │
│  Backend returns concise answer to DORURU:                  │
│  - TFT Display updates to "Vision Analyzed"                 │
│  - Response delivered to speech pipeline for TTS output     │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Core Vision Principles & Safety Constraints

1. **Hybrid Execution Policy**:
   - **On-Demand**: Images are captured and analyzed ONLY when explicitly requested by the user (e.g., "DORURU, look at this", "What am I holding?").
   - **Selected Events**: Triggered only for explicitly configured discrete events (e.g., user greeting event).
   - **No Continuous Streaming**: DORURU strictly does not perform continuous video streaming, continuous frame uploads, or background cloud surveillance.
2. **Server-Side API Key Security**:
   - Gemini API keys are loaded strictly from environment variables on the backend server (`.env`).
   - The ESP32 firmware contains zero cloud credentials.
3. **Configurable Model Name (Never Hardcoded)**:
   - The model identifier is dynamically loaded from `GEMINI_MODEL` (e.g., `gemini-2.5-flash`). It is never hardcoded in application logic.
4. **No False Autonomy Claims**:
   - The system instructions explicitly enforce that DORURU does not claim continuous visual navigation, obstacle avoidance, person tracking, or real-time spatial mapping.
5. **Ephemeral Storage Policy**:
   - Captured frames are processed strictly in-memory (`io.BytesIO`) and freed immediately after Gemini inference. No image is retained on disk by default.

---

## 3. Image Validation & Smart Optimization Pipeline

Implemented in [`backend/app/vision/image_processor.py`](../backend/app/vision/image_processor.py):

| Check / Step | Rule / Threshold | Purpose |
|--------------|------------------|---------|
| **Magic Bytes** | JPEG (`0xFFD8`), PNG (`\x89PNG`), WebP (`RIFF...WEBP`) | Rejects non-image and corrupt payloads immediately |
| **Payload Size** | Bounded to $\le$ `MAX_IMAGE_PAYLOAD_BYTES` (2MB) | Prevents memory exhaustion |
| **Dimension Bounds** | Min: $16\times16$ px; Max: $4096\times4096$ px | Filters invalid buffers |
| **Smart Resizing** | Downsamples images $> 1024$ px using Lanczos resampling | Preserves aspect ratio, reduces token costs and inference latency |
| **VGA Pass-Through** | Optimal OV3660 frames ($640\times480$) pass through without re-encoding | Prevents loss of crisp high-frequency detail |

---

## 4. API Endpoints Reference

### 1. `POST /api/v1/vision/upload` (Binary Device Transport)
Authenticated endpoint used directly by the ESP32 firmware:
- **Headers**:
  - `Content-Type: image/jpeg`
  - `X-Device-ID: DORURU-SENSE-01`
  - `X-Device-Token: <local_secret_token>`
  - `X-Trigger-Reason: on_demand`
  - `X-Context-Prompt: <optional_question>`
- **Body**: Raw JPEG bytes.
- **Response**:
  ```json
  {
    "status": "success",
    "device_id": "DORURU-SENSE-01",
    "bytes_received": 35480,
    "trigger_reason": "on_demand",
    "timestamp": 1793348120.5,
    "ephemeral": true,
    "vision_result": {
      "processed": true,
      "summary": "I can see an open laptop on a wooden desk with a development board next to it.",
      "prompt": "What do you see?",
      "latency_ms": 780.2,
      "model_used": "gemini-2.5-flash",
      "image_metadata": {
        "width": 640,
        "height": 480,
        "format": "JPEG",
        "original_bytes": 35480,
        "processed_bytes": 35480,
        "was_resized": false,
        "was_compressed": false
      }
    }
  }
  ```

### 2. `POST /api/v1/vision/analyze` (JSON / Base64 Inquiries)
Convenience endpoint for companion apps, laptop development, and diagnostics:
- **Body**:
  ```json
  {
    "image_base64": "<base64_encoded_image>",
    "prompt": "What color is the cup in front of me?",
    "trigger_type": "on_demand"
  }
  ```

---

## 5. Manual Testing Procedure

### Step 1: Configure Environment
Export required variables in your shell so `os.getenv()` reads them upon process startup:

**PowerShell (Windows):**
```powershell
$env:DORURU_DEVICE_TOKEN = "your_local_device_secret_token"
$env:GEMINI_API_KEY = "your_actual_gemini_api_key_here"
$env:GEMINI_MODEL = "gemini-2.5-flash"
```

**Bash / POSIX (Linux/macOS):**
```bash
export DORURU_DEVICE_TOKEN="your_local_device_secret_token"
export GEMINI_API_KEY="your_actual_gemini_api_key_here"
export GEMINI_MODEL="gemini-2.5-flash"
```

*(Optional) Loading from `.env` file (copied from `.env.example`):*
- **PowerShell:**
  ```powershell
  Get-Content .env | Where-Object { $_ -match '^[^#=]+=.+' } | ForEach-Object { $var = $_.Split('=', 2); [System.Environment]::SetEnvironmentVariable($var[0].Trim(), $var[1].Trim()) }
  ```
- **Bash:**
  ```bash
  export $(grep -v '^#' .env | xargs)
  ```

### Step 2: Start Backend Server
```powershell
python -m backend.app.main
```

### Step 3: Test with Curl (Local Image)
```powershell
curl -X POST http://localhost:8000/api/v1/vision/upload `
  -H "Content-Type: image/jpeg" `
  -H "X-Device-ID: DORURU-SENSE-01" `
  -H "X-Device-Token: your_local_device_secret_token" `
  -H "X-Context-Prompt: Describe the object in front of the camera" `
  --data-binary "@path_to_test_image.jpg"
```

### Step 4: Test from Physical Robot
1. Flash firmware (`platformio run -t upload`).
2. Open Serial Monitor at 115200 baud.
3. Type `c` to trigger on-demand capture.
4. Observe TFT display transitions:
   - "Looking..." (shutter open)
   - "Sending image..." (HTTP POST)
   - "Vision Analyzed" (response received and passed to speech pipeline)

---

## 6. Automated Test Suite Results

```powershell
python -m unittest discover -s tests -v
```

```
test_gemini_vision_service_api_error_handling ... ok
test_gemini_vision_service_mock_mode ... ok
test_image_dimension_limits ... ok
test_image_validation_unsupported_format ... ok
test_image_validation_valid_jpeg ... ok
test_no_false_autonomy_claims_in_persona ... ok
test_pass_through_optimal_ov3660_frame ... ok
test_smart_resizing_oversized_image ... ok
test_vision_analyze_json_endpoint ... ok
test_vision_upload_authenticated_endpoint ... ok
test_conflicting_documents_handling ... ok
test_dynamic_reindexing_without_code_changes ... ok
test_markdown_ingestion_and_chunking ... ok
test_missing_evidence_protocol ... ok
test_pdf_ingestion_with_page_attribution ... ok
test_plain_text_ingestion ... ok
test_query_classification ... ok
test_rag_api_endpoints ... ok
test_relevant_retrieval ... ok
test_source_attribution_metadata ... ok
test_e2e_camera_flow_and_display_states ... ok
test_e2e_network_loss_graceful_recovery ... ok
test_authenticated_upload_success ... ok
test_bounded_burst_control ... ok
test_corrupt_non_jpeg_payload_rejected ... ok
test_ephemeral_storage_policy ... ok
test_framebuffer_lifecycle_simulation ... ok
test_health_endpoint ... ok
test_invalid_auth_token_rejected ... ok
test_missing_auth_token_rejected ... ok
test_network_loss_graceful_handling ... ok
test_oversized_payload_rejected ... ok

----------------------------------------------------------------------
Ran 32 tests in 0.733s

OK (100% Pass)
```

