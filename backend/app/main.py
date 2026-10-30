"""
backend/app/main.py - DORURU Unified Robot Backend API & Vision Transport Server

Combines:
1. FastAPI Application: Autonomy Level 1 Movement Intent Router, Device Clock Synchronization,
   and System Autonomy Health endpoints.
2. Flask Application: Ephemeral Vision Transport, College RAG Ingestion & Querying,
   Device Telemetry, and Session Recovery Endpoints.
3. Unified ASGI Mounting: Mounts Flask via WSGIMiddleware onto FastAPI for production ASGI serving,
   while providing seamless compatibility for both Flask test_client and FastAPI TestClient.
"""

import time
import os
import hmac
import threading
from pathlib import Path

# Flask & CORS imports
from flask import Flask, request, jsonify
from flask_cors import CORS

# FastAPI imports
from fastapi import FastAPI
from fastapi.middleware.wsgi import WSGIMiddleware

from . import config
from .rag.service import CollegeRAGService
from .vision.gemini_vision_service import GeminiVisionService
from .vision.schemas import VisionTriggerType
from .session.session_manager import SessionManager
from .session.command_safety import validate_movement_command, MovementCommand, MovementIntent

# Remote Teammate Movement Intent Router & Schemas
from backend.app.routers.movement import router as movement_router
from backend.app.schemas.movement import AutonomyCapabilities

# ==============================================================================
# FLASK APPLICATION SETUP (Vision, RAG, Session, Device Safety)
# ==============================================================================
flask_app = Flask(__name__)
flask_app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH
CORS(flask_app)

# In-memory telemetry
telemetry = {
    "total_uploads": 0,
    "auth_failures": 0,
    "validation_failures": 0,
    "last_upload_timestamp": None,
    "last_device_id": None
}

@flask_app.errorhandler(413)
def request_entity_too_large(error):
    telemetry["validation_failures"] += 1
    max_len = flask_app.config.get("MAX_CONTENT_LENGTH", config.MAX_CONTENT_LENGTH)
    return jsonify({
        "error": "Payload Too Large",
        "message": f"Payload exceeds maximum allowed limit of {max_len} bytes"
    }), 413


# Initialize Services
rag_service = CollegeRAGService()
vision_service = GeminiVisionService()
session_manager = SessionManager(default_ttl_seconds=config.SESSION_EXPIRY_SECONDS)

# Server-side device state & safety tracking
server_device_state = {
    "is_emergency_stop": False,
    "last_sequence_id": 0,
    "last_heartbeat_time": 0.0,
    "allow_offline_movement": config.ALLOW_OFFLINE_MOVEMENT
}
device_command_lock = threading.Lock()


def _authenticate_request():
    """
    Validates device-token authentication (X-Device-Token) or companion-app
    authorization check (Authorization: Bearer <token>) against config.DEVICE_AUTH_TOKEN.
    Returns (True, None) if authorized, or (False, response_tuple) if unauthorized.
    """
    device_token = request.headers.get("X-Device-Token")
    if not device_token:
        # Check Authorization: Bearer <token>
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            device_token = auth_header.split(" ", 1)[1]

    if not device_token or not hmac.compare_digest(device_token, config.DEVICE_AUTH_TOKEN):
        telemetry["auth_failures"] += 1
        return False, (jsonify({
            "error": "Unauthorized",
            "message": "Missing or invalid local device token"
        }), 401)

    return True, None


@flask_app.route("/api/v1/health", methods=["GET"])
def flask_health_check():
    """Health status endpoint."""
    return jsonify({
        "status": "online",
        "service": "DORURU Local Backend",
        "gemini_model_configured": bool(config.GEMINI_MODEL),
        "telemetry": telemetry
    }), 200


