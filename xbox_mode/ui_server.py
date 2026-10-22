"""Serves the HTML UI and its current state on 127.0.0.1. The controller loop publishes the state."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict

UI_FILE = Path(__file__).parent / "ui" / "index.html"


class UiState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: Dict[str, Any] = {"mode": "none"}

    def publish(self, state: Dict[str, Any]) -> None:
        with self._lock:
            self._state = state

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return self._state


def _handler_for(state: UiState) -> type:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def _send(self, status: int, content_type: str, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            path = self.path.split("?")[0]
            if path == "/state":
                self._send(200, "application/json", json.dumps(state.snapshot()).encode("utf-8"))
            elif path in ("/", "/index.html"):
                self._send(200, "text/html; charset=utf-8", UI_FILE.read_bytes())
            else:
                self._send(404, "text/plain", b"not found")

    return Handler


class UiServer:
    def __init__(self, port: int, state: UiState) -> None:
        self._server = ThreadingHTTPServer(("127.0.0.1", port), _handler_for(state))
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
