import os
import threading

from datetime import datetime, timezone

from mail_informer import db
from mail_informer.parsing import Mail


def mail(gmail_id, body="Text", ts=1_700_000_000):
    return Mail(
        gmail_id=gmail_id, thread_id="t",
        internal_date=datetime.fromtimestamp(ts, tz=timezone.utc),
        from_addr="a@example.org", to_addrs="b@example.org", subject="S",
        labels=["INBOX"], snippet="s", body_text=body,
    )


def test_migrate_is_repeatable(conn):
    db.migrate(conn)
    names = [r[0] for r in conn.execute("SELECT name FROM schema_migrations")]
    assert names == sorted(names) and names[0] == "001_init.sql"
    assert len(names) == len(set(names))


def test_insert_ignores_duplicates_and_strips_nul(conn):
    db.insert_mails(conn, [mail("a", "x\x00y")])
    db.insert_mails(conn, [mail("a", "andere"), mail("b")])
    rows = dict(conn.execute("SELECT gmail_id, body_text FROM messages"))
    assert rows == {"a": "xy", "b": "Text"}


def test_existing_ids(conn):
    db.insert_mails(conn, [mail("a")])
    assert db.existing_ids(conn, ["a", "b"]) == {"a"}
    assert db.existing_ids(conn, []) == set()


def test_latest_mail_date(conn):
    assert db.latest_mail_date(conn) is None
    db.insert_mails(conn, [mail("a", ts=1_700_000_000), mail("b", ts=1_700_001_000)])
    assert db.latest_mail_date(conn).timestamp() == 1_700_001_000


def test_sync_state_roundtrip_and_last_sync_at(conn):
    assert db.get_sync_state(conn) is None
    assert db.last_sync_at(conn) is None
    db.set_sync_state(conn, "1")
    db.set_sync_state(conn, "2")
    assert db.get_sync_state(conn)[0] == "2"
    assert db.last_sync_at(conn) is not None


def test_unlock_releases_lock(conn):
    other = db.connect(os.environ["TEST_DATABASE_URL"])
    try:
        assert db.try_lock(conn)
        db.unlock(conn)
        assert db.try_lock(other)
    finally:
        other.close()


def _run_migrate_in_thread(url, done):
    def run():
        c = db.connect(url)
        try:
            db.migrate(c)
        finally:
            c.close()
            done.set()

    thread = threading.Thread(target=run)
    thread.start()
    return thread


def test_migrate_waits_while_another_connection_holds_the_migration_lock(conn):
    url = os.environ["TEST_DATABASE_URL"]
    other = db.connect(url)
    try:
        other.execute("SELECT pg_advisory_lock(%s)", (db.MIGRATION_LOCK_KEY,))
        done = threading.Event()
        thread = _run_migrate_in_thread(url, done)
        assert not done.wait(0.5)
        other.execute("SELECT pg_advisory_unlock(%s)", (db.MIGRATION_LOCK_KEY,))
        assert done.wait(10)
        thread.join()
    finally:
        other.close()


def test_concurrent_migrations_apply_each_file_once(conn):
    url = os.environ["TEST_DATABASE_URL"]
    conn.execute("DROP TABLE IF EXISTS notifications, notifier_state, analyses, analyzer_state, messages, sync_state, schema_migrations")
    errors = []

    def run():
        c = db.connect(url)
        try:
            db.migrate(c)
        except Exception as e:  # collected so the test can report it
            errors.append(e)
        finally:
            c.close()

    threads = [threading.Thread(target=run) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    names = [r[0] for r in conn.execute("SELECT name FROM schema_migrations ORDER BY name")]
    assert names == sorted(set(names))


def test_insert_stores_bulk_flag_true_false_and_unknown(conn):
    bulk = mail("bulk")
    bulk = Mail(**{**bulk.__dict__, "is_bulk": True})
    personal = Mail(**{**mail("personal").__dict__, "is_bulk": False})
    unknown = mail("unknown")
    db.insert_mails(conn, [bulk, personal, unknown])
    rows = dict(conn.execute("SELECT gmail_id, is_bulk FROM messages"))
    assert rows == {"bulk": True, "personal": False, "unknown": None}
