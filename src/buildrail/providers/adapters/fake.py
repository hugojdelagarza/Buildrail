"""FakeProvider: a deterministic, offline provider for development and tests."""

from buildrail.providers.errors import ProviderError
from buildrail.providers.types import (
    CostEstimate,
    Message,
    ProviderCapabilities,
    ProviderRequest,
    ProviderResponse,
    Usage,
)

_MODEL_NAME = "fake-model"


class FakeProvider:
    """A local, deterministic Provider used by default in development and tests."""

    def __init__(self, *, error: ProviderError | None = None) -> None:
        self._error = error

    def capabilities(self) -> ProviderCapabilities:
        """Return this provider's fixed, offline-friendly capabilities."""
        return ProviderCapabilities(
            supports_streaming=False,
            supports_structured_output=False,
            supports_vision=False,
            supports_tools=False,
            max_context_tokens=100_000,
            capability_tiers=("default",),
        )

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        """Return a deterministic, canned completion, or raise the configured error."""
        if self._error is not None:
            raise self._error

        prompt = _last_user_text(request.messages)
        content = f"[fake response] {prompt}" if prompt else "[fake response]"
        input_tokens = _estimate_tokens(prompt)
        output_tokens = _estimate_tokens(content)

        return ProviderResponse(
            content=content,
            model_used=_MODEL_NAME,
            finish_reason="stop",
            usage=Usage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
            ),
            cost_estimate=CostEstimate(amount=0.0),
        )


def _last_user_text(messages: tuple[Message, ...]) -> str:
    for message in reversed(messages):
        if message.role == "user":
            return "".join(part.text for part in message.content)
    return ""


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)
