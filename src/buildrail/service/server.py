"""Buildrail's local HTTP service: a lightweight, localhost-only server that
exposes the same CoreEngine/ArtifactReader functionality the CLI already
uses, for a future local frontend to consume. No TLS, no authentication,
no multi-user concerns — this is not a cloud API or a remote server.

`run()` is a deliberate exception to the rest of the codebase's
Result-returning, one-shot `CoreEngine` methods: starting a server is a
long-running, blocking daemon command, not a single orchestration step,
so it prints its own status directly (mirroring how any other CLI dev
server — e.g. a local web server — reports readiness before blocking) and
returns a process exit code instead of a `Result`.
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from buildrail.service.routes import JsonBody, dispatch
from buildrail.service.transport import read_json_body, send_json_response

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8787


class BuildrailHTTPServer(ThreadingHTTPServer):
    """A ThreadingHTTPServer that carries the project root each request is answered against."""

    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[BaseHTTPRequestHandler],
        project_root: Path,
    ) -> None:
        super().__init__(server_address, handler_class)
        self.project_root = project_root


class _RequestHandler(BaseHTTPRequestHandler):
    """Delegates every request to `routes.dispatch`; owns no business logic itself."""

    server: BuildrailHTTPServer  # narrows the inherited `BaseServer` type for mypy

    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler's naming convention)
        self._handle(None)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        self._handle(read_json_body(raw))

    def _handle(self, body: JsonBody) -> None:
        status, payload = dispatch(self.command, self.path, body, self.server.project_root)
        send_json_response(self, status, payload)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass  # keep stdout limited to the CLI's own ready/shutdown lines


def create_server(
    project_root: Path, *, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT
) -> BuildrailHTTPServer:
    """Build (but do not start) a Buildrail HTTP server bound to `host`:`port`."""
    return BuildrailHTTPServer((host, port), _RequestHandler, project_root)


def run(project_root: Path, *, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> int:
    """Start the server and block until interrupted. Returns a process exit code."""
    try:
        server = create_server(project_root, host=host, port=port)
    except OSError as exc:
        print(f"Could not start the Buildrail service: {exc}")
        return 1

    print(f"Buildrail service listening on http://{host}:{port} (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down.")
    finally:
        server.server_close()
    return 0
