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
