import logging
from datetime import timedelta

import psycopg

from . import db
from .gmail import GmailClient, HistoryExpired
from .parsing import Mail, parse_message

log = logging.getLogger(__name__)

FALLBACK_BUFFER = timedelta(days=1)


def _fetch(gmail: GmailClient, conn: psycopg.Connection, ids: list[str]) -> list[Mail]:
    known = db.existing_ids(conn, ids)
    mails = []
    for message_id in ids:
        if message_id in known:
            continue
        raw = gmail.get_message(message_id)
        if raw is None:  # inzwischen gelöscht
            continue
        mails.append(parse_message(raw))
    return mails


def run_sync(conn: psycopg.Connection, gmail: GmailClient) -> int:
    """Ein Sync-Lauf. Gibt die Zahl neu gespeicherter Mails zurück."""
    state = db.get_sync_state(conn)
    if state is None:
        db.set_sync_state(conn, gmail.current_history_id())
        log.info("Initialisiert: Import startet ab jetzt, keine Historie")
        return 0

    history_id, updated_at = state
    # Vor dem Abruf lesen: Mails, die währenddessen eintreffen, kommen im nächsten Lauf.
    new_history_id = gmail.current_history_id()
    try:
        ids = gmail.new_message_ids(history_id)
    except HistoryExpired:
        since = (db.latest_mail_date(conn) or updated_at) - FALLBACK_BUFFER
        log.warning("historyId abgelaufen, lade Mails seit %s nach", since)
        ids = gmail.message_ids_after(since)

    mails = _fetch(gmail, conn, ids)
    with conn.transaction():
        db.insert_mails(conn, mails)
        db.set_sync_state(conn, new_history_id)
    log.info("%d neue Mails gespeichert", len(mails))
    return len(mails)
