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
    assert names == ["001_init.sql"]


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
    other = db.connect(conn.info.dsn)
    try:
        assert db.try_lock(conn)
        db.unlock(conn)
        assert db.try_lock(other)
    finally:
        other.close()
