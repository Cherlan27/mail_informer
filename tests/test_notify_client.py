import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from mail_informer.notify.client import HaWebhookClient, NotifierUnavailable

SECRET = "very-secret-id"
MESSAGE = {"kind": "mail", "category": "work", "importance": "urgent",
           "sender": "Anna", "summary": "Kurz."}


class FakeHomeAssistant:
    """A tiny local HTTP server that plays the role of the Home Assistant webhook."""

    def __init__(self, status=200, delay=0.0):
        self.status, self.delay = status, delay
        self.requests: list[dict] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                outer.requests.append({
                    "path": self.path, "type": self.headers["Content-Type"],
                    "json": json.loads(body)})
                time.sleep(outer.delay)
                self.send_response(outer.status)
                self.end_headers()

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}/api/webhook/{SECRET}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def ha():
    servers = []

    def make(**kwargs):
        s = FakeHomeAssistant(**kwargs)
        servers.append(s)
        return s

    yield make
    for s in servers:
        s.close()


def test_valid_post_sends_the_message_as_json(ha):
    server = ha()
    HaWebhookClient(server.url).send(MESSAGE)
    assert server.requests == [{
        "path": f"/api/webhook/{SECRET}", "type": "application/json", "json": MESSAGE}]


def test_error_status_raises_unavailable_without_the_address(ha):
    server = ha(status=500)
    with pytest.raises(NotifierUnavailable) as error:
        HaWebhookClient(server.url).send(MESSAGE)
    assert SECRET not in str(error.value)
    assert "500" in str(error.value)


def test_connection_refused_raises_unavailable_without_the_address():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    with pytest.raises(NotifierUnavailable) as error:
        HaWebhookClient(f"http://127.0.0.1:{port}/api/webhook/{SECRET}").send(MESSAGE)
    assert SECRET not in str(error.value)


def test_timeout_raises_unavailable_without_the_address(ha):
    server = ha(delay=1.0)
    with pytest.raises(NotifierUnavailable) as error:
        HaWebhookClient(server.url, timeout=0.2).send(MESSAGE)
    assert SECRET not in str(error.value)
