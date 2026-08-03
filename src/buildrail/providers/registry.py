"""Resolve a configured provider name to a concrete Provider instance — the
only module allowed to import a concrete adapter directly."""

from collections.abc import Callable

from buildrail.providers.adapters.fake import FakeProvider
from buildrail.providers.errors import UnsupportedProviderError
from buildrail.providers.types import Provider

_FACTORIES: dict[str, Callable[[], Provider]] = {
    "fake": FakeProvider,
}


def create_provider(name: str) -> Provider:
    """Return a new Provider instance for the given configured provider name."""
    try:
        factory = _FACTORIES[name]
    except KeyError:
        supported = ", ".join(sorted(_FACTORIES))
        raise UnsupportedProviderError(
            f"No provider registered for '{name}'. Supported providers: {supported}."
        ) from None
    return factory()
