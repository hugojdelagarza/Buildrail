"""JSON request/response helpers shared by the HTTP request handler.

Also owns CORS: allowed origins are limited to local frontend development
origins (any port on 127.0.0.1/localhost over http, plus the Tauri WebView's
`tauri://localhost` and `http://tauri.localhost`) — never `*`, since command
endpoints can execute pipelines. The allowed origin is echoed back exactly
(never wildcarded) so browsers only grant access to a request that actually
matched the allowlist.
"""

import json
from http.server import BaseHTTPRequestHandler
from typing import Any
from urllib.parse import urlsplit

from buildrail.service.routes import JsonBody

_ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost", "tauri.localhost"})


def read_json_body(raw: bytes) -> JsonBody:
    """Parse a request body as a JSON object, or return {} for an empty body.

    Returns None (a sentinel `routes.dispatch` treats as a 400) if the body
    is present but is not valid JSON or is not a JSON object.
    """
    if not raw:
        return {}
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def is_allowed_origin(origin: str) -> bool:
    """Return True for a local frontend dev origin: any port on
    127.0.0.1/localhost over http, or the Tauri WebView's own origins."""
    try:
        parsed = urlsplit(origin)
    except ValueError:
        return False
    if parsed.scheme == "tauri" and parsed.hostname == "localhost":
        return True
    return parsed.scheme == "http" and parsed.hostname in _ALLOWED_HOSTS


def send_cors_headers(handler: BaseHTTPRequestHandler) -> None:
    """Add CORS headers for the current request's Origin, if it's allowlisted."""
    origin = handler.headers.get("Origin")
    if origin and is_allowed_origin(origin):
        handler.send_header("Access-Control-Allow-Origin", origin)
        handler.send_header("Vary", "Origin")


def send_json_response(
    handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]
) -> None:
    """Write one JSON response, matching the handler's request protocol version."""
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    send_cors_headers(handler)
    handler.end_headers()
    handler.wfile.write(body)


def send_cors_preflight(handler: BaseHTTPRequestHandler) -> None:
    """Answer an OPTIONS preflight request."""
    handler.send_response(204)
    send_cors_headers(handler)
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Content-Length", "0")
    handler.end_headers()
