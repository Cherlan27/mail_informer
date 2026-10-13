import os
from datetime import datetime, timedelta, timezone

import pytest

from mail_informer import db
from mail_informer.parsing import Mail
from mail_informer.sync import FALLBACK_BUFFER, run_sync

DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


def mail(key, account_ts=1_700_000_000):
    return Mail(
        gmail_id=key, thread_id="t",
        internal_date=datetime.fromtimestamp(account_ts, tz=timezone.utc),
        from_addr="a@example.org", to_addrs="b@example.org", subject=f"S {key}",
        labels=["INBOX"], snippet="s", body_text="Text",
    )


class FakeSource:
    """A source that hands out prepared batches of ``(mails, cursor)``."""

    def __init__(self, start="100"):
        self.start = start
        self.batches: list[tuple[list[Mail], str | None]] = []
        self.fail_after: int | None = None  # raise after this many batches
        self.calls: list[tuple[str, datetime | None]] = []
        self.known_seen: list[set[str]] = []
        self.probe: list[str] = []

    def start_cursor(self):
        return self.start

    def fetch_since(self, cursor, fallback_since, is_known):
        self.calls.append((cursor, fallback_since))
        self.known_seen.append(is_known(self.probe))
        for number, batch in enumerate(self.batches):
            if self.fail_after is not None and number >= self.fail_after:
                raise RuntimeError("kaputt")
            yield batch


def count(conn, account=None):
    if account:
        return conn.execute("SELECT count(*) FROM messages WHERE account = %s",
                            (account,)).fetchone()[0]
    return conn.execute("SELECT count(*) FROM messages").fetchone()[0]


def cursor_of(conn, account="gmail"):
    return db.get_cursor(conn, account)[0]


def test_first_run_stores_the_starting_point_and_imports_nothing(conn):
    source = FakeSource("100")
    source.batches = [([mail("a")], "200")]
    assert run_sync(conn, "gmail", source) == 0
    assert count(conn) == 0
    assert cursor_of(conn) == "100"
    assert source.calls == []


def test_registered_account_without_cursor_counts_as_first_run(conn):
    db.register_account(conn, "gmail")
    source = FakeSource("100")
    assert run_sync(conn, "gmail", source) == 0
    assert cursor_of(conn) == "100"
    assert source.calls == []


def test_later_run_stores_mails_for_the_account_and_moves_the_cursor(conn):
    source = FakeSource()
    run_sync(conn, "privat", source)
    source.batches = [([mail("privat:a"), mail("privat:b"), mail("privat:c")], "200")]
    assert run_sync(conn, "privat", source) == 3
    assert count(conn, "privat") == 3
    assert cursor_of(conn, "privat") == "200"
    assert source.calls[0][0] == "100"
    assert conn.execute("SELECT count(*) FROM analyses").fetchone()[0] == 0


def test_no_new_mails_keeps_everything(conn):
    source = FakeSource()
    run_sync(conn, "gmail", source)
    source.batches = [([], "150")]
    assert run_sync(conn, "gmail", source) == 0
    assert count(conn) == 0
    assert cursor_of(conn) == "150"


def test_a_successful_run_without_any_batch_still_counts_as_a_sync(conn):
    # An IMAP mailbox with no news hands out nothing. The run still succeeded.
    source = FakeSource()
    run_sync(conn, "privat", source)
    conn.execute("UPDATE sync_state SET updated_at = now() - interval '1 hour'")
    source.batches = []
    assert run_sync(conn, "privat", source) == 0
    cursor, updated_at = db.get_cursor(conn, "privat")
    assert cursor == "100"
    assert datetime.now(timezone.utc) - updated_at < timedelta(minutes=1)


def test_a_failed_run_does_not_refresh_the_sync_time(conn):
    source = FakeSource()
    run_sync(conn, "privat", source)
    conn.execute("UPDATE sync_state SET updated_at = now() - interval '1 hour'")
    source.batches = [([mail("a")], "200")]
    source.fail_after = 0
    with pytest.raises(RuntimeError):
        run_sync(conn, "privat", source)
    assert datetime.now(timezone.utc) - db.get_cursor(conn, "privat")[1] > timedelta(minutes=50)


def test_repeated_run_stores_no_duplicates(conn):
    source = FakeSource()
    run_sync(conn, "gmail", source)
    source.batches = [([mail("a")], "200")]
    run_sync(conn, "gmail", source)
    run_sync(conn, "gmail", source)
    assert count(conn) == 1


def test_source_can_ask_which_mails_are_known(conn):
    source = FakeSource()
    run_sync(conn, "gmail", source)
    source.batches = [([mail("a")], "200")]
    run_sync(conn, "gmail", source)
    source.probe = ["a", "b"]
    run_sync(conn, "gmail", source)
    assert source.known_seen[-1] == {"a"}


def test_failure_keeps_the_old_cursor(conn):
    source = FakeSource()
    run_sync(conn, "gmail", source)
    source.batches = [([mail("a"), mail("b")], None)]
    source.batches.append(([mail("c")], "200"))
    source.fail_after = 1
    with pytest.raises(RuntimeError):
        run_sync(conn, "gmail", source)
    assert cursor_of(conn) == "100"
    assert count(conn) == 2  # the first batch is stored, the next run skips it


def test_cursor_can_move_after_each_batch(conn):
    source = FakeSource()
    run_sync(conn, "privat", source)
    source.batches = [([mail("privat:a")], "1:5"), ([mail("privat:b")], "1:9")]
    source.fail_after = 1
    with pytest.raises(RuntimeError):
        run_sync(conn, "privat", source)
    assert cursor_of(conn, "privat") == "1:5"


def test_failure_in_one_account_does_not_move_another(conn):
    good, bad = FakeSource(), FakeSource()
    run_sync(conn, "a", good)
    run_sync(conn, "b", bad)
    good.batches = [([mail("a1")], "200")]
    bad.batches = [([mail("b1")], "200")]
    bad.fail_after = 0
    run_sync(conn, "a", good)
    with pytest.raises(RuntimeError):
        run_sync(conn, "b", bad)
    assert cursor_of(conn, "a") == "200"
    assert cursor_of(conn, "b") == "100"


def test_fallback_date_is_the_newest_mail_of_this_account_minus_a_day(conn):
    source = FakeSource()
    run_sync(conn, "a", source)
    run_sync(conn, "b", source)
    db.insert_mails(conn, [mail("a1", 1_700_000_000)], "a")
    db.insert_mails(conn, [mail("b1", 1_700_900_000)], "b")
    run_sync(conn, "a", source)
    fallback = source.calls[-1][1]
    assert fallback == datetime.fromtimestamp(1_700_000_000, tz=timezone.utc) - FALLBACK_BUFFER


def test_fallback_date_without_mails_is_the_last_sync_time_minus_a_day(conn):
    source = FakeSource()
    run_sync(conn, "a", source)
    run_sync(conn, "a", source)
    fallback = source.calls[-1][1]
    expected = datetime.now(timezone.utc) - FALLBACK_BUFFER
    assert abs(fallback - expected) < timedelta(minutes=1)


def test_advisory_lock_is_exclusive(conn):
    other = db.connect(DATABASE_URL)
    try:
        assert db.try_lock(conn)
        assert not db.try_lock(other)
    finally:
        other.close()
