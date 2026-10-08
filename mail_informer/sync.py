import logging
from datetime import datetime, timedelta
from typing import Protocol

import psycopg

from . import db
from .gmail import HistoryExpired
from .parsing import Mail, parse_message

log = logging.getLogger(__name__)

FALLBACK_BUFFER = timedelta(days=1)
BATCH_SIZE = 100


class MailSource(Protocol):
    def current_history_id(self) -> str: ...
    def new_message_ids(self, start_history_id: str) -> list[str]: ...
    def message_ids_after(self, since: datetime) -> list[str]: ...
    def get_message(self, message_id: str) -> dict | None: ...


def _fetch(gmail: MailSource, conn: psycopg.Connection, ids: list[str]) -> list[Mail]:
    known = db.existing_ids(conn, ids)
    mails = []
    for message_id in ids:
        if message_id in known:
            continue
        raw = gmail.get_message(message_id)
        if raw is None:  # deleted in the meantime
            continue
        mails.append(parse_message(raw))
    return mails


def run_sync(conn: psycopg.Connection, gmail: MailSource) -> int:
    """Runs one sync.

    The first run only stores the starting point and imports nothing.
    Later runs import all mails added since the stored history ID.

    Args:
        conn: Database connection.
        gmail: Source of mails.

    Returns:
        The number of newly stored mails.
    """
    state = db.get_sync_state(conn)
    if state is None:
        db.set_sync_state(conn, gmail.current_history_id())
        log.info("Initialized: import starts now, no history")
        return 0

    history_id, updated_at = state
    # Read this before fetching. Mails that arrive meanwhile are picked up by the next run.
    new_history_id = gmail.current_history_id()
    try:
        ids = gmail.new_message_ids(history_id)
    except HistoryExpired:
        since = (db.latest_mail_date(conn) or updated_at) - FALLBACK_BUFFER
        log.warning("History ID expired, loading mails since %s", since)
        ids = gmail.message_ids_after(since)

    # Batches limit memory use. The insert is idempotent, so a batch may commit before
    # the history ID moves. After a crash, the next run fetches the rest and skips
    # mails that are already stored.
    stored = 0
    for start in range(0, len(ids), BATCH_SIZE):
        mails = _fetch(gmail, conn, ids[start:start + BATCH_SIZE])
        db.insert_mails(conn, mails)
        stored += len(mails)
    db.set_sync_state(conn, new_history_id)
    log.info("%d new mails stored", stored)
    return stored
