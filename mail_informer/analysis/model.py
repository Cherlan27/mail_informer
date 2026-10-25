"""Client for an OpenAI-compatible model server. Uses only the standard library."""

import json
import urllib.error
import urllib.request
from typing import Protocol

from .rules import InvalidAnswer

SEED = 7
MAX_ERROR_BODY = 4096
# These stops mean the answer is incomplete or was blocked, even if it looks like JSON.
BAD_FINISH_REASONS = ("length", "content_filter")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuses every redirect, so the 3xx answer becomes an ``HTTPError``.

    urllib would resend the ``Authorization`` header to the new host, also from
    https to http, and a local server could pass the request on to a remote one.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


class ModelUnavailable(Exception):
    """The model server cannot be reached, rejects the request, or does not answer correctly.

    This is a problem of the server, not of one mail. It must not count as a
    failed attempt for any mail.
    """


class ModelClient(Protocol):
    """What the analyzer needs from a model."""

    def chat_json(self, messages: list[dict], schema: dict) -> object:
        """Sends chat messages and returns the answer decoded as JSON."""
        ...


class OpenAICompatibleClient:
    """Talks to a server that offers the OpenAI chat completions API.

    This covers cloud services, local servers such as vLLM, and Ollama through its
    ``/v1`` endpoint. The answer is forced to follow a JSON schema.
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "",
        reasoning_effort: str = "",
        timeout: float = 120.0,
    ):
        """Creates a client.

        Args:
            base_url: Address of the API, for example ``http://host:11434/v1``.
            model: Name of the model to use.
            api_key: Optional key, sent as a bearer token. It is never put in errors.
            reasoning_effort: Optional ``reasoning_effort`` value, for example ``none``.
                Empty means the field is not sent, because some servers reject it.
            timeout: Seconds to wait for one answer.
        """
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._model = model
        self._api_key = api_key
        self._reasoning_effort = reasoning_effort
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
            ModelUnavailable: If the server cannot be reached, times out, returns an
                error status (also for a wrong key or a rate limit), redirects, or
                sends a response without a message.
            InvalidAnswer: If the model refused, the answer was cut off, or the answer
                is not valid JSON.
        """
        request_body = {
            "model": self._model,
            "messages": messages,
            "temperature": 0,
            "seed": SEED,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "answer", "strict": True, "schema": schema},
            },
        }
        if self._reasoning_effort:
            request_body["reasoning_effort"] = self._reasoning_effort
        body = json.dumps(request_body).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        request = urllib.request.Request(self._url, data=body, headers=headers)
        try:
            with _OPENER.open(request, timeout=self._timeout) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as e:
            raise ModelUnavailable(_http_error_text(e)) from e
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            raise ModelUnavailable(f"model server error: {e}") from e
        except json.JSONDecodeError as e:
            raise ModelUnavailable("model server sent an unreadable response") from e
        return _decode_answer(payload)


def _http_error_text(error: urllib.error.HTTPError) -> str:
    """Describes an error status without echoing the body text of the server.

    A server may repeat parts of the request in its error message, and the request
    holds mail text. Only the short error type and code are kept.
    """
    text = f"model server answered HTTP {error.code}"
    try:
        detail = json.loads(error.read(MAX_ERROR_BODY)).get("error")
    except (ValueError, AttributeError, OSError):
        return text
    if isinstance(detail, dict):
        parts = [str(detail[k]) for k in ("type", "code") if isinstance(detail.get(k), (str, int))]
        if parts:
            text += f" ({', '.join(parts)})"
    return text


def _decode_answer(payload: object) -> object:
    """Takes the JSON answer out of a chat completions response."""
    choices = payload.get("choices") if isinstance(payload, dict) else None
    choice = choices[0] if isinstance(choices, list) and choices else None
    message = choice.get("message") if isinstance(choice, dict) else None
    if not isinstance(message, dict):
        raise ModelUnavailable("model server response has no message")
    if message.get("refusal"):
        raise InvalidAnswer("model refused to answer")
    if choice.get("finish_reason") in BAD_FINISH_REASONS:
        raise InvalidAnswer(f"model answer is incomplete ({choice['finish_reason']})")
    content = message.get("content")
    if not isinstance(content, str):
        raise ModelUnavailable("model server response has no message content")
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise InvalidAnswer("model answer is not valid JSON") from e
