import os

import pytest

from mail_informer import db
from mail_informer.gmail import HistoryExpired
from mail_informer.sync import run_sync

DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL nicht gesetzt")


class FakeGmail:
    def __init__(self):
        self.history_id = "100"
        self.new_ids: list[str] = []
        self.expired = False
        self.messages: dict[str, dict] = {}
        self.after_ids: list[str] = []
        self.fetched: list[str] = []

    def current_history_id(self):
        return self.history_id

    def new_message_ids(self, start):
        if self.expired:
            raise HistoryExpired()
        return list(self.new_ids)

    def message_ids_after(self, since):
        return list(self.after_ids)

    def get_message(self, message_id):
        self.fetched.append(message_id)
        return self.messages.get(message_id)


def raw(message_id, body="Text"):
    import base64
    return {
        "id": message_id, "threadId": "t", "internalDate": "1700000000000",
        "labelIds": ["INBOX"], "snippet": "s",
        "payload": {
            "mimeType": "text/plain", "filename": "",
            "headers": [{"name": "Subject", "value": f"Betreff {message_id}"}],
            "body": {"data": base64.urlsafe_b64encode(body.encode()).decode()},
        },
    }


@pytest.fixture
def conn():
    c = db.connect(DATABASE_URL)
    c.execute("DROP TABLE IF EXISTS messages, sync_state, schema_migrations")
    db.migrate(c)
    yield c
    c.close()


def count(conn):
    return conn.execute("SELECT count(*) FROM messages").fetchone()[0]


def test_first_run_initializes_without_import(conn):
    gmail = FakeGmail()
    gmail.new_ids = ["a"]
    assert run_sync(conn, gmail) == 0
    assert count(conn) == 0
    assert db.get_sync_state(conn)[0] == "100"
    assert gmail.fetched == []


def test_delta_stores_mails_and_advances_state(conn):
    gmail = FakeGmail()
    run_sync(conn, gmail)
    gmail.history_id = "200"
    gmail.new_ids = ["a", "b", "c"]
    gmail.messages = {i: raw(i) for i in "abc"}
    assert run_sync(conn, gmail) == 3
    assert count(conn) == 3
    assert db.get_sync_state(conn)[0] == "200"
    status = conn.execute("SELECT DISTINCT analysis_status FROM messages").fetchall()
    assert status == [("pending",)]


def test_no_new_mails(conn):
    gmail = FakeGmail()
    run_sync(conn, gmail)
    gmail.history_id = "150"
    assert run_sync(conn, gmail) == 0
    assert db.get_sync_state(conn)[0] == "150"


def test_idempotent_and_skips_known(conn):
    gmail = FakeGmail()
    run_sync(conn, gmail)
    gmail.new_ids = ["a"]
    gmail.messages = {"a": raw("a")}
    run_sync(conn, gmail)
    gmail.fetched.clear()
    run_sync(conn, gmail)
    assert count(conn) == 1
    assert gmail.fetched == []


def test_deleted_message_skipped(conn):
    gmail = FakeGmail()
    run_sync(conn, gmail)
    gmail.new_ids = ["a", "gone"]
    gmail.messages = {"a": raw("a")}
    assert run_sync(conn, gmail) == 1


def test_failure_keeps_old_sync_state(conn):
    gmail = FakeGmail()
    run_sync(conn, gmail)
    gmail.history_id = "200"
    gmail.new_ids = ["a", "b"]
    gmail.messages = {"a": raw("a"), "b": raw("b")}

    def boom(message_id):
        if message_id == "b":
            raise RuntimeError("kaputt")
        return gmail.messages[message_id]

    gmail.get_message = boom
    with pytest.raises(RuntimeError):
        run_sync(conn, gmail)
    assert db.get_sync_state(conn)[0] == "100"
    assert count(conn) == 0


def test_expired_history_falls_back_to_date_query(conn):
    gmail = FakeGmail()
    run_sync(conn, gmail)
    gmail.expired = True
    gmail.history_id = "900"
    gmail.after_ids = ["x", "y"]
    gmail.messages = {"x": raw("x"), "y": raw("y")}
    assert run_sync(conn, gmail) == 2
    assert db.get_sync_state(conn)[0] == "900"


def test_advisory_lock_is_exclusive(conn):
    other = db.connect(DATABASE_URL)
    try:
        assert db.try_lock(conn)
        assert not db.try_lock(other)
    finally:
        other.close()
