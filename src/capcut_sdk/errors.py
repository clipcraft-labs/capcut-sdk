"""Stable exception types exposed by the SDK."""


class CapCutSDKError(Exception):
    """Base class for SDK errors."""


class ConfigurationError(CapCutSDKError):
    """The caller supplied incomplete or invalid SDK configuration."""


class ApiError(CapCutSDKError):
    """The remote API returned an error response."""

    def __init__(self, message: str, *, status_code: int | None = None, payload=None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload

