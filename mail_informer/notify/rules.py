"""Pure rules for notifications. This module does no I/O."""

from ..analysis.rules import clean_text

SENDER_MAX_CHARS = 200
SUMMARY_MAX_CHARS = 500
HOURLY_LIMIT = 10
# A mail whose analysis is older than this is no longer reported.
MAX_AGE_HOURS = 6


def mail_message(category: str, importance: str, sender: str | None, summary: str) -> dict:
    """Builds the message for one mail.

    The message holds no mail ID, no subject, and no body. Sender and summary are
    free text, so they are cleaned and cut.

    Args:
        category: The stored category.
        importance: ``urgent`` or ``important``.
        sender: The ``From`` header text.
        summary: The stored German summary.

    Returns:
        The message as a JSON-ready dict.
    """
    return {
        "kind": "mail",
        "category": category,
        "importance": importance,
        "sender": clean_text(sender or "", SENDER_MAX_CHARS),
        "summary": clean_text(summary, SUMMARY_MAX_CHARS),
    }


def digest_message(count: int) -> dict:
    """Builds the collective message for mails over the hourly limit."""
    return {"kind": "digest", "count": count}


def free_places(sent_last_hour: int) -> int:
    """Returns how many single messages may still be sent in this hour."""
    return max(0, HOURLY_LIMIT - sent_last_hour)


def order_mails(mails: list) -> list:
    """Orders mails for sending: ``urgent`` first, then the newest analysis first.

    Args:
        mails: Objects with ``importance`` and ``analyzed_at``.
    """
    newest_first = sorted(mails, key=lambda m: m.analyzed_at, reverse=True)
    return sorted(newest_first, key=lambda m: m.importance != "urgent")


def split_by_room(mails: list, room: int) -> tuple[list, list]:
    """Orders the mails and splits them into the ones to send singly and the rest."""
    ordered = order_mails(mails)
    return ordered[:room], ordered[room:]
