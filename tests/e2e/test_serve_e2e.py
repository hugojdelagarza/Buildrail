"""End-to-end test for `buildrail serve`: a real server bound to a real
localhost socket, answering real HTTP requests over the wire — not just
`routes.dispatch()` called in-process (that's covered in
`tests/unit/service/test_routes.py`). Binds to port 0 (OS-assigned) so this
never collides with a real Buildrail service or another test run. Uses
FakeProvider only; makes no live Anthropic request.
"""

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from buildrail.service import create_server


@pytest.fixture
def running_server(tmp_path: Path) -> Iterator[str]:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    (tmp_path / "main.py").write_text('"""Sample."""\n\n\ndef run():\n    pass\n', encoding="utf-8")

    server = create_server(tmp_path, host="127.0.0.1", port=0)
    host = str(server.server_address[0])
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _request(
    url: str, *, method: str = "GET", body: dict[str, Any] | None = None
) -> tuple[int, dict[str, Any]]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_server_binds_to_localhost_and_answers_health(running_server: str) -> None:
    status, body = _request(f"{running_server}/health")

    assert status == 200
    assert body["status"] == "ok"


def test_server_is_bound_to_127_0_0_1_specifically(running_server: str) -> None:
    assert running_server.startswith("http://127.0.0.1:")


def test_runs_endpoint_is_empty_before_any_command_runs(running_server: str) -> None:
    status, body = _request(f"{running_server}/runs")

    assert status == 200
    assert body == {"runs": []}


def test_explain_command_endpoint_runs_over_real_http(running_server: str) -> None:
    status, body = _request(f"{running_server}/commands/explain", method="POST", body={})

    assert status == 200
    assert body["success"] is True


def test_project_intelligence_endpoint_and_artifact_browsing_over_real_http(
    running_server: str,
) -> None:
    pipeline_status, pipeline_body = _request(
        f"{running_server}/commands/project-intelligence", method="POST", body={}
    )
    assert pipeline_status == 200
    assert pipeline_body["success"] is True

    runs_status, runs_body = _request(f"{running_server}/runs")
    assert runs_status == 200
    assert len(runs_body["runs"]) == 1
    run_id = runs_body["runs"][0]["run_id"]

    run_status, run_body = _request(f"{running_server}/runs/{run_id}")
    assert run_status == 200
    assert run_body["pipeline"] == "project-intelligence"
    assert len(run_body["artifacts"]) == 6

    artifact_id = run_body["artifacts"][0]["id"]
    artifact_status, artifact_body = _request(f"{running_server}/artifacts/{artifact_id}")
    assert artifact_status == 200
    assert artifact_body["id"] == artifact_id


def test_unknown_run_returns_404_over_real_http(running_server: str) -> None:
    status, body = _request(f"{running_server}/runs/20260101-000000-abcdef")

    assert status == 404
    assert "error" in body


def test_discovery_endpoints_respond_over_real_http(running_server: str) -> None:
    for path in ("/version", "/commands", "/skills", "/pipelines", "/project", "/config"):
        status, _body = _request(f"{running_server}{path}")
        assert status == 200, path


def test_cors_allows_a_local_dev_origin(running_server: str) -> None:
    request = urllib.request.Request(
        f"{running_server}/health", headers={"Origin": "http://localhost:5173"}
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        assert response.headers.get("Access-Control-Allow-Origin") == "http://localhost:5173"


def test_cors_rejects_a_remote_origin(running_server: str) -> None:
    request = urllib.request.Request(
        f"{running_server}/health", headers={"Origin": "https://evil.example.com"}
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        assert response.headers.get("Access-Control-Allow-Origin") is None


def test_cors_preflight_options_request_succeeds(running_server: str) -> None:
    request = urllib.request.Request(
        f"{running_server}/commands/verify",
        method="OPTIONS",
        headers={"Origin": "http://127.0.0.1:5173"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        assert response.status == 204
        assert response.headers.get("Access-Control-Allow-Origin") == "http://127.0.0.1:5173"
        assert "POST" in (response.headers.get("Access-Control-Allow-Methods") or "")


def test_cors_preflight_allows_put_for_the_config_endpoint(running_server: str) -> None:
    # A real browser sends this preflight before PUT /config; if the server
    # doesn't advertise PUT here, the browser blocks the real request and it
    # never reaches the handler at all — this is what test_put_config_*
    # below cannot catch on its own, since urllib doesn't enforce CORS.
    request = urllib.request.Request(
        f"{running_server}/config",
        method="OPTIONS",
        headers={"Origin": "http://127.0.0.1:5173"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        assert response.status == 204
        assert "PUT" in (response.headers.get("Access-Control-Allow-Methods") or "")


def test_put_config_endpoint_creates_a_config_over_real_http(running_server: str) -> None:
    status, body = _request(f"{running_server}/config", method="PUT", body={"provider": "fake"})

    assert status == 200
    assert body["status"] == "ok"
    assert body["provider"] == "fake"


def test_put_config_endpoint_rejects_an_unsupported_provider_over_real_http(
    running_server: str,
) -> None:
    status, body = _request(f"{running_server}/config", method="PUT", body={"provider": "openai"})

    assert status == 400
    assert "error" in body


def test_no_response_ever_contains_a_credential_looking_value(running_server: str) -> None:
    for path in ("/health", "/version", "/project", "/config", "/skills", "/pipelines"):
        _status, body = _request(f"{running_server}{path}")
        serialized = json.dumps(body)
        assert "ANTHROPIC_API_KEY" not in serialized
        assert "sk-ant" not in serialized
