"""Errors the Provider Gateway and its adapters raise, normalized across providers."""


class ProviderError(Exception):
    """Base class for all provider errors the Core Engine can present cleanly."""


class UnsupportedProviderError(ProviderError):
    """Raised when a configured provider name has no registered implementation."""


class AuthenticationError(ProviderError):
    """Raised when a provider rejects missing or invalid credentials."""


class InvalidRequestError(ProviderError):
    """Raised when a request is malformed or requests an unsupported capability."""


class ContentFilterError(ProviderError):
    """Raised when a provider refuses or filters its own response."""


class RateLimitError(ProviderError):
    """Raised when a provider throttles the caller. Retryable by future callers."""


class ProviderUnavailableError(ProviderError):
    """Raised on a transient provider failure such as a timeout. Retryable."""


class UnknownProviderError(ProviderError):
    """Wraps any error a provider raises that isn't already a ProviderError."""
