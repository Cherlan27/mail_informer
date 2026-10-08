import json
import os
import re
from datetime import datetime, timezone

import pytest

from mail_informer import cli, db
from mail_informer.analysis import prompts
from mail_informer.analysis.evaluate import Label, evaluate, format_report, load_labels
from mail_informer.analysis.model import ModelUnavailable
from mail_informer.analysis.rules import InvalidAnswer
from mail_informer.parsing import Mail


def add(conn, gmail_id, is_bulk=False):
    db.insert_mails(conn, [Mail(
        gmail_id=gmail_id, thread_id="t", internal_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        from_addr="a@example.org", to_addrs="b@example.org", subject=f"subject-{gmail_id}",
        body_text="Text", is_bulk=is_bulk,
    )])


class FakeModel:
    """Answers by subject. answers maps gmail_id to (category, importance) or an exception."""

    def __init__(self, answers):
        self.answers = answers

    def chat_json(self, messages, schema):
        assert schema is prompts.CLASSIFY_SCHEMA  # evaluation never asks for summaries
        user = next(m["content"] for m in messages if m["role"] == "user")
        gmail_id = re.search(r"Subject: subject-(\S+)", user).group(1)
        answer = self.answers[gmail_id]
        if isinstance(answer, Exception):
            raise answer
        category, importance = answer
        return {"category": category, "importance": importance, "reason": "r"}


def labels(*rows):
    return [Label(gmail_id=g, category=c, importance=i) for g, c, i in rows]


def test_report_counts_correct_categories_and_importance(conn):
    for i in "abcd":
        add(conn, i)
    model = FakeModel({
        "a": ("security", "urgent"),       # both right
        "b": ("newsletter", "ignore"),     # both right
        "c": ("job", "normal"),            # category wrong, importance right
        "d": ("other", "important"),       # category right, importance wrong
    })
    report = evaluate(conn, model, labels(
        ("a", "security", "urgent"), ("b", "newsletter", "ignore"),
        ("c", "newsletter", "normal"), ("d", "other", "normal")))
    assert report.total == 4
    assert report.category_correct == 3
    assert report.importance_correct == 3
    assert report.invalid == 0


def test_missed_urgent_mails_are_listed(conn):
    for i in "ab":
        add(conn, i)
    model = FakeModel({"a": ("security", "important"), "b": ("work", "urgent")})
    report = evaluate(conn, model, labels(("a", "security", "urgent"), ("b", "work", "urgent")))
    assert report.missed_urgent == ["a"]


def test_false_urgent_mails_are_listed(conn):
    add(conn, "a")
    report = evaluate(conn, FakeModel({"a": ("advertising", "urgent")}),
                      labels(("a", "advertising", "ignore")))
    assert report.false_urgent == ["a"]
    assert report.missed_urgent == []


def test_missed_urgent_uses_the_raw_model_answer_not_the_bulk_guard(conn):
    add(conn, "old", is_bulk=None)  # unknown bulk flag: the guard would lower urgent
    report = evaluate(conn, FakeModel({"old": ("security", "urgent")}),
                      labels(("old", "security", "urgent")))
    assert report.missed_urgent == []
    assert report.guard_lowered == 1


def test_invalid_answer_counts_as_wrong_not_as_a_crash(conn):
    add(conn, "a")
    report = evaluate(conn, FakeModel({"a": InvalidAnswer("not json")}),
                      labels(("a", "work", "urgent")))
    assert report.invalid == 1
    assert report.category_correct == 0 and report.importance_correct == 0
    assert report.missed_urgent == ["a"]


def test_unavailable_model_stops_the_evaluation(conn):
    add(conn, "a")
    with pytest.raises(ModelUnavailable):
        evaluate(conn, FakeModel({"a": ModelUnavailable("down")}), labels(("a", "work", "normal")))


def test_evaluation_writes_nothing_to_the_database(conn):
    add(conn, "a")
    before = conn.execute("SELECT * FROM messages").fetchall()
    evaluate(conn, FakeModel({"a": ("work", "normal")}), labels(("a", "work", "normal")))
    assert conn.execute("SELECT count(*) FROM analyses").fetchone()[0] == 0
    assert conn.execute("SELECT * FROM messages").fetchall() == before


def test_label_for_an_unknown_mail_is_an_error(conn):
    with pytest.raises(ValueError, match="nope"):
        evaluate(conn, FakeModel({}), labels(("nope", "work", "normal")))


def test_report_text_shows_the_numbers_and_the_missed_urgent_ids(conn):
    for i in "ab":
        add(conn, i)
    report = evaluate(conn, FakeModel({"a": ("work", "normal"), "b": ("work", "urgent")}),
                      labels(("a", "work", "urgent"), ("b", "work", "urgent")))
    text = format_report(report, "some-model")
    assert "some-model" in text
    assert "importance: 1/2" in text
    assert "category: 2/2" in text
    assert "missed urgent: 1" in text
    assert "a" in text.split("missed urgent")[1]


# --- label file ---------------------------------------------------------------------

def write(path, *lines):
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_load_labels_reads_ids_and_ratings_only(tmp_path):
    f = tmp_path / "labels.jsonl"
    write(f, json.dumps({"gmail_id": "a", "category": "work", "importance": "urgent"}),
          "", json.dumps({"gmail_id": "b", "category": "job", "importance": "ignore"}))
    assert load_labels(f) == [Label("a", "work", "urgent"), Label("b", "job", "ignore")]


@pytest.mark.parametrize("line", [
    '{"gmail_id": "a", "category": "spam", "importance": "urgent"}',
    '{"gmail_id": "a", "category": "work", "importance": "critical"}',
    '{"category": "work", "importance": "urgent"}',
    "not json",
])
def test_load_labels_rejects_bad_lines(tmp_path, line):
    f = tmp_path / "labels.jsonl"
    write(f, line)
    with pytest.raises(ValueError, match="line 1"):
        load_labels(f)


# --- command ---------------------------------------------------------------------------

def test_evaluate_command_prints_the_report_and_returns_0(conn, tmp_path, monkeypatch, capsys):
    add(conn, "a")
    f = tmp_path / "labels.jsonl"
    write(f, json.dumps({"gmail_id": "a", "category": "work", "importance": "normal"}))
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    monkeypatch.setenv("ANALYZER_MODEL", "env-model")
    seen = {}

    def factory(url, name, *args, **kwargs):
        seen["name"] = name
        return FakeModel({"a": ("work", "normal")})

    monkeypatch.setattr(cli, "OllamaClient", factory)
    assert cli.main(["evaluate", "--labels", str(f), "--model", "other-model"]) == 0
    assert seen["name"] == "other-model"
    assert "other-model" in capsys.readouterr().out
