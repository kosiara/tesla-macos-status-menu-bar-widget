"""Local HTTP server to handle OAuth callback for teslabar:// URL scheme."""

import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)

_callback_result: dict | None = None
_server: HTTPServer | None = None


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        global _callback_result
        logger.info("OAuth: path received: " + self.path)
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        code = params.get("code", [None])[0]
        state = params.get("state", [None])[0]
        error = params.get("error", [None])[0]

        logger.info("OAuth: code=%s, state=%s, error=%s", code, state, error)

        # Ignore unrelated requests (e.g. /favicon.ico) — don't overwrite result
        if not code and not error and parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return

        if error:
            _callback_result = {"error": error}
        elif code:
            _callback_result = {"code": code, "state": state}
        elif _callback_result is None:
            _callback_result = {"error": "No code received"}

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(
            b"<html><body><h2>Authentication successful!</h2>"
            b"<p>You can close this window and return to TeslaBar.</p>"
            b"</body></html>"
        )

    def log_message(self, format: str, *args: object) -> None:
        logger.debug(format, *args)


def start_callback_server(port: int = 8457) -> None:
    global _server, _callback_result
    _callback_result = None
    _server = HTTPServer(("127.0.0.1", port), OAuthCallbackHandler)
    thread = threading.Thread(target=_server.serve_forever, daemon=True)
    thread.start()
    logger.info("OAuth callback server started on port %d", port)


def stop_callback_server() -> None:
    global _server
    logger.info("OAuth callback server shutting down....")
    if _server:
        _server.shutdown()
        _server = None


def get_callback_result() -> dict | None:
    return _callback_result


def get_local_redirect_uri(port: int = 8457) -> str:
    return f"http://localhost:{port}/callback"
