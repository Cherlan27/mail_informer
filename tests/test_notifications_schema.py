from datetime import datetime, timezone

import psycopg
import pytest

from mail_informer import db
from mail_informer.parsing import Mail


def add_mail(conn, gmail_id="m1"):
    db.insert_mails(conn, [Mail(
        gmail_id=gmail_id, thread_id="t",
        internal_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        from_addr="a@example.org", to_addrs="b@example.org", subject="S", body_text="Text",
    )])


def insert(conn, gmail_id="m1", status="sent", importance="urgent"):
    conn.execute(
        "INSERT INTO notifications (gmail_id, status, importance) VALUES (%s, %s, %s)",
        (gmail_id, status, importance),
    )


def test_notification_for_unknown_mail_is_rejected(conn):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        insert(conn, "missing")


def test_a_mail_can_be_recorded_only_once(conn):
    add_mail(conn)
    insert(conn)
    with pytest.raises(psycopg.errors.UniqueViolation):
        insert(conn, status="suppressed")


def test_unknown_status_is_rejected(conn):
    add_mail(conn)
    with pytest.raises(psycopg.errors.CheckViolation):
        insert(conn, status="queued")


def test_only_important_and_urgent_can_be_recorded(conn):
    add_mail(conn)
    with pytest.raises(psycopg.errors.CheckViolation):
        insert(conn, importance="normal")


def test_notifier_state_holds_one_row(conn):
    conn.execute("INSERT INTO notifier_state (id, start_at) VALUES (1, now())")
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("INSERT INTO notifier_state (id, start_at) VALUES (2, now())")


def test_migrating_a_database_with_mails_and_results_keeps_them_unchanged(conn):
    # The state of the running system: migrations 001 to 003 applied, data present.
    conn.execute("DROP TABLE IF EXISTS notifications, notifier_state, schema_migrations")
    conn.execute("CREATE TABLE schema_migrations (name text PRIMARY KEY)")
    conn.execute("INSERT INTO schema_migrations VALUES ('001_init.sql'), ('002_bulk_flag.sql'), "
                 "('003_analyses.sql')")
    add_mail(conn, "old1")
    conn.execute(
        """INSERT INTO analyses (gmail_id, prompt_version, status, category, importance,
                                 summary, reason, model, attempts)
           VALUES ('old1', 'v1', 'done', 'work', 'important', 'Kurz.', 'r', 'm', 1)""")
    mails = conn.execute("SELECT * FROM messages ORDER BY gmail_id").fetchall()
    results = conn.execute("SELECT * FROM analyses ORDER BY id").fetchall()

    db.migrate(conn)

    assert conn.execute("SELECT * FROM messages ORDER BY gmail_id").fetchall() == mails
    assert conn.execute("SELECT * FROM analyses ORDER BY id").fetchall() == results
    assert conn.execute("SELECT count(*) FROM notifications").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM notifier_state").fetchone()[0] == 0