@flask_app.route("/api/v1/vision/upload", methods=["POST"])
def upload_vision_frame():
    """
    Authenticated image transport endpoint for DORURU camera frames.
    
    Security & Privacy:
    - Rejects unauthenticated requests with 401.
    - Strictly ephemeral: image bytes are kept in memory only during processing,
      never persisted to disk by default.
    - Does NOT implement person tracking or autonomous visual navigation.
    """
    # 1. Authenticate Request
    is_authenticated, auth_error = _authenticate_request()
    if not is_authenticated:
        return auth_error

    device_id = request.headers.get("X-Device-ID", "UNKNOWN")
    trigger_reason = request.headers.get("X-Trigger-Reason", "0") # 0=on_demand, 2=event
    context_prompt = request.headers.get("X-Context-Prompt", "Analyze this image")

    # 2. Check Payload Size
    content_length = request.content_length or len(request.data)
    if content_length > config.MAX_IMAGE_PAYLOAD_BYTES:
        telemetry["validation_failures"] += 1
        return jsonify({
            "error": "Payload Too Large",
            "message": f"Image exceeds maximum limit of {config.MAX_IMAGE_PAYLOAD_BYTES} bytes"
        }), 413

    # 3. Read Frame Bytes
    image_bytes = request.data
    if not image_bytes:
        telemetry["validation_failures"] += 1
        return jsonify({
            "error": "Bad Request",
            "message": "Empty image payload"
        }), 400

    # 4. Validate and Process Image via Vision Pipeline
    try:
        trigger_enum = VisionTriggerType.ON_DEMAND if trigger_reason in ("0", "on_demand") else VisionTriggerType.SELECTED_EVENT
        vision_res = vision_service.analyze_frame(
            image_bytes=image_bytes,
            context_prompt=context_prompt,
            trigger_type=trigger_enum,
            device_id=device_id
        )
    except ValueError as ve:
        telemetry["validation_failures"] += 1
        return jsonify({
            "error": "Bad Request",
            "message": str(ve)
        }), 400
    except Exception as e:
        return jsonify({
            "error": "Internal Server Error",
            "message": f"Vision processing error: {str(e)}"
        }), 500

    # 5. Verify Ephemeral Policy
    if config.PERSIST_IMAGES:
        # Only if explicitly configured for offline debugging
        debug_dir = Path("debug_captures")
        debug_dir.mkdir(exist_ok=True)
        filename = debug_dir / f"frame_{int(time.time()*1000)}.jpg"
        with open(filename, "wb") as f:
            f.write(image_bytes)

    # 6. Update Telemetry
    telemetry["total_uploads"] += 1
    telemetry["last_upload_timestamp"] = time.time()
    telemetry["last_device_id"] = device_id

    # 7. Return Structured Response to Device Pipeline
    response_payload = {
        "status": vision_res.status,
        "device_id": device_id,
        "bytes_received": len(image_bytes),
        "trigger_reason": vision_res.trigger_type.value,
        "timestamp": time.time(),
        "ephemeral": not config.PERSIST_IMAGES,
        "vision_result": {
            "processed": (vision_res.status == "success"),
            "summary": vision_res.answer,
            "prompt": context_prompt,
            "latency_ms": vision_res.latency_ms,
            "model_used": vision_res.model_used,
            "image_metadata": vision_res.image_metadata.model_dump()
        }
    }
    if vision_res.error:
        response_payload["error"] = vision_res.error

    return jsonify(response_payload), 200


