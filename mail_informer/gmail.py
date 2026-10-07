from datetime import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
RETRIES = 5  # googleapiclient wiederholt bei 429/5xx mit exponentiellem Backoff


class HistoryExpired(Exception):
    """Der gespeicherte historyId ist bei Gmail nicht mehr gültig."""


def load_credentials(token_path: str) -> Credentials:
    path = Path(token_path)
    creds = Credentials.from_authorized_user_file(str(path), SCOPES)
    if not creds.valid:
        creds.refresh(Request())
        path.write_text(creds.to_json(), encoding="utf-8")
    return creds


class GmailClient:
    def __init__(self, service):
        self._svc = service.users()

    @classmethod
    def from_token(cls, token_path: str) -> "GmailClient":
        creds = load_credentials(token_path)
        return cls(build("gmail", "v1", credentials=creds, cache_discovery=False))

    def current_history_id(self) -> str:
        return self._svc.getProfile(userId="me").execute(num_retries=RETRIES)["historyId"]

    def new_message_ids(self, start_history_id: str) -> list[str]:
        """IDs seit start_history_id hinzugekommener Mails (dedupliziert, in Reihenfolge)."""
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
        try:
            return self._svc.messages().get(
                userId="me", id=message_id, format="full"
            ).execute(num_retries=RETRIES)
        except HttpError as e:
            if e.resp.status == 404:
                return None
            raise
