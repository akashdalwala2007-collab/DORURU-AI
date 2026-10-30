---
phase: 11
plan: 1
wave: 1
gap_closure: false
---

# Plan 11.1: Hybrid Vision with Gemini

## Objective
Connect the Phase 5 OV3660 camera capture flow to the local backend vision service and Google Gemini orchestration using the current official Google GenAI SDK (`google.genai`). Keep Gemini API keys server-side only, load the model identifier strictly from environment variables without hardcoding, validate and smartly resize image inputs, enforce ephemeral storage, and disclaim continuous tracking/navigation capabilities.

## Context
- `doruru_phase.txt` (Phase 11 Master Prompt)
- `backend/app/config.py` (Vision and Gemini configuration)
- `firmware/src/transport/vision_transport.cpp` (Phase 5 HTTP capture transport)

## Tasks

<task type="auto" effort="high">
  <name>Build Image Processing and Optimization Pipeline</name>
  <files>backend/app/vision/image_processor.py, backend/app/vision/schemas.py</files>
  <action>
    Validate image format (JPEG, PNG, WebP) and magic byte signatures.
    Check dimensions and payload bounds.
    Smartly downsample oversized images while passing through optimal 640x480 OV3660 frames without quality loss.
    Enforce ephemeral in-memory processing.
  </action>
  <verify>python -m unittest tests/test_vision_gemini.py -k image_validation</verify>
  <done>Clean validation and smart resizing preserving aspect ratio and fine detail</done>
</task>

<task type="auto" effort="high">
  <name>Implement Gemini Vision Service with Official SDK</name>
  <files>backend/app/vision/gemini_vision_service.py</files>
  <action>
    Integrate google.genai Client with types.Part.from_bytes.
    Load model from config.GEMINI_MODEL without hardcoding.
    Enforce voice-first persona: 1-3 sentences max.
    Explicitly prohibit person tracking, object following, continuous navigation, and obstacle avoidance claims.
    Handle APIError, 429 quota exhaustion, timeouts, and provide mock fallback.
  </action>
  <verify>python -m unittest tests/test_vision_gemini.py -k gemini_vision_service</verify>
  <done>Zero cloud secrets on device, robust error handling, voice-first response</done>
</task>

<task type="auto" effort="medium">
  <name>Integrate Endpoints into Backend</name>
  <files>backend/app/main.py</files>
  <action>
    Route POST /api/v1/vision/upload to Gemini vision pipeline.
    Add POST /api/v1/vision/analyze for JSON / base64 image inquiries.
    Deliver structured response with latency, model info, and summary.
  </action>
  <verify>python -m unittest tests/test_vision_gemini.py -k endpoint</verify>
  <done>Endpoints deliver validated responses to robot and client</done>
</task>

<task type="auto" effort="medium">
  <name>Create Automated Mock Tests & Documentation</name>
  <files>tests/test_vision_gemini.py, docs/PHASE_11_HYBRID_VISION_GEMINI.md</files>
  <action>
    Build unit tests covering format validation, resizing, persona disclaimers, quota errors, and endpoints.
    Document manual hardware testing procedure with real camera triggers.
  </action>
  <verify>python -m unittest discover -s tests -v</verify>
  <done>100% test pass rate across all project tests</done>
</task>

