import pytest

from buildrail.providers.adapters.fake import FakeProvider
from buildrail.providers.errors import RateLimitError
from buildrail.providers.types import Message, ProviderRequest, TextPart


def _request(text: str) -> ProviderRequest:
    return ProviderRequest(messages=(Message(role="user", content=(TextPart(text=text),)),))


def test_capabilities_are_fixed_and_offline_friendly() -> None:
    provider = FakeProvider()

    capabilities = provider.capabilities()

    assert capabilities.supports_streaming is False
    assert capabilities.supports_structured_output is False
    assert capabilities.supports_vision is False
    assert capabilities.supports_tools is False
    assert capabilities.capability_tiers == ("default",)


def test_complete_is_deterministic_for_the_same_request() -> None:
    provider = FakeProvider()
    request = _request("hello")

    first = provider.complete(request)
    second = provider.complete(request)

    assert first == second


def test_complete_reflects_the_prompt_in_its_response() -> None:
    provider = FakeProvider()

    response = provider.complete(_request("hello"))

    usage = response.usage
    assert "hello" in response.content
    assert response.finish_reason == "stop"
    assert response.model_used
    assert usage.total_tokens == usage.input_tokens + usage.output_tokens
    assert response.cost_estimate.amount == 0.0


def test_complete_raises_the_configured_error() -> None:
    provider = FakeProvider(error=RateLimitError("too fast"))

    with pytest.raises(RateLimitError, match="too fast"):
        provider.complete(_request("hello"))
