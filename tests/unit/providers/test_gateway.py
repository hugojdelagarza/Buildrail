import pytest

from buildrail.providers import (
    Message,
    ProviderCapabilities,
    ProviderRequest,
    ProviderResponse,
    RateLimitError,
    UnknownProviderError,
)
from buildrail.providers.adapters.fake import FakeProvider
from buildrail.providers.gateway import ProviderGateway
from buildrail.providers.types import TextPart


def _request() -> ProviderRequest:
    return ProviderRequest(messages=(Message(role="user", content=(TextPart(text="hi"),)),))


def test_complete_delegates_to_the_wrapped_provider() -> None:
    gateway = ProviderGateway(FakeProvider())

    response = gateway.complete(_request())

    assert isinstance(response, ProviderResponse)
    assert response.content


def test_capabilities_delegates_to_the_wrapped_provider() -> None:
    gateway = ProviderGateway(FakeProvider())

    capabilities = gateway.capabilities()

    assert isinstance(capabilities, ProviderCapabilities)
    assert capabilities.capability_tiers == ("default",)


def test_complete_reraises_known_provider_errors_unchanged() -> None:
    gateway = ProviderGateway(FakeProvider(error=RateLimitError("slow down")))

    with pytest.raises(RateLimitError, match="slow down"):
        gateway.complete(_request())


class _ExplodingProvider:
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_streaming=False,
            supports_structured_output=False,
            supports_vision=False,
            supports_tools=False,
            max_context_tokens=1,
            capability_tiers=("default",),
        )

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        raise RuntimeError("boom")


def test_complete_wraps_unexpected_errors_in_unknown_provider_error() -> None:
    gateway = ProviderGateway(_ExplodingProvider())

    with pytest.raises(UnknownProviderError, match="boom"):
        gateway.complete(_request())