@flask_app.route("/api/v1/vision/analyze", methods=["POST"])
def analyze_vision_json():
    """
    JSON / Base64 vision inquiry endpoint for manual tests and companion apps.
    Accepts: {"image_base64": "...", "prompt": "...", "trigger_type": "on_demand"}
    """
    import base64

    # 1. Require device-token authentication or companion-app authorization check
    is_authenticated, auth_error = _authenticate_request()
    if not is_authenticated:
        return auth_error

    # 2. Enforce MAX_CONTENT_LENGTH before parsing JSON payload or decoding image
    content_length = request.content_length or (len(request.data) if request.data else 0)
    max_len = flask_app.config.get("MAX_CONTENT_LENGTH", config.MAX_CONTENT_LENGTH)
    if content_length > max_len:
        telemetry["validation_failures"] += 1
        return jsonify({
            "error": "Payload Too Large",
            "message": f"Payload exceeds maximum allowed limit of {max_len} bytes"
        }), 413

    # 3. Parse JSON payload
    payload = request.get_json(silent=True) or {}
    image_b64 = payload.get("image_base64", "")
    prompt = payload.get("prompt", "Describe what is visible in front of the robot")
    trigger_str = payload.get("trigger_type", "on_demand")

    if not image_b64:
        return jsonify({"error": "Bad Request", "message": "Missing 'image_base64' payload"}), 400

    try:
        image_bytes = base64.b64decode(image_b64)
    except Exception as e:
        return jsonify({"error": "Bad Request", "message": f"Invalid base64 encoding: {e}"}), 400

    # 4. Retain existing image-size validation and vision processing
    trigger_enum = VisionTriggerType.ON_DEMAND if trigger_str == "on_demand" else VisionTriggerType.SELECTED_EVENT
    try:
        vision_res = vision_service.analyze_frame(
            image_bytes=image_bytes,
            context_prompt=prompt,
            trigger_type=trigger_enum,
            device_id="API-CLIENT"
        )
        return jsonify({
            "status": vision_res.status,
            "answer": vision_res.answer,
            "latency_ms": vision_res.latency_ms,
            "model_used": vision_res.model_used,
            "image_metadata": vision_res.image_metadata.model_dump(),
            "ephemeral": True,
            "error": vision_res.error
        }), 200
    except ValueError as ve:
        telemetry["validation_failures"] += 1
        return jsonify({"error": "Bad Request", "message": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": "Internal Server Error", "message": str(e)}), 500


# ==============================================================================
# PHASE 9: COLLEGE KNOWLEDGE BASE AND RAG ENDPOINTS
# ==============================================================================

@flask_app.route("/api/v1/rag/query", methods=["POST"])
def rag_query():
    """
    RAG Query Endpoint:
    - Distinguishes college queries from general queries.
    - Retrieves top matching chunks with complete source metadata.
    - Strictly answers from verified context (refusing to hallucinate if missing).
    - Flags conflicting documents when discrepancies exist.
    """
    payload = request.get_json(silent=True) or {}
    query_text = payload.get("query", "").strip()
    top_k = payload.get("top_k", config.RAG_TOP_K)

    if not query_text:
        return jsonify({
            "error": "Bad Request",
            "message": "Missing 'query' parameter"
        }), 400

    result = rag_service.answer_query(query_text, top_k=top_k)
    return jsonify({
        "status": "success",
        "query": query_text,
        "is_college_query": result["is_college_query"],
        "classification_reason": result["classification_reason"],
        "answer": result["answer"],
        "sources": result["sources"],
        "evidence_count": result["evidence_count"],
        "conflict_detected": result["conflict_detected"],
        "conflict_details": result.get("conflict_details")
    }), 200


@flask_app.route("/api/v1/rag/reindex", methods=["POST"])
def rag_reindex():
    """
    Triggers re-indexing of documents in knowledge_base/documents without application restart.
    """
    force = request.args.get("force", "true").lower() in ("true", "1")
    total_chunks = rag_service.reindex(force=force)
    return jsonify({
        "status": "success",
        "message": "Knowledge base re-indexed successfully",
        "total_chunks": total_chunks,
        "files_indexed": list(rag_service.retriever.indexed_files.keys())
    }), 200


@flask_app.route("/api/v1/rag/status", methods=["GET"])
def rag_status():
    """Returns RAG knowledge base statistics and indexed file manifests."""
    retriever = rag_service.retriever
    return jsonify({
        "status": "online",
        "total_chunks": len(retriever.chunks),
        "files_indexed": list(retriever.indexed_files.keys()),
        "vocabulary_size": len(retriever.idf),
        "docs_dir": str(retriever.docs_dir),
        "index_dir": str(retriever.index_dir)
    }), 200


# ==============================================================================
# PHASE 13: SESSION LIFECYCLE, OFFLINE FALLBACK & SAFETY ENDPOINTS
# ==============================================================================

@flask_app.route("/api/v1/session/new", methods=["POST"])
def session_new():
    """Initializes a new ephemeral conversation session."""
    payload = request.get_json(silent=True) or {}
    ttl = payload.get("ttl_seconds")
    try:
        sess = session_manager.create_session(ttl_seconds=ttl)
    except ValueError as ve:
        return jsonify({
            "error": "Bad Request",
            "message": str(ve)
        }), 400
    except RuntimeError as re:
        return jsonify({
            "error": "Capacity Exceeded",
            "message": str(re)
        }), 429

    return jsonify({
        "status": "created",
        "session": sess.to_dict()
    }), 201


@flask_app.route("/api/v1/session/status", methods=["GET"])
def session_status():
    """Retrieves session metadata, checking validity and expiration."""
    session_id = request.args.get("session_id")
    if not session_id:
        return jsonify({"error": "Bad Request", "message": "Missing 'session_id' parameter"}), 400

    sess = session_manager.get_session(session_id)
    if not sess:
        return jsonify({"error": "Not Found", "message": "Session expired or does not exist"}), 404

    return jsonify({
        "status": "active",
        "session": sess.to_dict()
    }), 200


@flask_app.route("/api/v1/session/reset", methods=["POST"])
def session_reset():
    """Strictly wipes temporary session memory and creates a refreshed session."""
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id")
    if not session_id:
        return jsonify({"error": "Bad Request", "message": "Missing 'session_id' parameter"}), 400

    fresh = session_manager.reset_session(session_id)
    return jsonify({
        "status": "reset_successful",
        "message": "Temporary conversation context and history cleared completely.",
        "session": fresh.to_dict()
    }), 200


@flask_app.route("/api/v1/device/status", methods=["POST"])
def device_status_exchange():
    """
    Authenticated status and heartbeat exchange between robot and local backend.
    """
    is_authenticated, auth_error = _authenticate_request()
    if not is_authenticated:
        return auth_error

    payload = request.get_json(silent=True) or {}
    with device_command_lock:
        server_device_state["last_heartbeat_time"] = time.time()
        is_estop = server_device_state["is_emergency_stop"]
        last_seq = server_device_state["last_sequence_id"]

    return jsonify({
        "status": "online",
        "server_time": time.time(),
        "is_emergency_stop": is_estop,
        "emergency_stop_active": is_estop,
        "last_sequence_id": last_seq,
        "active_sessions": session_manager.active_session_count()
    }), 200


@flask_app.route("/api/v1/device/command", methods=["POST"])
def device_movement_command():
    """
    Validates and dispatches a bounded movement command.
    Enforces monotonic sequence IDs, timestamp staleness checks, bounds, and emergency stop.
    """
    is_authenticated, auth_error = _authenticate_request()
    if not is_authenticated:
        return auth_error

    payload = request.get_json(silent=True) or {}
    current_time_ms = int(time.time() * 1000)

    with device_command_lock:
        val_res = validate_movement_command(
            command_dict=payload,
            current_time_ms=current_time_ms,
            last_sequence_id=server_device_state["last_sequence_id"],
            is_online=True,
            allow_offline_movement=server_device_state["allow_offline_movement"],
            is_emergency_stop_active=server_device_state["is_emergency_stop"]
        )

        if not val_res.valid:
            telemetry["validation_failures"] += 1
            return jsonify({
                "error": "Command Rejected",
                "reason": val_res.reason
            }), 400

        # Handle intent-specific watermark & state updates:
        # - STOP: does not change last_sequence_id
        # - EMERGENCY_STOP: sets is_emergency_stop, does not change last_sequence_id
        # - other movement intents: advance the sequence watermark
        if val_res.command.intent == MovementIntent.EMERGENCY_STOP:
            server_device_state["is_emergency_stop"] = True
        elif val_res.command.intent == MovementIntent.STOP:
            pass
        else:
            server_device_state["last_sequence_id"] = val_res.command.command_id

    return jsonify({
        "status": "accepted",
        "reason": val_res.reason,
        "command": val_res.command.model_dump()
    }), 200


@flask_app.route("/api/v1/device/emergency_stop", methods=["POST"])
def device_emergency_stop():
    """Engages emergency stop immediately with highest priority."""
    is_authenticated, auth_error = _authenticate_request()
    if not is_authenticated:
        return auth_error

    with device_command_lock:
        server_device_state["is_emergency_stop"] = True
    return jsonify({
        "status": "emergency_stop_engaged",
        "message": "Emergency stop activated. All movement commands rejected."
    }), 200


@flask_app.route("/api/v1/device/emergency_stop/reset", methods=["POST"])
def device_emergency_stop_reset():
    """Clears emergency stop after manual operator verification."""
    is_authenticated, auth_error = _authenticate_request()
    if not is_authenticated:
        return auth_error

    with device_command_lock:
        server_device_state["is_emergency_stop"] = False
    return jsonify({
        "status": "emergency_stop_cleared",
        "message": "Emergency stop cleared. Movement commands re-enabled."
    }), 200


@flask_app.route("/api/v1/device/capabilities", methods=["GET"])
def device_capabilities():
    """
    Returns verified online and offline capabilities.
    Strictly disclaims that cloud conversation, Gemini, or remote answering works offline.
    """
    return jsonify({
        "online_features": [
            "local_wake_word_detection",
            "local_stt_whisper",
            "gemini_general_reasoning",
            "rag_college_retrieval",
            "on_demand_gemini_vision",
            "piper_tts_synthesis",
            "backend_device_telemetry_exchange"
        ],
        "offline_features": [
            "local_hardware_emergency_stop",
            "automatic_motor_stop_on_timeout_or_disconnect",
            "tft_offline_status_display",
            "supervised_bounded_movement_when_explicitly_enabled",
            "local_wake_word_or_manual_fallback"
        ],
        "offline_disclaimers": [
            "Gemini general reasoning is NOT available offline",
            "Cloud vision analysis is NOT available offline",
            "College RAG remote answering is NOT available offline",
            "Cloud conversation does NOT function offline"
        ]
    }), 200


# ==============================================================================
# FASTAPI APPLICATION SETUP (Autonomy Level 1 Movement Intent Router)
# ==============================================================================
fastapi_app = FastAPI(
    title="DORURU Robot Backend API",
    description="Backend AI Orchestrator and Device Communication Service for DORURU",
    version="1.0.0",
)

# Register Movement Intent Router from Phase 12
fastapi_app.include_router(movement_router)


@fastapi_app.get("/")
async def root():
    return {
        "robot": "DORURU",
        "description": "Educational & Lab Assistant Robot",
        "status": "online",
        "autonomy_level": 1,
    }


@fastapi_app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "autonomy": AutonomyCapabilities().model_dump(),
    }


# Mount the Flask WSGI app onto FastAPI root so that all /api/v1/* Flask endpoints
# are cleanly routed when running under ASGI (Uvicorn / FastAPI).
fastapi_app.mount("/", WSGIMiddleware(flask_app))

# Seamless Test Compatibility & Execution Bridging:
# 1. Provide .test_client() returning Flask's test client for Flask test suites.
# 2. Provide .config pointing to Flask's config dictionary.
# 3. Provide .run() executing Flask's WSGI server for background thread simulation tests.
fastapi_app.test_client = flask_app.test_client
fastapi_app.config = flask_app.config
fastapi_app.run = flask_app.run

# Canonical application export
app = fastapi_app

if __name__ == "__main__":
    print(f"Starting DORURU Unified Local Backend on {config.HOST}:{config.PORT}...")
    flask_app.run(host=config.HOST, port=config.PORT, debug=False)
