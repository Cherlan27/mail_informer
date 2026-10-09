import logging
from collections.abc import Callable, Iterator
from datetime import datetime, timedelta
from typing import Protocol

import psycopg

from . import db
from .parsing import Mail

log = logging.getLogger(__name__)

FALLBACK_BUFFER = timedelta(days=1)

# Mails to store, and the cursor to save once they are stored (None: keep the old one).
Batch = tuple[list[Mail], str | None]


class MailSource(Protocol):
    """A mailbox the poller can read. The cursor is text that only the source understands."""

    def start_cursor(self) -> str: ...

    def fetch_since(
        self,
        cursor: str,
        fallback_since: datetime,
        is_known: Callable[[list[str]], set[str]],
    ) -> Iterator[Batch]: ...


def run_sync(conn: psycopg.Connection, account: str, source: MailSource) -> int:
    """Runs one sync of one account.

    The first run only stores the starting point and imports nothing.
    Later runs import the mails added since the stored cursor. The cursor moves only
    after the mails up to it are stored.

    Args:
        conn: Database connection.
        account: Name of the account. It keeps the cursor and the mails apart.
        source: The mailbox of this account.

    Returns:
        The number of newly stored mails.
    """
    state = db.get_cursor(conn, account)
    if state is None or state[0] is None:
        db.set_cursor(conn, account, source.start_cursor())
        log.info("%s: initialized, import starts now, no history", account)
        return 0

    cursor, updated_at = state
    # If the source can no longer use the cursor, it reloads mails since this date.
    fallback_since = (db.latest_mail_date(conn, account) or updated_at) - FALLBACK_BUFFER

    # The insert is idempotent, so a batch may commit before the cursor moves. After a
    # crash, the next run fetches the rest and skips mails that are already stored.
    stored = 0
    batches = source.fetch_since(cursor, fallback_since, lambda ids: db.existing_ids(conn, ids))
    for mails, new_cursor in batches:
        db.insert_mails(conn, mails, account)
        stored += len(mails)
        if new_cursor is not None:
            db.set_cursor(conn, account, new_cursor)
    # A source with no news hands out nothing, so no cursor was saved. The run still
    # succeeded, and the health check looks at this time.
    db.touch_sync(conn, account)
    log.info("%s: %d new mails stored", account, stored)
    return stored
