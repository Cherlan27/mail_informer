import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from mail_informer.analysis.model import ModelUnavailable, OpenAICompatibleClient
from mail_informer.analysis.rules import InvalidAnswer

SCHEMA = {"type": "object", "properties": {"summary": {"type": "string"}}}
MESSAGES = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]


def completion(content='{"summary": "ok"}', finish_reason="stop", refusal=None) -> dict:
    """Builds an answer in the chat completions format."""
    message = {"role": "assistant", "content": content}
    if refusal is not None:
        message = {"role": "assistant", "content": None, "refusal": refusal}
    return {"choices": [{"index": 0, "message": message, "finish_reason": finish_reason}]}


class FakeServer:
    """A tiny local HTTP server that plays the role of an OpenAI-compatible server."""

    def __init__(self, status=200, payload=None, raw=None, delay=0.0):
        self.status = status
        self.payload = completion() if payload is None else payload
        self.raw = raw
        self.delay = delay
        self.requests: list[dict] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                outer.requests.append({
                    "path": self.path,
                    "json": json.loads(body),
                    "authorization": self.headers.get("Authorization"),
                })
                time.sleep(outer.delay)
                data = outer.raw if outer.raw is not None else json.dumps(outer.payload).encode()
                self.send_response(outer.status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}/v1"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def server():
    servers = []

    def make(**kwargs):
        s = FakeServer(**kwargs)
        servers.append(s)
        return s

    yield make
    for s in servers:
        s.close()


def test_valid_answer_is_decoded(server):
    s = server(payload=completion('{"summary": "Hallo"}'))
    client = OpenAICompatibleClient(s.url, "test-model")
    assert client.chat_json(MESSAGES, SCHEMA) == {"summary": "Hallo"}


def test_request_asks_for_the_schema_and_is_deterministic(server):
    s = server()
    OpenAICompatibleClient(s.url, "test-model").chat_json(MESSAGES, SCHEMA)
    sent = s.requests[0]
    assert sent["path"] == "/v1/chat/completions"
    body = sent["json"]
    assert body["model"] == "test-model"
    assert body["messages"] == MESSAGES
    assert body["temperature"] == 0
    assert "seed" in body
    assert body["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "answer", "strict": True, "schema": SCHEMA},
    }
    assert "tools" not in body
    assert "stream" not in body


def test_reasoning_effort_is_sent_when_set(server):
    s = server()
    OpenAICompatibleClient(s.url, "m", reasoning_effort="none").chat_json(MESSAGES, SCHEMA)
    assert s.requests[0]["json"]["reasoning_effort"] == "none"


def test_no_reasoning_field_when_effort_is_empty(server):
    s = server()
    OpenAICompatibleClient(s.url, "m").chat_json(MESSAGES, SCHEMA)
    assert "reasoning_effort" not in s.requests[0]["json"]
    assert not any("reason" in key for key in s.requests[0]["json"])


def test_trailing_slash_in_the_address_is_fine(server):
    s = server()
    OpenAICompatibleClient(s.url + "/", "m").chat_json(MESSAGES, SCHEMA)
    assert s.requests[0]["path"] == "/v1/chat/completions"


def test_key_is_sent_as_bearer_token(server):
    s = server()
    OpenAICompatibleClient(s.url, "m", api_key="sk-abc").chat_json(MESSAGES, SCHEMA)
    assert s.requests[0]["authorization"] == "Bearer sk-abc"


def test_no_authorization_header_without_a_key(server):
    s = server()
    OpenAICompatibleClient(s.url, "m").chat_json(MESSAGES, SCHEMA)
    assert s.requests[0]["authorization"] is None


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429, 500, 503])
def test_http_error_means_model_unavailable(server, status):
    s = server(status=status, payload={"error": {"message": "echo: u", "type": "bad_thing"}})
    with pytest.raises(ModelUnavailable) as error:
        OpenAICompatibleClient(s.url, "m", api_key="sk-secret").chat_json(MESSAGES, SCHEMA)
    text = str(error.value)
    assert str(status) in text
    assert "bad_thing" in text
    assert "sk-secret" not in text
    assert "echo: u" not in text


def test_http_error_with_unreadable_body_still_means_model_unavailable(server):
    s = server(status=502, raw=b"<html>Bad gateway</html>")
    with pytest.raises(ModelUnavailable, match="502"):
        OpenAICompatibleClient(s.url, "m").chat_json(MESSAGES, SCHEMA)


@pytest.mark.parametrize("payload", [{}, {"choices": []}, {"choices": [{}]}, [], {"choices": "x"}])
def test_answer_without_a_message_means_model_unavailable(server, payload):
    s = server(payload=payload)
    with pytest.raises(ModelUnavailable):
        OpenAICompatibleClient(s.url, "m").chat_json(MESSAGES, SCHEMA)


def test_body_that_is_not_json_means_model_unavailable(server):
    s = server(raw=b"hello")
    with pytest.raises(ModelUnavailable):
        OpenAICompatibleClient(s.url, "m").chat_json(MESSAGES, SCHEMA)


def test_refusal_is_an_invalid_answer(server):
    s = server(payload=completion(refusal="I cannot help with that"))
    with pytest.raises(InvalidAnswer):
        OpenAICompatibleClient(s.url, "m").chat_json(MESSAGES, SCHEMA)


@pytest.mark.parametrize("reason", ["length", "content_filter"])
def test_cut_off_answer_is_an_invalid_answer(server, reason):
    s = server(payload=completion('{"summary": "ha', finish_reason=reason))
    with pytest.raises(InvalidAnswer):
        OpenAICompatibleClient(s.url, "m").chat_json(MESSAGES, SCHEMA)


def test_answer_that_is_not_json_is_an_invalid_answer(server):
    s = server(payload=completion("Sure! Here is your answer"))
    with pytest.raises(InvalidAnswer):
        OpenAICompatibleClient(s.url, "m").chat_json(MESSAGES, SCHEMA)


def test_connection_refused_means_model_unavailable():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with pytest.raises(ModelUnavailable):
        OpenAICompatibleClient(f"http://127.0.0.1:{port}/v1", "m").chat_json(MESSAGES, SCHEMA)


def test_timeout_means_model_unavailable(server):
    s = server(delay=1.0)
    with pytest.raises(ModelUnavailable):
        OpenAICompatibleClient(s.url, "m", timeout=0.2).chat_json(MESSAGES, SCHEMA)
