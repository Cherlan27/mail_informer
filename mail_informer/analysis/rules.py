"""Pure rules for mail analysis. This module does no I/O."""

import unicodedata
from dataclasses import dataclass

CATEGORIES = (
    "security", "personal", "work", "authority", "appointment", "invoice",
    "delivery", "job", "newsletter", "advertising", "other",
)
IMPORTANCE = ("ignore", "normal", "important", "urgent")

REASON_MAX_CHARS = 200
SUMMARY_MAX_CHARS = 400
CLASSIFY_BODY_CHARS = 2_000
SUMMARIZE_BODY_CHARS = 8_000


class InvalidAnswer(ValueError):
    """The model answer does not follow the expected schema."""


@dataclass(frozen=True)
class Classification:
    """A valid rating of one mail."""

    category: str
    importance: str
    reason: str


def clean_text(text: str, max_len: int | None = None) -> str:
    """Makes model text safe to store.

    Removes control characters, turns line breaks and tabs into spaces,
    collapses runs of spaces, and cuts the result to ``max_len``.

    Args:
        text: The raw text.
        max_len: Maximum length of the result. None means no limit.

    Returns:
        The cleaned text.
    """
    kept = (
        " " if ch in "\n\r\t" else ch
        for ch in text
        if ch in "\n\r\t" or unicodedata.category(ch) != "Cc"
    )
    cleaned = " ".join("".join(kept).split())
    return cleaned if max_len is None else cleaned[:max_len]


def _require_object(answer: object) -> dict:
    if not isinstance(answer, dict):
        raise InvalidAnswer("answer is not a JSON object")
    return answer


def _require_text(answer: dict, key: str) -> str:
    value = answer.get(key)
    if not isinstance(value, str):
        raise InvalidAnswer(f"'{key}' is missing or not text")
    return value


def parse_classification(answer: object) -> Classification:
    """Checks a classify answer from the model.

    Args:
        answer: The decoded JSON answer.

    Returns:
        The validated rating with a cleaned, shortened reason.

    Raises:
        InvalidAnswer: If a field is missing, has the wrong type, or has a value
            that is not allowed.
    """
    data = _require_object(answer)
    category = _require_text(data, "category")
    importance = _require_text(data, "importance")
    reason = _require_text(data, "reason")
    if category not in CATEGORIES:
        raise InvalidAnswer(f"unknown category: {category!r}")
    if importance not in IMPORTANCE:
        raise InvalidAnswer(f"unknown importance: {importance!r}")
    return Classification(category, importance, clean_text(reason, REASON_MAX_CHARS))


def parse_summary(answer: object) -> str:
    """Checks a summarize answer from the model.

    Args:
        answer: The decoded JSON answer.

    Returns:
        The cleaned, shortened summary.

    Raises:
        InvalidAnswer: If the summary is missing or not text.
    """
    return clean_text(_require_text(_require_object(answer), "summary"), SUMMARY_MAX_CHARS)


def apply_bulk_guard(importance: str, is_bulk: bool | None) -> str:
    """Lowers ``urgent`` to ``important`` for bulk mail.

    A mail whose bulk flag is unknown counts as bulk. This is the safe default.

    Args:
        importance: The importance given by the model.
        is_bulk: True, False, or None if unknown.

    Returns:
        The importance to store.
    """
    if importance == "urgent" and is_bulk is not False:
        return "important"
    return importance


def _mail_input(sender: str | None, subject: str | None, body: str, max_body: int) -> dict:
    return {"sender": sender or "", "subject": subject or "", "body": body[:max_body]}


def build_classify_input(sender: str | None, subject: str | None, body: str) -> dict:
    """Builds the short model input for classification."""
    return _mail_input(sender, subject, body, CLASSIFY_BODY_CHARS)


def build_summarize_input(sender: str | None, subject: str | None, body: str) -> dict:
    """Builds the longer model input for summarizing."""
    return _mail_input(sender, subject, body, SUMMARIZE_BODY_CHARS)
