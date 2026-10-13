import logging
from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .parsing import Mail, parse_message

log = logging.getLogger(__name__)
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
BATCH_SIZE = 100
RETRIES = 5  # googleapiclient retries 429/5xx errors with exponential backoff


class HistoryExpired(Exception):
    """Gmail no longer accepts the stored history ID."""


def load_credentials(token_path: str) -> Credentials:
    """Loads the OAuth token and refreshes it if needed.

    A refreshed token is written back to ``token_path``.

    Args:
        token_path: Path to the token file created by the ``auth`` command.

    Returns:
        Valid credentials.
    """
    path = Path(token_path)
    creds = Credentials.from_authorized_user_file(str(path), SCOPES)
    if not creds.valid:
        creds.refresh(Request())
        path.write_text(creds.to_json(), encoding="utf-8")
    return creds


class GmailClient:
    """Read-only access to the Gmail API."""

    def __init__(self, service):
        self._svc = service.users()

    @classmethod
    def from_token(cls, token_path: str) -> "GmailClient":
        """Builds a client from the token file."""
        creds = load_credentials(token_path)
        return cls(build("gmail", "v1", credentials=creds, cache_discovery=False))

    def current_history_id(self) -> str:
        """Returns the current history ID of the mailbox."""
        return self._svc.getProfile(userId="me").execute(num_retries=RETRIES)["historyId"]

    def new_message_ids(self, start_history_id: str) -> list[str]:
        """Lists IDs of mails added since a history ID.

        Args:
            start_history_id: The history ID to start from.

        Returns:
            Message IDs without duplicates, in the order Gmail returned them.

        Raises:
            HistoryExpired: If Gmail no longer knows ``start_history_id``.
        """
        ids: dict[str, None] = {}
        token = None
        while True:
            try:
                resp = self._svc.history().list(
                    userId="me",
                    startHistoryId=start_history_id,
                    historyTypes=["messageAdded"],
                    pageToken=token,
                ).execute(num_retries=RETRIES)
            except HttpError as e:
                if e.resp.status == 404:
                    raise HistoryExpired() from e
                raise
            for entry in resp.get("history", []):
                for added in entry.get("messagesAdded", []):
                    ids[added["message"]["id"]] = None
            token = resp.get("nextPageToken")
            if not token:
                return list(ids)

    def message_ids_after(self, since: datetime) -> list[str]:
        """Lists IDs of all mails received after ``since``, excluding spam and trash."""
        ids: list[str] = []
        token = None
        query = f"after:{int(since.timestamp())}"
        while True:
            resp = self._svc.messages().list(
                userId="me", q=query, pageToken=token, includeSpamTrash=False
            ).execute(num_retries=RETRIES)
            ids.extend(m["id"] for m in resp.get("messages", []))
            token = resp.get("nextPageToken")
            if not token:
                return ids

    def get_message(self, message_id: str) -> dict | None:
        """Fetches one full message. Returns None if it was deleted in the meantime."""
        try:
            return self._svc.messages().get(
                userId="me", id=message_id, format="full"
            ).execute(num_retries=RETRIES)
        except HttpError as e:
            if e.resp.status == 404:
                return None
            raise

    def start_cursor(self) -> str:
        """Returns the cursor to start from: the current history ID."""
        return self.current_history_id()

    def fetch_since(
        self,
        cursor: str,
        fallback_since: datetime,
        is_known: Callable[[list[str]], set[str]],
    ) -> Iterator[tuple[list[Mail], str | None]]:
        """Yields the mails added since the cursor, in batches.

        Batches carry no cursor. The last item is an empty batch with the new history
        ID, so the cursor moves only after all mails were handed out.

        Args:
            cursor: The stored history ID.
            fallback_since: Where to restart if Gmail no longer knows the cursor.
            is_known: Tells which of the given mail IDs are already stored.
        """
        # Read this before fetching. Mails that arrive meanwhile are picked up by the next run.
        new_history_id = self.current_history_id()
        try:
            ids = self.new_message_ids(cursor)
        except HistoryExpired:
            log.warning("History ID expired, loading mails since %s", fallback_since)
            ids = self.message_ids_after(fallback_since)
        for start in range(0, len(ids), BATCH_SIZE):
            chunk = ids[start:start + BATCH_SIZE]
            known = is_known(chunk)
            mails = []
            for message_id in chunk:
                if message_id in known:
                    continue
                raw = self.get_message(message_id)
                if raw is None:  # deleted in the meantime
                    continue
                mails.append(parse_message(raw))
            if mails:
                yield mails, None
        yield [], new_history_id
