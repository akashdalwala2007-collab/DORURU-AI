import re
from typing import Optional
from backend.app.schemas.movement import (
    MovementDirection,
    AutonomyLevel,
    MovementIntent,
    MovementIntentRequest,
)


class MovementIntentError(Exception):
    """Base exception for movement intent errors."""
    pass


class UnsupportedAutonomyError(MovementIntentError):
    """Raised when user requests autonomy Level 2-4 features that are disabled."""
    pass


class UnknownMovementIntentError(MovementIntentError):
    """Raised when text cannot be safely mapped to a recognized bounded intent."""
    pass


class MovementIntentParser:
    """
    Translates natural-language text into strictly validated, bounded movement intents.
    
    Enforces strict safety rules:
    1. Movement commands never execute directly from arbitrary text.
    2. "Come here" maps to bounded forward motion with an explicit disclaimer
       that it cannot locate the user (Level 4 tracking disabled).
    3. Autonomous roaming and user-following are strictly rejected.
    4. Duration is capped at MAX_DURATION_MS (3000ms).
    5. Speed is capped at MAX_SPEED_PWM (220).
    """

    DEFAULT_SPEED_PWM = 150
    DEFAULT_DURATION_MS = 1000
    MIN_SPEED_PWM = 60
    MAX_SPEED_PWM = 220
    MIN_DURATION_MS = 50
    MAX_DURATION_MS = 3000

    # Phrases mapped to directions
    _STOP_PATTERNS = [
        r"\bstop\b", r"\bhalt\b", r"\bfreeze\b", r"\bemergency\s+stop\b",
        r"\bbrake\b",
        r"\bdon'?t\s+move\b(?!.*\b(?:forward|backward|back|left|right(?!\s+now))\b)",
        r"\bdo\s+not\s+move\b(?!.*\b(?:forward|backward|back|left|right(?!\s+now))\b)",
        r"\bwait\b"
    ]
    _NEGATION_PATTERNS = [
        r"\b(?:don'?t|do\s+not|never|not|no|cannot|can'?t|won'?t)\b"
    ]
    _COME_HERE_PATTERNS = [
        r"\bcome\s+here\b", r"\bcome\s+closer\b", r"\bcome\s+to\s+me\b", r"\bcome\s+near\b"
    ]
    _FORWARD_PATTERNS = [
        r"\bforward\b", r"\bgo\s+forward\b", r"\bmove\s+forward\b",
        r"\bdrive\s+forward\b"
    ]
    _GO_BACK_PATTERNS = [
        r"\bgo\s+back\b", r"\bback\s+up\b", r"\breverse\b",
        r"\bmove\s+back\b", r"\bstep\s+back\b", r"\bbackward\b"
    ]
    _TURN_LEFT_PATTERNS = [
        r"\bturn\s+left\b", r"\bpivot\s+left\b", r"\bspin\s+left\b",
        r"\brotate\s+left\b"
    ]
    _TURN_RIGHT_PATTERNS = [
        r"\bturn\s+right\b", r"\bpivot\s+right\b", r"\bspin\s+right\b",
        r"\brotate\s+right\b"
    ]

    # Strictly forbidden autonomy level 2-4 requests
    _FORBIDDEN_AUTONOMY_PATTERNS = [
        (r"\bfollow\s+(me|the\s+user|him|her|person)\b", 
         "Autonomous user-following is disabled (Autonomy Level 4 sensors not confirmed)."),
        (r"\btrack\s+(me|user|person|face)\b", 
         "Person-tracking navigation is disabled (Autonomy Level 4 sensors not confirmed)."),
        (r"\b(roam|patrol|explore|wander)\b", 
         "Autonomous exploration/roaming is disabled (Autonomy Level 2/3 sensors not confirmed)."),
        (r"\b(navigate|go)\s+to\s+(room|lab|kitchen|door|target|destination)\b", 
         "SLAM destination navigation is disabled (Autonomy Level 3/4 localization unconfirmed)."),
    ]

    @classmethod
    def parse(cls, request: MovementIntentRequest) -> MovementIntent:
        """
        Parses a MovementIntentRequest into a validated MovementIntent.
        """
        text = request.text.strip().lower()

        # 1. Check STOP patterns with absolute highest priority (always immediate STOP)
        if any(re.search(p, text) for p in cls._STOP_PATTERNS):
            return MovementIntent(
                direction=MovementDirection.STOP,
                speed_pwm=cls.MIN_SPEED_PWM,
                duration_ms=cls.MIN_DURATION_MS,
                autonomy_level=AutonomyLevel.LEVEL_1_BOUNDED_TIMED,
                is_approximate_timed=True,
                user_localization_used=False,
                safety_disclaimer="Immediate stop command.",
                original_text=request.text,
            )

        # 2. Check for unconfirmed autonomy Level 2-4 requests and reject immediately
        for pattern, reason in cls._FORBIDDEN_AUTONOMY_PATTERNS:
            if re.search(pattern, text):
                raise UnsupportedAutonomyError(reason)

        # 3. Reject negated movement commands (unless they matched an explicit STOP phrase above)
        if any(re.search(p, text) for p in cls._NEGATION_PATTERNS):
            raise UnknownMovementIntentError(
                f"Negated phrase '{request.text}' rejected for safety. Negated movement commands do not produce movement intents."
            )

        # 4. For active motion commands, extract and validate duration and speed bounds
        detected_duration_ms = cls._extract_duration(text)
        final_duration_ms = (
            request.duration_override_ms or 
            detected_duration_ms or 
            cls.DEFAULT_DURATION_MS
        )

        # Clamp/enforce duration boundaries for motion commands
        if final_duration_ms < cls.MIN_DURATION_MS or final_duration_ms > cls.MAX_DURATION_MS:
            raise MovementIntentError(
                f"Requested duration {final_duration_ms}ms is outside safe bounds "
                f"[{cls.MIN_DURATION_MS}ms .. {cls.MAX_DURATION_MS}ms]."
            )

        # Speed resolution
        final_speed_pwm = request.speed_override or cls.DEFAULT_SPEED_PWM
        if final_speed_pwm < cls.MIN_SPEED_PWM or final_speed_pwm > cls.MAX_SPEED_PWM:
            raise MovementIntentError(
                f"Requested speed {final_speed_pwm} PWM is outside safe bounds "
                f"[{cls.MIN_SPEED_PWM} .. {cls.MAX_SPEED_PWM}]."
            )

        # 5. Match Direction for Active Motion Commands

        # "Come here" check -> FORWARD with approximate/no-localization disclaimer
        if any(re.search(p, text) for p in cls._COME_HERE_PATTERNS):
            return MovementIntent(
                direction=MovementDirection.FORWARD,
                speed_pwm=final_speed_pwm,
                duration_ms=min(final_duration_ms, 1500), # conservative 1.5s bound for come here
                autonomy_level=AutonomyLevel.LEVEL_1_BOUNDED_TIMED,
                is_approximate_timed=True,
                user_localization_used=False,
                safety_disclaimer=(
                    "Command 'come here' mapped to bounded forward movement. "
                    "Note: distance is approximate and does NOT locate user position (Level 4 tracking unconfirmed)."
                ),
                original_text=request.text,
            )

        # "Go back" check -> REVERSE with approximate disclaimer
        if any(re.search(p, text) for p in cls._GO_BACK_PATTERNS):
            return MovementIntent(
                direction=MovementDirection.REVERSE,
                speed_pwm=final_speed_pwm,
                duration_ms=min(final_duration_ms, 1500),
                autonomy_level=AutonomyLevel.LEVEL_1_BOUNDED_TIMED,
                is_approximate_timed=True,
                user_localization_used=False,
                safety_disclaimer=(
                    "Command 'go back' mapped to bounded reverse movement. "
                    "Note: distance is approximate without wheel encoders."
                ),
                original_text=request.text,
            )

        # Standard Forward
        if any(re.search(p, text) for p in cls._FORWARD_PATTERNS):
            return MovementIntent(
                direction=MovementDirection.FORWARD,
                speed_pwm=final_speed_pwm,
                duration_ms=final_duration_ms,
                autonomy_level=AutonomyLevel.LEVEL_1_BOUNDED_TIMED,
                is_approximate_timed=True,
                user_localization_used=False,
                safety_disclaimer="Bounded timed forward motion. Distance is approximate.",
                original_text=request.text,
            )

        # Turn Left / Pivot Left
        if any(re.search(p, text) for p in cls._TURN_LEFT_PATTERNS):
            return MovementIntent(
                direction=MovementDirection.TURN_LEFT,
                speed_pwm=final_speed_pwm,
                duration_ms=min(final_duration_ms, 1000), # 1s max for pivot
                autonomy_level=AutonomyLevel.LEVEL_1_BOUNDED_TIMED,
                is_approximate_timed=True,
                user_localization_used=False,
                safety_disclaimer="Bounded timed pivot left. Rotation angle is approximate.",
                original_text=request.text,
            )

        # Turn Right / Pivot Right
        if any(re.search(p, text) for p in cls._TURN_RIGHT_PATTERNS):
            return MovementIntent(
                direction=MovementDirection.TURN_RIGHT,
                speed_pwm=final_speed_pwm,
                duration_ms=min(final_duration_ms, 1000),
                autonomy_level=AutonomyLevel.LEVEL_1_BOUNDED_TIMED,
                is_approximate_timed=True,
                user_localization_used=False,
                safety_disclaimer="Bounded timed pivot right. Rotation angle is approximate.",
                original_text=request.text,
            )

        # Unrecognized phrase
        raise UnknownMovementIntentError(
            f"Phrase '{request.text}' could not be safely mapped to a verified movement intent. "
            f"Supported intents: STOP, FORWARD, REVERSE, TURN_LEFT, TURN_RIGHT, 'come here', 'go back'."
        )

    @classmethod
    def _extract_duration(cls, text: str) -> Optional[int]:
        """Extracts seconds or ms if explicitly mentioned in phrase."""
        # Check seconds, e.g. "for 2 seconds", "1.5s", "1 sec"
        sec_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:seconds?|secs?|s)\b", text)
        if sec_match:
            try:
                seconds = float(sec_match.group(1))
                return int(seconds * 1000)
            except ValueError:
                pass

        # Check milliseconds, e.g. "500 ms"
        ms_match = re.search(r"(\d+)\s*(?:milliseconds?|ms)\b", text)
        if ms_match:
            try:
                return int(ms_match.group(1))
            except ValueError:
                pass

        return None

