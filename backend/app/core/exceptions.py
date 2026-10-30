"""Domain exceptions for DORURU backend.

Provides consistent error codes and HTTP status code mappings.
"""

from typing import Any, Optional


class DoruruException(Exception):
    """Base exception for all DORURU application errors."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: Optional[Any] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details


class AuthenticationError(DoruruException):
    """Raised when device or client authentication fails."""

    def __init__(self, message: str = "Invalid or missing credentials", details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="AUTHENTICATION_FAILED",
            status_code=401,
            details=details,
        )


class PermissionDeniedError(DoruruException):
    """Raised when an authenticated device lacks permissions."""

    def __init__(self, message: str = "Action not permitted for this device", details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="PERMISSION_DENIED",
            status_code=403,
            details=details,
        )


class PayloadTooLargeError(DoruruException):
    """Raised when an uploaded payload exceeds the configured byte limit."""

    def __init__(self, message: str = "Payload exceeds maximum allowed size", details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="PAYLOAD_TOO_LARGE",
            status_code=413,
            details=details,
        )


class UnsupportedMediaTypeError(DoruruException):
    """Raised when an uploaded file or body is not an allowed media type."""

    def __init__(self, message: str = "Unsupported media type", details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="UNSUPPORTED_MEDIA_TYPE",
            status_code=415,
            details=details,
        )


class InvalidCommandError(DoruruException):
    """Raised when a movement or control command violates safety bounds or schema."""

    def __init__(self, message: str = "Command rejected: exceeds safety bounds or invalid intent", details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="INVALID_COMMAND",
            status_code=422,
            details=details,
        )


class StaleCommandError(DoruruException):
    """Raised when a command's timestamp exceeds the replay/freshness window."""

    def __init__(self, message: str = "Command rejected: timestamp expired/stale", details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="STALE_COMMAND",
            status_code=400,
            details=details,
        )


class SessionNotFoundError(DoruruException):
    """Raised when a requested conversation session does not exist."""

    def __init__(self, message: str = "Session not found", details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="SESSION_NOT_FOUND",
            status_code=404,
            details=details,
        )


class SessionExpiredError(DoruruException):
    """Raised when a conversation session has expired due to inactivity."""

    def __init__(self, message: str = "Session has expired due to inactivity", details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="SESSION_EXPIRED",
            status_code=410,
            details=details,
        )


class DeviceNotFoundError(DoruruException):
    """Raised when a device ID is not found in the registry."""

    def __init__(self, message: str = "Device not registered", details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="DEVICE_NOT_FOUND",
            status_code=404,
            details=details,
        )


class ServiceUnavailableError(DoruruException):
    """Raised when a requested subsystem or service is unavailable."""

    def __init__(self, message: str = "Service temporarily unavailable", details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="SERVICE_UNAVAILABLE",
            status_code=503,
            details=details,
        )
