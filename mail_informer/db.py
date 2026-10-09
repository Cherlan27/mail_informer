from datetime import datetime
from importlib import resources
from typing import NamedTuple

import psycopg

from .parsing import Mail


class PendingMail(NamedTuple):
    """The fields of an archived mail that the analyzer needs."""

    gmail_id: str
    from_addr: str | None
    subject: str | None
    body_text: str
    is_bulk: bool | None


LOCK_KEY = 726_001  # Advisory lock key that prevents parallel runs
MIGRATION_LOCK_KEY = 726_002  # Advisory lock key that serializes migrations
ANALYZER_LOCK_KEY = 726_003  # Advisory lock key that prevents parallel analyzer passes


def connect(database_url: str) -> psycopg.Connection:
    """Opens an autocommit connection to Postgres."""
    return psycopg.connect(database_url, autocommit=True)


def try_lock(conn: psycopg.Connection) -> bool:
    """Tries to take the run lock without waiting. Returns True if it got the lock."""
    return conn.execute("SELECT pg_try_advisory_lock(%s)", (LOCK_KEY,)).fetchone()[0]


def unlock(conn: psycopg.Connection) -> None:
    """Releases the run lock."""
    conn.execute("SELECT pg_advisory_unlock(%s)", (LOCK_KEY,))


def migrate(conn: psycopg.Connection) -> None:
    """Applies all SQL files in ``migrations/`` that are not applied yet, in name order.

    Several containers may start at the same time, so this waits for a lock first.
    """
    conn.execute("SELECT pg_advisory_lock(%s)", (MIGRATION_LOCK_KEY,))
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY)")
        files = sorted(
            (f for f in resources.files("mail_informer").joinpath("migrations").iterdir()
             if f.name.endswith(".sql")),
            key=lambda f: f.name,
        )
        applied = {r[0] for r in conn.execute("SELECT name FROM schema_migrations")}
        for f in files:
            if f.name in applied:
                continue
            with conn.transaction():
                conn.execute(f.read_text(encoding="utf-8"))
                conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (f.name,))
    finally:
        conn.execute("SELECT pg_advisory_unlock(%s)", (MIGRATION_LOCK_KEY,))


def get_sync_state(conn: psycopg.Connection) -> tuple[str, datetime] | None:
    """Returns ``(history_id, updated_at)``, or None before the first run."""
    row = conn.execute("SELECT history_id, updated_at FROM sync_state WHERE id = 1").fetchone()
    return (row[0], row[1]) if row else None


def set_sync_state(conn: psycopg.Connection, history_id: str) -> None:
    """Stores the history ID and sets ``updated_at`` to now."""
    conn.execute(
        """INSERT INTO sync_state (id, history_id, updated_at) VALUES (1, %s, now())
           ON CONFLICT (id) DO UPDATE SET history_id = EXCLUDED.history_id, updated_at = now()""",
        (history_id,),
    )


def latest_mail_date(conn: psycopg.Connection) -> datetime | None:
    """Returns the date of the newest stored mail, or None if there is none."""
    return conn.execute("SELECT max(internal_date) FROM messages").fetchone()[0]


def existing_ids(conn: psycopg.Connection, ids: list[str]) -> set[str]:
    """Returns those of the given Gmail IDs that are already stored."""
    if not ids:
        return set()
    rows = conn.execute("SELECT gmail_id FROM messages WHERE gmail_id = ANY(%s)", (ids,))
    return {r[0] for r in rows}


