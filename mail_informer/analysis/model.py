"""Client for the local model server (Ollama). Uses only the standard library."""

import json
import urllib.error
import urllib.request
from typing import Protocol

from .rules import InvalidAnswer

SEED = 7
KEEP_ALIVE = "10m"


class ModelUnavailable(Exception):
    """The model server cannot be reached or does not answer correctly.

    This is a problem of the server, not of one mail. It must not count as a
    failed attempt for any mail.
    """


class ModelClient(Protocol):
    """What the analyzer needs from a model."""

    def chat_json(self, messages: list[dict], schema: dict) -> object:
        """Sends chat messages and returns the answer decoded as JSON."""
        ...


class OllamaClient:
    """Talks to Ollama over HTTP and forces the answer to follow a JSON schema."""

    def __init__(self, base_url: str, model: str, timeout: float = 120.0):
        """Creates a client.

        Args:
            base_url: Address of the model server, for example ``http://host:11434``.
            model: Name of the model to use.
            timeout: Seconds to wait for one answer.
        """
        self._url = base_url.rstrip("/") + "/api/chat"
        self._model = model
        self._timeout = timeout

    def chat_json(self, messages: list[dict], schema: dict) -> object:
        """Sends chat messages and returns the answer decoded as JSON.

        The request carries no tools, so the model can only answer with text.

        Args:
            messages: Chat messages with ``role`` and ``content``.
            schema: JSON schema that the answer must follow.

        Returns:
            The decoded JSON answer.

        Raises:
            ModelUnavailable: If the server cannot be reached, times out, or returns
                an error status.
            InvalidAnswer: If the answer is not valid JSON.
        """
        body = json.dumps({
            "model": self._model,
            "messages": messages,
            "stream": False,
            "format": schema,
            "think": False,
            "options": {"temperature": 0, "seed": SEED},
            "keep_alive": KEEP_ALIVE,
        }).encode("utf-8")
        request = urllib.request.Request(
            self._url, data=body, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                payload = json.load(response)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            raise ModelUnavailable(f"model server error: {e}") from e
        except json.JSONDecodeError as e:
            raise ModelUnavailable("model server sent an unreadable response") from e
        content = (payload.get("message") or {}).get("content") if isinstance(payload, dict) else None
        if not isinstance(content, str):
            raise ModelUnavailable("model server response has no message content")
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise InvalidAnswer("model answer is not valid JSON") from e
