"""
backend/app/session/session_manager.py - Session Lifecycle & Ephemeral Context Management

Enforces:
- Ephemeral session memory: sessions expire after inactivity.
- Explicit session reset clears all temporary context and conversation history.
- Expired sessions are purged immediately, preventing cross-session memory leakage.
"""

import time
import uuid
import threading
from typing import Optional, Dict, Any, List
from .. import config

DEFAULT_SESSION_TTL_SECONDS = int(getattr(config, "SESSION_EXPIRY_SECONDS", 900)) # 15 minutes default
MIN_SESSION_TTL_SECONDS = 1
MAX_SESSION_TTL_SECONDS = 86400 # 24 hours max
DEFAULT_MAX_SESSIONS = 1000

class Session:
    """Represents an active ephemeral conversation session with DORURU."""
    def __init__(self, session_id: Optional[str] = None, ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS):
        self.session_id: str = session_id or str(uuid.uuid4())
        self.created_at: float = time.time()
        self.last_activity_at: float = self.created_at
        self.ttl_seconds: int = ttl_seconds
        self.conversation_history: List[Dict[str, str]] = []
        self.context: Dict[str, Any] = {}

    def is_expired(self, current_time: Optional[float] = None) -> bool:
        now = current_time if current_time is not None else time.time()
        return (now - self.last_activity_at) > self.ttl_seconds

    def touch(self, current_time: Optional[float] = None):
        self.last_activity_at = current_time if current_time is not None else time.time()

    def add_message(self, role: str, content: str):
        self.touch()
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": time.time()
        })

    def clear_memory(self):
        """Strictly wipes all temporary conversation context and history."""
        self.conversation_history.clear()
        self.context.clear()
        self.touch()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "last_activity_at": self.last_activity_at,
            "ttl_seconds": self.ttl_seconds,
            "turns_count": len(self.conversation_history),
            "is_expired": self.is_expired()
        }

class SessionManager:
    """Thread-safe manager for session lifecycle, expiration, and memory purging."""
    def __init__(
        self,
        default_ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS,
        max_sessions: int = DEFAULT_MAX_SESSIONS
    ):
        self.default_ttl: int = default_ttl_seconds
        self.max_sessions: int = max_sessions
        self._sessions: Dict[str, Session] = {}
        self._lock = threading.Lock()

    def create_session(self, ttl_seconds: Optional[int] = None) -> Session:
        if ttl_seconds is None:
            ttl = self.default_ttl
        else:
            if not isinstance(ttl_seconds, int) or isinstance(ttl_seconds, bool):
                raise ValueError("ttl_seconds must be an integer")
            if ttl_seconds < MIN_SESSION_TTL_SECONDS or ttl_seconds > MAX_SESSION_TTL_SECONDS:
                raise ValueError(
                    f"ttl_seconds must be an integer between {MIN_SESSION_TTL_SECONDS} and {MAX_SESSION_TTL_SECONDS}"
                )
            ttl = ttl_seconds

        with self._lock:
            # Under session lock, purge expired sessions before adding new session
            now = time.time()
            expired_ids = [sid for sid, s in self._sessions.items() if s.is_expired(now)]
            for sid in expired_ids:
                self._sessions[sid].clear_memory()
                del self._sessions[sid]

            # Enforce defined maximum size for _sessions
            if len(self._sessions) >= self.max_sessions:
                raise RuntimeError(f"Session capacity reached (maximum {self.max_sessions} active sessions)")

            session = Session(ttl_seconds=ttl)
            self._sessions[session.session_id] = session
            return session

    def get_session(self, session_id: str) -> Optional[Session]:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return None
            if session.is_expired():
                # Session expired: strictly clear memory and remove
                session.clear_memory()
                del self._sessions[session_id]
                return None
            session.touch()
            return session

    def reset_session(self, session_id: str) -> Session:
        """Explicitly wipes memory and returns a refreshed clean session."""
        with self._lock:
            existing = self._sessions.get(session_id)
            if existing:
                existing.clear_memory()
                # Create a fresh clean session replacing the old one
                fresh_session = Session(ttl_seconds=existing.ttl_seconds)
                del self._sessions[session_id]
                self._sessions[fresh_session.session_id] = fresh_session
                return fresh_session
            else:
                fresh = Session(ttl_seconds=self.default_ttl)
                self._sessions[fresh.session_id] = fresh
                return fresh

    def cleanup_expired(self, current_time: Optional[float] = None) -> int:
        now = current_time if current_time is not None else time.time()
        purged = 0
        with self._lock:
            expired_ids = [
                sid for sid, sess in self._sessions.items()
                if sess.is_expired(now)
            ]
            for sid in expired_ids:
                self._sessions[sid].clear_memory()
                del self._sessions[sid]
                purged += 1
        return purged

    def active_session_count(self) -> int:
        with self._lock:
            return len(self._sessions)

    def clear_all(self):
        """Purges all sessions and clears memory."""
        with self._lock:
            for s in self._sessions.values():
                s.clear_memory()
            self._sessions.clear()

