"""Unit tests for the Anthropic adapter. Mocks the SDK client — no network calls."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import anthropic
import httpx
import pytest

from buildrail.providers.adapters.anthropic import AnthropicProvider
from buildrail.providers.errors import (
    AuthenticationError,
    InvalidRequestError,
    ProviderUnavailableError,
    RateLimitError,
)
from buildrail.providers.types import Message, ProviderRequest, TextPart


def _fake_response(
    *,
    text: str = "ok",
    model: str = "claude-haiku-4-5-20251001",
    stop_reason: str = "end_turn",
    input_tokens: int = 10,
    output_tokens: int = 5,
) -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        model=model,
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


def _status_error(cls: type[Exception], message: str = "error") -> Exception:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status_code=400, request=request)
    return cls(message, response=response, body=None)  # type: ignore[call-arg]


def _provider(
    monkeypatch: pytest.MonkeyPatch,
    *,
    create_return: object = None,
    create_side_effect: Exception | None = None,
) -> tuple[AnthropicProvider, MagicMock]:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    mock_client = MagicMock()
    if create_side_effect is not None:
        mock_client.messages.create.side_effect = create_side_effect
    else:
        mock_client.messages.create.return_value = create_return or _fake_response()
    monkeypatch.setattr(
        "buildrail.providers.adapters.anthropic.anthropic.Anthropic",
        lambda **kwargs: mock_client,
    )
    return AnthropicProvider(), mock_client


def _request(text: str = "hi") -> ProviderRequest:
    return ProviderRequest(messages=(Message(role="user", content=(TextPart(text=text),)),))


def test_missing_api_key_raises_authentication_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(AuthenticationError):
        AnthropicProvider()


def test_complete_translates_request_into_anthropic_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider, mock_client = _provider(monkeypatch)
    request = ProviderRequest(
        messages=(
            Message(role="system", content=(TextPart(text="Be terse."),)),
            Message(role="user", content=(TextPart(text="Review this."),)),
        )
    )

    provider.complete(request)

    _, kwargs = mock_client.messages.create.call_args
    assert kwargs["system"] == "Be terse."
    assert kwargs["messages"] == [{"role": "user", "content": "Review this."}]
    assert isinstance(kwargs["max_tokens"], int)
    assert kwargs["model"]


def test_complete_translates_response_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    provider, _ = _provider(
        monkeypatch,
        create_return=_fake_response(
            text="looks fine",
            model="claude-haiku-4-5-20251001",
            stop_reason="end_turn",
            input_tokens=12,
            output_tokens=7,
        ),
    )

    response = provider.complete(_request())

    assert response.content == "looks fine"
    assert response.model_used == "claude-haiku-4-5-20251001"
    assert response.finish_reason == "end_turn"
    assert response.usage.input_tokens == 12
    assert response.usage.output_tokens == 7
    assert response.usage.total_tokens == 19
    assert response.cost_estimate.basis == "advisory"
    assert response.cost_estimate.amount >= 0.0


def test_complete_maps_authentication_error(monkeypatch: pytest.MonkeyPatch) -> None:
    provider, _ = _provider(
        monkeypatch,
        create_side_effect=_status_error(anthropic.AuthenticationError, "bad key"),
    )

    with pytest.raises(AuthenticationError):
        provider.complete(_request())


def test_complete_maps_rate_limit_error(monkeypatch: pytest.MonkeyPatch) -> None:
    provider, _ = _provider(
        monkeypatch,
        create_side_effect=_status_error(anthropic.RateLimitError, "slow down"),
    )

    with pytest.raises(RateLimitError):
        provider.complete(_request())


def test_complete_maps_bad_request_error(monkeypatch: pytest.MonkeyPatch) -> None:
    provider, _ = _provider(
        monkeypatch,
        create_side_effect=_status_error(anthropic.BadRequestError, "bad request"),
    )

    with pytest.raises(InvalidRequestError):
        provider.complete(_request())


def test_complete_maps_connection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    provider, _ = _provider(
        monkeypatch,
        create_side_effect=anthropic.APIConnectionError(message="conn failed", request=request),
    )

    with pytest.raises(ProviderUnavailableError):
        provider.complete(_request())


def test_complete_makes_no_network_call(monkeypatch: pytest.MonkeyPatch) -> None:
    provider, mock_client = _provider(monkeypatch)

    provider.complete(_request())

    mock_client.messages.create.assert_called_once()
