"""Provider Gateway data types: requests, responses, capabilities, and the Provider protocol."""

from dataclasses import dataclass
from typing import Literal, Protocol

Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class TextPart:
    """A text segment of a message's content."""

    text: str


@dataclass(frozen=True)
class Message:
    """A single turn in a provider request's conversation."""

    role: Role
    content: tuple[TextPart, ...]


@dataclass(frozen=True)
class ProviderRequest:
    """A provider-neutral request for a single completion."""

    messages: tuple[Message, ...]
    capability_tier: str = "default"


@dataclass(frozen=True)
class Usage:
    """Token accounting for a single provider call."""

    input_tokens: int
    output_tokens: int
    total_tokens: int


@dataclass(frozen=True)
class CostEstimate:
    """An advisory cost estimate for a single provider call."""

    amount: float
    currency: str = "USD"
    basis: Literal["advisory"] = "advisory"


@dataclass(frozen=True)
class ProviderResponse:
    """A provider-neutral response to a single completion request."""

    content: str
    model_used: str
    finish_reason: str
    usage: Usage
    cost_estimate: CostEstimate


@dataclass(frozen=True)
class ProviderCapabilities:
    """What a provider supports, checked before a request is made."""

    supports_streaming: bool
    supports_structured_output: bool
    supports_vision: bool
    supports_tools: bool
    max_context_tokens: int
    capability_tiers: tuple[str, ...]


class Provider(Protocol):
    """The interface every concrete provider adapter must satisfy."""

    def capabilities(self) -> ProviderCapabilities:
        """Return what this provider supports."""
        ...

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        """Produce a single completion for the given request."""
        ...