def insert_mails(conn: psycopg.Connection, mails: list[Mail]) -> None:
    """Stores mails. Mails that already exist are skipped. NUL bytes are removed from the body."""
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO messages
                 (gmail_id, thread_id, internal_date, from_addr, to_addrs, subject,
                  labels, snippet, body_text, is_bulk)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (gmail_id) DO NOTHING""",
            [
                (m.gmail_id, m.thread_id, m.internal_date, m.from_addr, m.to_addrs,
                 m.subject, m.labels, m.snippet, m.body_text.replace("\x00", ""),
                 m.is_bulk)
                for m in mails
            ],
        )


def last_sync_at(conn: psycopg.Connection) -> datetime | None:
    """Returns the time of the last successful sync, or None before the first run."""
    row = conn.execute("SELECT updated_at FROM sync_state WHERE id = 1").fetchone()
    return row[0] if row else None


_UNANALYZED = """FROM messages m
    LEFT JOIN analyses a ON a.gmail_id = m.gmail_id AND a.prompt_version = %s
    WHERE a.id IS NULL OR (a.status = 'pending' AND a.attempts < %s)"""


def try_analyzer_lock(conn: psycopg.Connection) -> bool:
    """Tries to take the analyzer lock without waiting. Returns True if it got the lock."""
    return conn.execute("SELECT pg_try_advisory_lock(%s)", (ANALYZER_LOCK_KEY,)).fetchone()[0]


def analyzer_unlock(conn: psycopg.Connection) -> None:
    """Releases the analyzer lock."""
    conn.execute("SELECT pg_advisory_unlock(%s)", (ANALYZER_LOCK_KEY,))


def pick_unanalyzed(
    conn: psycopg.Connection, prompt_version: str, max_attempts: int, limit: int
) -> list[PendingMail]:
    """Returns mails that still need an analysis, newest first.

    A mail needs an analysis if it has no result for the prompt version, or its result
    is still pending with fewer than ``max_attempts`` attempts.
    """
    rows = conn.execute(
        f"""SELECT m.gmail_id, m.from_addr, m.subject, m.body_text, m.is_bulk
            {_UNANALYZED} ORDER BY m.internal_date DESC LIMIT %s""",
        (prompt_version, max_attempts, limit),
    )
    return [PendingMail(*r) for r in rows]


def get_mails(conn: psycopg.Connection, ids: list[str]) -> list[PendingMail]:
    """Returns the archived mails with the given Gmail IDs. Unknown IDs are left out."""
    rows = conn.execute(
        """SELECT gmail_id, from_addr, subject, body_text, is_bulk
           FROM messages WHERE gmail_id = ANY(%s)""",
        (ids,),
    )
    return [PendingMail(*r) for r in rows]


def count_unanalyzed(conn: psycopg.Connection, prompt_version: str, max_attempts: int) -> int:
    """Counts the mails that still need an analysis."""
    return conn.execute(
        f"SELECT count(*) {_UNANALYZED}", (prompt_version, max_attempts)
    ).fetchone()[0]


def record_failed_attempt(
    conn: psycopg.Connection, gmail_id: str, prompt_version: str, model: str, max_attempts: int
) -> str:
    """Counts one failed attempt. Returns the new status, ``pending`` or ``failed``."""
    return conn.execute(
        """INSERT INTO analyses (gmail_id, prompt_version, status, model, attempts)
           VALUES (%(id)s, %(v)s, CASE WHEN 1 >= %(max)s THEN 'failed' ELSE 'pending' END,
                   %(model)s, 1)
           ON CONFLICT (gmail_id, prompt_version) DO UPDATE SET
             attempts = analyses.attempts + 1,
             status = CASE WHEN analyses.attempts + 1 >= %(max)s THEN 'failed' ELSE 'pending' END,
             model = EXCLUDED.model,
             updated_at = now()
           RETURNING status""",
        {"id": gmail_id, "v": prompt_version, "model": model, "max": max_attempts},
    ).fetchone()[0]


def save_result(
    conn: psycopg.Connection, gmail_id: str, prompt_version: str, model: str,
    category: str, importance: str, summary: str, reason: str,
) -> None:
    """Stores a finished result. Replaces an earlier pending row for the same mail and version."""
    conn.execute(
        """INSERT INTO analyses
             (gmail_id, prompt_version, status, category, importance, summary, reason,
              model, attempts)
           VALUES (%s, %s, 'done', %s, %s, %s, %s, %s, 1)
           ON CONFLICT (gmail_id, prompt_version) DO UPDATE SET
             status = 'done', category = EXCLUDED.category, importance = EXCLUDED.importance,
             summary = EXCLUDED.summary, reason = EXCLUDED.reason, model = EXCLUDED.model,
             attempts = analyses.attempts + 1, updated_at = now()""",
        (gmail_id, prompt_version, category, importance, summary, reason, model),
    )


def touch_analyzer_ok(conn: psycopg.Connection) -> None:
    """Records that an analyzer pass finished successfully now."""
    conn.execute(
        """INSERT INTO analyzer_state (id, last_ok_at) VALUES (1, now())
           ON CONFLICT (id) DO UPDATE SET last_ok_at = now()"""
    )


def last_analyzer_ok(conn: psycopg.Connection) -> datetime | None:
    """Returns the time of the last successful analyzer pass, or None before the first one."""
    row = conn.execute("SELECT last_ok_at FROM analyzer_state WHERE id = 1").fetchone()
    return row[0] if row else None
