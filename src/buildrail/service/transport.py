"""JSON request/response helpers shared by the HTTP request handler."""

import json
from http.server import BaseHTTPRequestHandler
from typing import Any

from buildrail.service.routes import JsonBody


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


def send_json_response(
    handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]
) -> None:
    """Write one JSON response, matching the handler's request protocol version."""
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)
