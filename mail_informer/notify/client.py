"""Client for the Home Assistant webhook. Uses only the standard library."""

import json
import urllib.error
import urllib.request
from typing import Protocol


class NotifierUnavailable(Exception):
    """Home Assistant cannot be reached or answers with an error.

    The message never contains the webhook address, because the address holds a secret.
    """


class Notifier(Protocol):
    """What the notifier pass needs to send a message."""

    def send(self, message: dict) -> None:
        """Sends one message.

        Raises:
            NotifierUnavailable: If the message could not be delivered.
        """
        ...


class HaWebhookClient:
    """Posts messages as JSON to a Home Assistant webhook."""

    def __init__(self, url: str, timeout: float = 20.0):
        """Creates a client.

        Args:
            url: Full webhook address, including the secret id.
            timeout: Seconds to wait for the answer.
        """
        self._url = url
        self._timeout = timeout

    def send(self, message: dict) -> None:
        """Posts one message.

        Raises:
            NotifierUnavailable: If the server cannot be reached, times out, or answers
                with an error status.
        """
        request = urllib.request.Request(
            self._url, data=json.dumps(message).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout):
                pass
        except urllib.error.HTTPError as e:
            raise NotifierUnavailable(f"Home Assistant answered with status {e.code}") from None
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            # str(e) of a URLError holds only the reason, not the address.
            raise NotifierUnavailable(f"Home Assistant is not reachable: {e}") from None
