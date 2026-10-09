"""One notifier pass: report new important and urgent mails to Home Assistant."""

import logging

import psycopg

from .. import db
from . import rules
from .client import Notifier

log = logging.getLogger(__name__)


def run_notification(conn: psycopg.Connection, notifier: Notifier) -> int:
    """Runs one notifier pass.

    A mail is sent first and recorded after that, one mail per transaction. A crash
    in between sends that mail again in the next pass. A repeated message is better
    than a lost one. Only one pass can run at a time.

    Args:
        conn: Database connection.
        notifier: Where the messages go.

    Returns:
        The number of single messages sent. 0 if another pass is active.

    Raises:
        NotifierUnavailable: If a message could not be delivered. Mails sent before
            that stay recorded. Nothing is recorded for the failed message.
    """
    if not db.try_notifier_lock(conn):
        log.info("Another notifier pass is active, exiting")
        return 0
    try:
        start_at = db.set_notifier_start(conn)
        mails = db.pick_reportable(conn, start_at, rules.MAX_AGE_HOURS)
        room = rules.free_places(db.count_sent_last_hour(conn))
        singles, rest = rules.split_by_room(mails, room)
        for mail in singles:
            notifier.send(rules.mail_message(mail.category, mail.importance, mail.sender, mail.summary))
            db.record_sent(conn, mail.gmail_id, mail.importance)
        if rest:
            notifier.send(rules.digest_message(len(rest)))
            db.record_suppressed(conn, [(m.gmail_id, m.importance) for m in rest])
        db.touch_notifier_ok(conn)
        log.info("%d messages sent, %d mails in a collective message", len(singles), len(rest))
        return len(singles)
    finally:
        db.notifier_unlock(conn)
