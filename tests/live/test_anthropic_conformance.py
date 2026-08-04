"""Opt-in live conformance test against the real Anthropic API.

Excluded from the default suite (pyproject.toml's `--ignore=tests/live`),
per docs/testing.md §6. Requires explicit opt-in via
BUILDRAIL_LIVE_ANTHROPIC_TESTS=1 and a real ANTHROPIC_API_KEY. Makes at
most one minimal request. Run explicitly with:
    pytest tests/live/test_anthropic_conformance.py --no-cov -p no:cacheprovider
"""

import os

import pytest

from buildrail.providers.adapters.anthropic import AnthropicProvider
from buildrail.providers.types import Message, ProviderRequest, TextPart

pytestmark = pytest.mark.skipif(
    os.environ.get("BUILDRAIL_LIVE_ANTHROPIC_TESTS") != "1"
    or not os.environ.get("ANTHROPIC_API_KEY"),
    reason=(
        "Live Anthropic conformance test requires BUILDRAIL_LIVE_ANTHROPIC_TESTS=1 "
        "and ANTHROPIC_API_KEY."
    ),
)


def test_anthropic_provider_completes_a_minimal_request() -> None:
    provider = AnthropicProvider()

    response = provider.complete(
        ProviderRequest(messages=(Message(role="user", content=(TextPart(text="Say OK."),)),))
    )

    assert response.content
    assert response.usage.total_tokens > 0
