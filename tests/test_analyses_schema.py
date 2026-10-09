import psycopg
import pytest

from mail_informer import db
from mail_informer.parsing import Mail
from datetime import datetime, timezone


def add_mail(conn, gmail_id="m1"):
    db.insert_mails(conn, [Mail(
        gmail_id=gmail_id, thread_id="t",
        internal_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        from_addr="a@example.org", to_addrs="b@example.org", subject="S",
        body_text="Text",
    )])


def insert(conn, gmail_id="m1", version="v1", status="done", category="other",
           importance="normal", summary="", reason="r", attempts=1):
    conn.execute(
        """INSERT INTO analyses
             (gmail_id, prompt_version, status, category, importance, summary, reason,
              model, attempts)
           VALUES (%s, %s, %s, %s, %s, %s, %s, 'test-model', %s)""",
        (gmail_id, version, status, category, importance, summary, reason, attempts),
    )


def test_result_for_unknown_mail_is_rejected(conn):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        insert(conn, gmail_id="does-not-exist")


def test_same_mail_and_prompt_version_cannot_exist_twice(conn):
    add_mail(conn)
    insert(conn)
    with pytest.raises(psycopg.errors.UniqueViolation):
        insert(conn)


def test_new_prompt_version_adds_a_second_result(conn):
    add_mail(conn)
    insert(conn, version="v1")
    insert(conn, version="v2", importance="important")
    rows = conn.execute("SELECT prompt_version FROM analyses ORDER BY 1").fetchall()
    assert rows == [("v1",), ("v2",)]


def test_done_result_needs_category_and_importance(conn):
    add_mail(conn)
    with pytest.raises(psycopg.errors.CheckViolation):
        insert(conn, status="done", category=None, importance="normal")
    with pytest.raises(psycopg.errors.CheckViolation):
        insert(conn, status="done", category="other", importance=None)


@pytest.mark.parametrize("status", ["failed", "pending"])
def test_only_done_results_have_category_and_importance(conn, status):
    add_mail(conn)
    with pytest.raises(psycopg.errors.CheckViolation):
        insert(conn, status=status, category="other", importance="normal")
    insert(conn, status=status, category=None, importance=None)


def test_unknown_status_and_importance_are_rejected(conn):
    add_mail(conn)
    with pytest.raises(psycopg.errors.CheckViolation):
        insert(conn, status="maybe", category=None, importance=None)
    with pytest.raises(psycopg.errors.CheckViolation):
        insert(conn, importance="critical")


def test_summary_defaults_to_empty_text(conn):
    add_mail(conn)
    conn.execute(
        "INSERT INTO analyses (gmail_id, prompt_version, status, model) "
        "VALUES ('m1', 'v1', 'pending', 'test-model')"
    )
    assert conn.execute("SELECT summary, reason, attempts FROM analyses").fetchone() == ("", "", 0)


def test_analyzer_state_is_a_single_row_table(conn):
    conn.execute("INSERT INTO analyzer_state (id, last_ok_at) VALUES (1, now())")
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("INSERT INTO analyzer_state (id, last_ok_at) VALUES (2, now())")


def test_migrating_a_database_with_old_mails_keeps_them_unchanged(conn):
    # Rebuild the state of the running system: only migration 001 applied, mails present.
    conn.execute("DROP TABLE IF EXISTS analyses, analyzer_state, messages, sync_state, schema_migrations")
    first = db.resources.files("mail_informer").joinpath("migrations/001_init.sql")
    conn.execute("CREATE TABLE schema_migrations (name text PRIMARY KEY)")
    conn.execute(first.read_text(encoding="utf-8"))
    conn.execute("INSERT INTO schema_migrations VALUES ('001_init.sql')")
    conn.execute(
        """INSERT INTO messages (gmail_id, thread_id, internal_date, subject, body_text)
           VALUES ('old1', 't', '2026-01-01', 'Betreff', 'Text'), ('old2', 't', '2026-01-02', 'B2', 'T2')"""
    )

    db.migrate(conn)

    rows = conn.execute(
        "SELECT gmail_id, thread_id, subject, body_text, is_bulk FROM messages ORDER BY gmail_id"
    ).fetchall()
    assert rows == [("old1", "t", "Betreff", "Text", None), ("old2", "t", "B2", "T2", None)]
    columns = {r[0] for r in conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'messages'")}
    assert "analysis_status" not in columns
    assert conn.execute("SELECT count(*) FROM analyses").fetchone()[0] == 0
