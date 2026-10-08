from datetime import datetime
from importlib import resources

import psycopg

from .parsing import Mail

LOCK_KEY = 726_001  # Advisory lock key that prevents parallel runs


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
    """Applies all SQL files in ``migrations/`` that are not applied yet, in name order."""
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
                  labels, snippet, body_text)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (gmail_id) DO NOTHING""",
            [
                (m.gmail_id, m.thread_id, m.internal_date, m.from_addr, m.to_addrs,
                 m.subject, m.labels, m.snippet, m.body_text.replace("\x00", ""))
                for m in mails
            ],
        )


def last_sync_at(conn: psycopg.Connection) -> datetime | None:
    """Returns the time of the last successful sync, or None before the first run."""
    row = conn.execute("SELECT updated_at FROM sync_state WHERE id = 1").fetchone()
    return row[0] if row else None
