"""Proof that the Anthropic SDK stays inside its adapter, and that the
default (Fake Provider) path never attempts a real network connection.
"""

import socket
from pathlib import Path

import pytest

from buildrail.providers.adapters.fake import FakeProvider
from buildrail.providers.gateway import ProviderGateway
from buildrail.providers.registry import create_provider
from buildrail.providers.types import Message, ProviderRequest, TextPart

_SRC_ROOT = Path(__file__).resolve().parents[3] / "src" / "buildrail"
_ADAPTER_PATH = _SRC_ROOT / "providers" / "adapters" / "anthropic.py"


def test_anthropic_sdk_is_imported_only_by_its_adapter_module() -> None:
    python_files = [
        path
        for path in _SRC_ROOT.rglob("*.py")
        if path != _ADAPTER_PATH and "__pycache__" not in path.parts
    ]
    offenders = [path for path in python_files if "import anthropic" in path.read_text("utf-8")]
    assert offenders == []


def test_fake_provider_path_makes_no_network_call(monkeypatch: pytest.MonkeyPatch) -> None:
    def _blocked_connect(*args: object, **kwargs: object) -> None:
        raise AssertionError("Unexpected network connection attempt during Fake Provider path.")

    monkeypatch.setattr(socket.socket, "connect", _blocked_connect)

    provider = create_provider("fake")
    gateway = ProviderGateway(provider)
    request = ProviderRequest(messages=(Message(role="user", content=(TextPart(text="hi"),)),))

    response = gateway.complete(request)

    assert isinstance(provider, FakeProvider)
    assert response.content
