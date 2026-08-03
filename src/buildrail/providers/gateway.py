"""The Provider Gateway: the single boundary between Buildrail and any AI provider."""

from buildrail.providers.errors import ProviderError, UnknownProviderError
from buildrail.providers.types import (
    Provider,
    ProviderCapabilities,
    ProviderRequest,
    ProviderResponse,
)


class ProviderGateway:
    """Wraps a single Provider, normalizing its errors for every caller."""

    def __init__(self, provider: Provider) -> None:
        self._provider = provider

    def capabilities(self) -> ProviderCapabilities:
        """Return the wrapped provider's capabilities."""
        return self._provider.capabilities()

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        """Send a request to the wrapped provider, normalizing unexpected errors."""
        try:
            return self._provider.complete(request)
        except ProviderError:
            raise
        except Exception as exc:
            raise UnknownProviderError(f"Unexpected error from provider: {exc}") from exc
