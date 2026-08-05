from buildrail.service.transport import is_allowed_origin


def test_allows_localhost_with_any_port() -> None:
    assert is_allowed_origin("http://localhost:5173") is True
    assert is_allowed_origin("http://localhost:3000") is True


def test_allows_127_0_0_1_with_any_port() -> None:
    assert is_allowed_origin("http://127.0.0.1:5173") is True
    assert is_allowed_origin("http://127.0.0.1:8080") is True


def test_allows_tauri_origins() -> None:
    assert is_allowed_origin("tauri://localhost") is True
    assert is_allowed_origin("http://tauri.localhost") is True


def test_rejects_a_remote_origin() -> None:
    assert is_allowed_origin("http://evil.example.com") is False
    assert is_allowed_origin("https://buildrail.dev") is False


def test_rejects_https_on_localhost() -> None:
    assert is_allowed_origin("https://localhost:5173") is False


def test_rejects_a_malformed_origin() -> None:
    assert is_allowed_origin("not a url") is False
    assert is_allowed_origin("") is False
