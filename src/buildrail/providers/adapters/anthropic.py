"""AnthropicProvider: a real Provider backed by Anthropic's Claude models.

The only module in Buildrail allowed to import the `anthropic` SDK
(docs/project-layout.md's provider adapter boundary). Reads
ANTHROPIC_API_KEY from the environment only — never from config, never
logged, never placed in any request/response type the rest of the
system sees.
"""

import os

import anthropic
from anthropic.types import MessageParam

from buildrail.providers.errors import (
    AuthenticationError,
    InvalidRequestError,
    ProviderUnavailableError,
    RateLimitError,
    UnknownProviderError,
)
from buildrail.providers.types import (
    CostEstimate,
    ProviderCapabilities,
    ProviderRequest,
    ProviderResponse,
    Usage,
)

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"
_MAX_OUTPUT_TOKENS = 1024

# Advisory only (docs/provider-interface.md §4) — USD per million tokens
# (input, output). Verify against Anthropic's current pricing page before
# relying on this for anything beyond a rough estimate.
_PRICE_PER_MILLION_TOKENS_USD: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5-20251001": (1.0, 5.0),
}


class AnthropicProvider:
    """A Provider backed by Anthropic's Messages API."""

    def __init__(self, *, model: str | None = None) -> None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise AuthenticationError(
                "ANTHROPIC_API_KEY is not set. Set it in your environment before using "
                'provider = "anthropic".'
            )
        self._model = model or _DEFAULT_MODEL
        self._client = anthropic.Anthropic(api_key=api_key)

    def capabilities(self) -> ProviderCapabilities:
        """Return this provider's capabilities (single-request, text-only, for now)."""
        return ProviderCapabilities(
            supports_streaming=False,
            supports_structured_output=False,
            supports_vision=False,
            supports_tools=False,
            max_context_tokens=200_000,
            capability_tiers=("default",),
        )

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        """Send one request to Claude and translate the response, mapping SDK errors."""
        system_text, messages = _translate_request(request)
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=_MAX_OUTPUT_TOKENS,
                system=system_text,
                messages=messages,
            )
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
            raise AuthenticationError(str(exc)) from exc
        except anthropic.RateLimitError as exc:
            raise RateLimitError(str(exc)) from exc
        except (
            anthropic.BadRequestError,
            anthropic.NotFoundError,
            anthropic.UnprocessableEntityError,
        ) as exc:
            raise InvalidRequestError(str(exc)) from exc
        except (anthropic.APIConnectionError, anthropic.APIStatusError) as exc:
            raise ProviderUnavailableError(str(exc)) from exc
        except anthropic.APIError as exc:
            raise UnknownProviderError(str(exc)) from exc

        return _translate_response(response)


def _translate_request(request: ProviderRequest) -> tuple[str, list[MessageParam]]:
    system_parts: list[str] = []
    messages: list[MessageParam] = []
    for message in request.messages:
        text = "".join(part.text for part in message.content)
        if message.role == "system":
            system_parts.append(text)
        else:
            messages.append(MessageParam(role=message.role, content=text))
    return "\n\n".join(system_parts), messages


def _translate_response(response: anthropic.types.Message) -> ProviderResponse:
    content = "".join(block.text for block in response.content if block.type == "text")
    usage = Usage(
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        total_tokens=response.usage.input_tokens + response.usage.output_tokens,
    )
    return ProviderResponse(
        content=content,
        model_used=response.model,
        finish_reason=response.stop_reason or "unknown",
        usage=usage,
        cost_estimate=_estimate_cost(response.model, usage),
    )


def _estimate_cost(model: str, usage: Usage) -> CostEstimate:
    input_rate, output_rate = _PRICE_PER_MILLION_TOKENS_USD.get(model, (0.0, 0.0))
    amount = (usage.input_tokens * input_rate + usage.output_tokens * output_rate) / 1_000_000
    return CostEstimate(amount=round(amount, 6))
