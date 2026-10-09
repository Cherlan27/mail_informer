import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from mail_informer.analysis.model import ModelUnavailable, OllamaClient
from mail_informer.analysis.rules import InvalidAnswer

SCHEMA = {"type": "object", "properties": {"summary": {"type": "string"}}}
MESSAGES = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]


class FakeOllama:
    """A tiny local HTTP server that plays the role of Ollama."""

    def __init__(self, status=200, content='{"summary": "ok"}', delay=0.0):
        self.status, self.content, self.delay = status, content, delay
        self.requests: list[dict] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                outer.requests.append({"path": self.path, "json": json.loads(body)})
                time.sleep(outer.delay)
                payload = json.dumps({"message": {"role": "assistant", "content": outer.content}})
                self.send_response(outer.status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(payload.encode())

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def ollama():
    servers = []

    def make(**kwargs):
        s = FakeOllama(**kwargs)
        servers.append(s)
        return s

    yield make
    for s in servers:
        s.close()


def test_valid_answer_is_decoded(ollama):
    server = ollama(content='{"summary": "Hallo"}')
    client = OllamaClient(server.url, "test-model")
    assert client.chat_json(MESSAGES, SCHEMA) == {"summary": "Hallo"}


def test_request_is_constrained_and_deterministic(ollama):
    server = ollama()
    OllamaClient(server.url, "test-model").chat_json(MESSAGES, SCHEMA)
    sent = server.requests[0]
    assert sent["path"] == "/api/chat"
    body = sent["json"]
    assert body["model"] == "test-model"
    assert body["messages"] == MESSAGES
    assert body["stream"] is False
    assert body["format"] == SCHEMA
    assert body["options"]["temperature"] == 0
    assert "seed" in body["options"]
    assert "keep_alive" in body
    assert body["think"] is False
    assert "tools" not in body


def test_answer_that_is_not_json_is_an_invalid_answer(ollama):
    server = ollama(content="Sure! Here is your answer")
    with pytest.raises(InvalidAnswer):
        OllamaClient(server.url, "m").chat_json(MESSAGES, SCHEMA)


def test_http_error_means_model_unavailable(ollama):
    server = ollama(status=500)
    with pytest.raises(ModelUnavailable):
        OllamaClient(server.url, "m").chat_json(MESSAGES, SCHEMA)


def test_unknown_model_means_model_unavailable(ollama):
    server = ollama(status=404)
    with pytest.raises(ModelUnavailable):
        OllamaClient(server.url, "m").chat_json(MESSAGES, SCHEMA)


def test_connection_refused_means_model_unavailable():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    with pytest.raises(ModelUnavailable):
        OllamaClient(f"http://127.0.0.1:{port}", "m").chat_json(MESSAGES, SCHEMA)


def test_timeout_means_model_unavailable(ollama):
    server = ollama(delay=1.0)
    with pytest.raises(ModelUnavailable):
        OllamaClient(server.url, "m", timeout=0.2).chat_json(MESSAGES, SCHEMA)
