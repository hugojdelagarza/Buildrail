import pytest

from buildrail.providers.adapters.fake import FakeProvider
from buildrail.providers.errors import UnsupportedProviderError
from buildrail.providers.registry import create_provider


def test_create_provider_returns_fake_provider_for_fake() -> None:
    provider = create_provider("fake")

    assert isinstance(provider, FakeProvider)


def test_create_provider_raises_for_unsupported_name() -> None:
    with pytest.raises(UnsupportedProviderError, match="bogus"):
        create_provider("bogus")
