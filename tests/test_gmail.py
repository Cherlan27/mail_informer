from datetime import datetime, timezone

import httplib2
import pytest
from googleapiclient.errors import HttpError

from mail_informer.gmail import GmailClient, HistoryExpired


def http_error(status):
    return HttpError(httplib2.Response({"status": status}), b"{}")


class Call:
    def __init__(self, result):
        self.result = result

    def execute(self, num_retries=0):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class Resource:
    """Returns the next prepared answer on each call and records the arguments."""

    def __init__(self, *results):
        self.results = list(results)
        self.calls = []

    def _next(self, **kwargs):
        self.calls.append(kwargs)
        return Call(self.results.pop(0))

    list = get = _next


class Users:
    def __init__(self, history=None, messages=None):
        self._history, self._messages = history, messages

    def users(self):
        return self

    def history(self):
        return self._history

    def messages(self):
        return self._messages


def client(history=None, messages=None):
    return GmailClient(Users(history, messages))


def test_new_message_ids_paginates_and_deduplicates():
    history = Resource(
        {"history": [{"messagesAdded": [{"message": {"id": "a"}}, {"message": {"id": "b"}}]}],
         "nextPageToken": "p2"},
        {"history": [{"messagesAdded": [{"message": {"id": "a"}}, {"message": {"id": "c"}}]}]},
    )
    assert client(history=history).new_message_ids("1") == ["a", "b", "c"]
    assert history.calls[1]["pageToken"] == "p2"


def test_new_message_ids_empty():
    assert client(history=Resource({})).new_message_ids("1") == []


def test_expired_history_raises_history_expired():
    with pytest.raises(HistoryExpired):
        client(history=Resource(http_error(404))).new_message_ids("1")


def test_other_history_errors_propagate():
    with pytest.raises(HttpError):
        client(history=Resource(http_error(500))).new_message_ids("1")


def test_message_ids_after_uses_epoch_query_and_paginates():
    messages = Resource(
        {"messages": [{"id": "a"}], "nextPageToken": "p2"},
        {"messages": [{"id": "b"}]},
    )
    since = datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert client(messages=messages).message_ids_after(since) == ["a", "b"]
    assert messages.calls[0]["q"] == f"after:{int(since.timestamp())}"


def test_get_message_returns_none_when_deleted():
    assert client(messages=Resource(http_error(404))).get_message("x") is None


def test_get_message_returns_payload():
    assert client(messages=Resource({"id": "x"})).get_message("x") == {"id": "x"}


# --- the MailSource methods (start_cursor, fetch_since) ---

import base64

from mail_informer import gmail as gmail_module


def raw_message(message_id, body="Text"):
    return {
        "id": message_id, "threadId": "t", "internalDate": "1700000000000",
        "labelIds": ["INBOX"], "snippet": "s",
        "payload": {
            "mimeType": "text/plain", "filename": "",
            "headers": [{"name": "Subject", "value": f"Betreff {message_id}"}],
            "body": {"data": base64.urlsafe_b64encode(body.encode()).decode()},
        },
    }


class FakeApi:
    """Replaces the four low-level methods of the client."""

    def __init__(self):
        self.history_id = "100"
        self.new_ids: list[str] = []
        self.expired = False
        self.after_ids: list[str] = []
        self.messages: dict[str, dict] = {}
        self.fetched: list[str] = []
        self.after_asked: list[datetime] = []

    def install(self, c: GmailClient) -> GmailClient:
        c.current_history_id = lambda: self.history_id

        def new_message_ids(start):
            if self.expired:
                raise HistoryExpired()
            return list(self.new_ids)

        def message_ids_after(since):
            self.after_asked.append(since)
            return list(self.after_ids)

        def get_message(message_id):
            self.fetched.append(message_id)
            return self.messages.get(message_id)

        c.new_message_ids = new_message_ids
        c.message_ids_after = message_ids_after
        c.get_message = get_message
        return c


SINCE = datetime(2026, 10, 1, tzinfo=timezone.utc)


def fetch(api: FakeApi, known=lambda ids: set()):
    c = api.install(client())
    return list(c.fetch_since("100", SINCE, known))


def test_start_cursor_is_the_current_history_id():
    api = FakeApi()
    api.history_id = "777"
    assert api.install(client()).start_cursor() == "777"


def test_fetch_since_returns_parsed_mails_and_the_new_history_id_last():
    api = FakeApi()
    api.history_id = "200"
    api.new_ids = ["a", "b"]
    api.messages = {"a": raw_message("a"), "b": raw_message("b")}
    batches = fetch(api)
    assert [m.gmail_id for m in batches[0][0]] == ["a", "b"]
    assert batches[0][1] is None  # the history ID moves only after all batches
    assert batches[-1] == ([], "200")


def test_fetch_since_without_news_only_moves_the_cursor():
    api = FakeApi()
    api.history_id = "150"
    assert fetch(api) == [([], "150")]


def test_fetch_since_skips_known_mails_without_fetching_them():
    api = FakeApi()
    api.new_ids = ["a", "b"]
    api.messages = {"a": raw_message("a"), "b": raw_message("b")}
    batches = fetch(api, known=lambda ids: {"a"})
    assert [m.gmail_id for m in batches[0][0]] == ["b"]
    assert api.fetched == ["b"]


def test_fetch_since_skips_deleted_mails():
    api = FakeApi()
    api.new_ids = ["a", "gone"]
    api.messages = {"a": raw_message("a")}
    assert [m.gmail_id for m in fetch(api)[0][0]] == ["a"]


def test_fetch_since_uses_the_date_query_when_history_expired():
    api = FakeApi()
    api.expired = True
    api.history_id = "900"
    api.after_ids = ["x", "y"]
    api.messages = {"x": raw_message("x"), "y": raw_message("y")}
    batches = fetch(api)
    assert api.after_asked == [SINCE]
    assert [m.gmail_id for m in batches[0][0]] == ["x", "y"]
    assert batches[-1][1] == "900"


def test_fetch_since_works_in_batches(monkeypatch):
    monkeypatch.setattr(gmail_module, "BATCH_SIZE", 2)
    api = FakeApi()
    api.new_ids = ["a", "b", "c", "d", "e"]
    api.messages = {i: raw_message(i) for i in api.new_ids}
    batches = fetch(api)
    assert [len(b[0]) for b in batches] == [2, 2, 1, 0]
