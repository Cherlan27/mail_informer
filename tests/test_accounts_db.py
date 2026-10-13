from datetime import datetime, timedelta, timezone
from importlib import resources

import psycopg
import pytest

from mail_informer import db
from mail_informer.parsing import Mail

DROP = ("DROP TABLE IF EXISTS notifications, notifier_state, analyses, analyzer_state, "
        "messages, sync_state, schema_migrations")


def mail(gmail_id, ts=1_700_000_000):
    return Mail(
        gmail_id=gmail_id, thread_id="t",
        internal_date=datetime.fromtimestamp(ts, tz=timezone.utc),
        from_addr="a@example.org", to_addrs="b@example.org", subject="S", body_text="Text",
    )


def test_migration_keeps_existing_data_and_moves_it_to_the_gmail_account(conn):
    # The running system: migrations 001 to 004 applied, data present.
    conn.execute(DROP)
    conn.execute("CREATE TABLE schema_migrations (name text PRIMARY KEY)")
    folder = resources.files("mail_informer").joinpath("migrations")
    for name in ("001_init.sql", "002_bulk_flag.sql", "003_analyses.sql", "004_notifications.sql"):
        conn.execute(folder.joinpath(name).read_text(encoding="utf-8"))
        conn.execute("INSERT INTO schema_migrations VALUES (%s)", (name,))
    conn.execute("INSERT INTO messages (gmail_id, thread_id, internal_date, body_text) "
                 "VALUES ('old1', 't', now(), 'x')")
    conn.execute(
        """INSERT INTO analyses (gmail_id, prompt_version, status, category, importance,
                                 summary, reason, model, attempts)
           VALUES ('old1', 'v1', 'done', 'work', 'important', 'Kurz.', 'r', 'm', 1)""")
    conn.execute("INSERT INTO notifications (gmail_id, status, importance) "
                 "VALUES ('old1', 'sent', 'important')")
    conn.execute("INSERT INTO sync_state (id, history_id) VALUES (1, 'h-100')")
    analyses = conn.execute("SELECT * FROM analyses").fetchall()
    notifications = conn.execute("SELECT * FROM notifications").fetchall()

    db.migrate(conn)

    assert conn.execute("SELECT gmail_id, account FROM messages").fetchall() == [("old1", "gmail")]
    assert conn.execute("SELECT * FROM analyses").fetchall() == analyses
    assert conn.execute("SELECT * FROM notifications").fetchall() == notifications
    assert conn.execute("SELECT account, cursor FROM sync_state").fetchall() == [("gmail", "h-100")]


def test_a_mail_needs_an_account(conn):
    with pytest.raises(psycopg.errors.NotNullViolation):
        conn.execute("INSERT INTO messages (gmail_id, thread_id, internal_date) "
                     "VALUES ('x', 't', now())")


def test_insert_stores_the_account(conn):
    db.insert_mails(conn, [mail("privat:a")], "privat")
    assert conn.execute("SELECT account FROM messages").fetchone()[0] == "privat"


def test_register_account_creates_an_unstarted_row_once(conn):
    assert db.get_cursor(conn, "privat") is None
    db.register_account(conn, "privat")
    cursor, first = db.get_cursor(conn, "privat")
    assert cursor is None
    db.set_cursor(conn, "privat", "1:5")
    db.register_account(conn, "privat")  # must not reset the cursor
    assert db.get_cursor(conn, "privat")[0] == "1:5"
    assert first is not None


def test_set_cursor_moves_updated_at_and_only_for_its_account(conn):
    db.register_account(conn, "a")
    db.register_account(conn, "b")
    conn.execute("UPDATE sync_state SET updated_at = now() - interval '1 hour'")
    db.set_cursor(conn, "a", "x")
    a = db.get_cursor(conn, "a")
    b = db.get_cursor(conn, "b")
    assert a[0] == "x" and datetime.now(timezone.utc) - a[1] < timedelta(minutes=1)
    assert b[0] is None and datetime.now(timezone.utc) - b[1] > timedelta(minutes=30)


def test_latest_mail_date_is_per_account(conn):
    assert db.latest_mail_date(conn, "a") is None
    db.insert_mails(conn, [mail("a1", ts=1_700_000_000)], "a")
    db.insert_mails(conn, [mail("b1", ts=1_700_005_000)], "b")
    assert db.latest_mail_date(conn, "a").timestamp() == 1_700_000_000


def test_oldest_sync_at_is_the_oldest_of_the_given_accounts(conn):
    for name in ("a", "b", "removed"):
        db.register_account(conn, name)
    conn.execute("UPDATE sync_state SET updated_at = now() - interval '10 minutes' "
                 "WHERE account = 'a'")
    conn.execute("UPDATE sync_state SET updated_at = now() - interval '1 day' "
                 "WHERE account = 'removed'")
    oldest = db.oldest_sync_at(conn, ["a", "b"])
    assert timedelta(minutes=9) < datetime.now(timezone.utc) - oldest < timedelta(minutes=11)


def test_oldest_sync_at_is_none_when_an_account_has_no_row(conn):
    db.register_account(conn, "a")
    assert db.oldest_sync_at(conn, ["a", "never-registered"]) is None
    assert db.oldest_sync_at(conn, []) is None


def test_touch_sync_refreshes_the_time_but_not_the_cursor(conn):
    db.register_account(conn, "a")
    db.set_cursor(conn, "a", "x")
    conn.execute("UPDATE sync_state SET updated_at = now() - interval '1 hour'")
    db.touch_sync(conn, "a")
    cursor, updated_at = db.get_cursor(conn, "a")
    assert cursor == "x" and datetime.now(timezone.utc) - updated_at < timedelta(minutes=1)
