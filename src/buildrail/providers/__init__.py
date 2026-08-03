"""Buildrail's Provider Gateway: the provider-neutral boundary to AI models."""

from buildrail.providers.errors import (
    AuthenticationError,
    ContentFilterError,
    InvalidRequestError,
    ProviderError,
    ProviderUnavailableError,
    RateLimitError,
    UnknownProviderError,
    UnsupportedProviderError,
)
from buildrail.providers.gateway import ProviderGateway
from buildrail.providers.registry import create_provider
from buildrail.providers.types import (
    CostEstimate,
    Message,
    Provider,
    ProviderCapabilities,
    ProviderRequest,
    ProviderResponse,
    TextPart,
    Usage,
)

__all__ = [
    "AuthenticationError",
    "ContentFilterError",
    "CostEstimate",
    "InvalidRequestError",
    "Message",
    "Provider",
    "ProviderCapabilities",
    "ProviderError",
    "ProviderGateway",
    "ProviderRequest",
    "ProviderResponse",
    "ProviderUnavailableError",
    "RateLimitError",
    "TextPart",
    "UnknownProviderError",
    "UnsupportedProviderError",
    "Usage",
    "create_provider",
]
