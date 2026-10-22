"""Localhost endpoint the Chrome extension posts to. Bound to 127.0.0.1 only."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Optional

from .policy import HANDLING, NATIVE, PageReport

ALLOWED_STATES = (HANDLING, NATIVE)
MAX_BODY_BYTES = 4096


class HeartbeatStore:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._report: Optional[PageReport] = None

    def record(self, state: str) -> None:
        with self._lock:
            self._report = PageReport(state=state, received_at=self._clock())

    def latest(self) -> Optional[PageReport]:
        with self._lock:
            return self._report

    def status(self) -> dict:
        with self._lock:
            if self._report is None:
                return {"state": None, "age_seconds": None}
            age = self._clock() - self._report.received_at
            return {"state": self._report.state, "age_seconds": round(age, 3)}


def _handler_for(store: HeartbeatStore) -> type:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def _respond(self, status: int) -> None:
            self.send_response(status)
            origin = self.headers.get("Origin", "")
            if origin.startswith("chrome-extension://"):
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_OPTIONS(self) -> None:
            self._respond(204)

        def do_GET(self) -> None:
            if self.path != "/status":
                self._respond(404)
                return
            body = json.dumps(store.status()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            if self.path != "/heartbeat":
                self._respond(404)
                return
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY_BYTES:
                self._respond(413)
                return
            try:
                body = json.loads(self.rfile.read(length) or b"null")
            except json.JSONDecodeError:
                self._respond(400)
                return
            state = body.get("state") if isinstance(body, dict) else None
            if state not in ALLOWED_STATES:
                self._respond(400)
                return
            store.record(state)
            self._respond(204)

    return Handler


class HeartbeatServer:
    def __init__(self, port: int, store: HeartbeatStore) -> None:
        self._server = ThreadingHTTPServer(("127.0.0.1", port), _handler_for(store))
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
