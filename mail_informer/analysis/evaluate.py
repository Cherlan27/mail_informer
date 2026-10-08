"""Compares a model with hand-made labels. Nothing is written to the database.

The label file is JSON Lines. Each line holds ``gmail_id``, ``category`` and
``importance``. It holds no mail text. The text is read from the archive.
"""

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import psycopg

from .. import db
from . import rules
from .analyzer import classify
from .model import ModelClient
from .rules import InvalidAnswer


@dataclass(frozen=True)
class Label:
    """The rating a person gave to one mail."""

    gmail_id: str
    category: str
    importance: str


@dataclass
class Report:
    """The result of one evaluation run."""

    total: int = 0
    category_correct: int = 0
    importance_correct: int = 0
    invalid: int = 0
    guard_lowered: int = 0
    missed_urgent: list[str] = field(default_factory=list)
    false_urgent: list[str] = field(default_factory=list)
    wrong_importance: list[tuple[str, str, str]] = field(default_factory=list)  # id, expected, answered
    confusion: Counter = field(default_factory=Counter)  # (expected, predicted) -> count


def load_labels(path: str | Path) -> list[Label]:
    """Reads a label file.

    Args:
        path: Path to the JSON Lines file. Empty lines are skipped.

    Returns:
        The labels in file order.

    Raises:
        ValueError: If a line is not valid. The message names the line number.
    """
    labels = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            gmail_id, category, importance = data["gmail_id"], data["category"], data["importance"]
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise ValueError(f"line {number}: not a valid label ({e})") from e
        if category not in rules.CATEGORIES:
            raise ValueError(f"line {number}: unknown category {category!r}")
        if importance not in rules.IMPORTANCE:
            raise ValueError(f"line {number}: unknown importance {importance!r}")
        labels.append(Label(gmail_id, category, importance))
    return labels


def evaluate(conn: psycopg.Connection, model: ModelClient, labels: list[Label]) -> Report:
    """Runs the model on labeled mails and compares the answers with the labels.

    Missed and false urgent mails are counted from the raw model answer. The bulk
    guard is a separate rule, so it must not hide a weak model. The number of
    answers that the guard would lower is reported on its own.

    Args:
        conn: Database connection. Only read.
        model: The model to test.
        labels: The hand-made labels.

    Returns:
        The report.

    Raises:
        ValueError: If a label names a mail that is not in the archive.
        ModelUnavailable: If the model server cannot be reached.
    """
    mails = {m.gmail_id: m for m in db.get_mails(conn, [lb.gmail_id for lb in labels])}
    unknown = [lb.gmail_id for lb in labels if lb.gmail_id not in mails]
    if unknown:
        raise ValueError(f"labels name mails that are not in the archive: {', '.join(unknown)}")
    report = Report()
    for label in labels:
        mail = mails[label.gmail_id]
        report.total += 1
        try:
            answer = classify(model, mail)
        except InvalidAnswer:
            report.invalid += 1
            report.confusion[(label.importance, "invalid")] += 1
            report.wrong_importance.append((label.gmail_id, label.importance, "invalid"))
            if label.importance == "urgent":
                report.missed_urgent.append(label.gmail_id)
            continue
        report.category_correct += answer.category == label.category
        report.importance_correct += answer.importance == label.importance
        if answer.importance != label.importance:
            report.wrong_importance.append((label.gmail_id, label.importance, answer.importance))
        report.confusion[(label.importance, answer.importance)] += 1
        if label.importance == "urgent" and answer.importance != "urgent":
            report.missed_urgent.append(label.gmail_id)
        if label.importance != "urgent" and answer.importance == "urgent":
            report.false_urgent.append(label.gmail_id)
        if rules.apply_bulk_guard(answer.importance, mail.is_bulk) != answer.importance:
            report.guard_lowered += 1
    return report


def format_report(report: Report, model_name: str) -> str:
    """Formats a report as plain text for the terminal."""
    lines = [
        f"Model: {model_name}",
        f"Mails: {report.total} (invalid answers: {report.invalid})",
        f"category: {report.category_correct}/{report.total}",
        f"importance: {report.importance_correct}/{report.total}",
        f"missed urgent: {len(report.missed_urgent)} {report.missed_urgent}",
        f"false urgent: {len(report.false_urgent)} {report.false_urgent}",
        f"answers the bulk guard would lower: {report.guard_lowered}",
        "importance (expected -> answered):",
    ]
    for (expected, answered), count in sorted(report.confusion.items()):
        lines.append(f"  {expected} -> {answered}: {count}")
    if report.wrong_importance:
        lines.append("wrong importance (mail: expected -> answered):")
        for gmail_id, expected, answered in report.wrong_importance:
            lines.append(f"  {gmail_id}: {expected} -> {answered}")
    return "\n".join(lines)
