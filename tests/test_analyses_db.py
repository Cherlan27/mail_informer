from datetime import datetime, timedelta, timezone

from mail_informer import db
from mail_informer.parsing import Mail

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)
V = "v1"
MAX = 3


def add(conn, gmail_id, days=0, is_bulk=False, subject="S", body="Text", sender="a@example.org"):
    db.insert_mails(conn, [Mail(
        gmail_id=gmail_id, thread_id="t", internal_date=BASE + timedelta(days=days),
        from_addr=sender, to_addrs="b@example.org", subject=subject, body_text=body,
        is_bulk=is_bulk,
    )])


def pick(conn, limit=50, version=V):
    return [m.gmail_id for m in db.pick_unanalyzed(conn, version, MAX, limit)]


def save(conn, gmail_id, version=V, importance="normal"):
    db.save_result(conn, gmail_id, version, "model-a", "other", importance, "", "reason")


def test_picks_unanalyzed_mails_newest_first(conn):
    add(conn, "old", days=1)
    add(conn, "new", days=3)
    add(conn, "mid", days=2)
    assert pick(conn) == ["new", "mid", "old"]


def test_pick_returns_the_fields_the_analyzer_needs(conn):
    add(conn, "m1", is_bulk=True, subject="Betreff", body="Inhalt", sender="x@example.org")
    mail = db.pick_unanalyzed(conn, V, MAX, 10)[0]
    assert (mail.gmail_id, mail.from_addr, mail.subject, mail.body_text, mail.is_bulk) == \
        ("m1", "x@example.org", "Betreff", "Inhalt", True)


def test_pick_respects_the_limit(conn):
    for i in range(5):
        add(conn, f"m{i}", days=i)
    assert len(pick(conn, limit=2)) == 2


def test_finished_mails_are_skipped(conn):
    add(conn, "done")
    add(conn, "todo", days=-1)
    save(conn, "done")
    assert pick(conn) == ["todo"]


def test_finished_result_of_another_prompt_version_does_not_count(conn):
    add(conn, "m1")
    save(conn, "m1", version="v0")
    assert pick(conn, version="v1") == ["m1"]


def test_failed_attempts_below_the_limit_stay_in_the_queue(conn):
    add(conn, "m1")
    db.record_failed_attempt(conn, "m1", V, "model-a", MAX)
    db.record_failed_attempt(conn, "m1", V, "model-a", MAX)
    assert pick(conn) == ["m1"]
    assert conn.execute("SELECT status, attempts FROM analyses").fetchone() == ("pending", 2)


def test_mail_is_marked_failed_after_the_last_attempt_and_leaves_the_queue(conn):
    add(conn, "m1")
    for _ in range(MAX):
        status = db.record_failed_attempt(conn, "m1", V, "model-a", MAX)
    assert status == "failed"
    assert conn.execute("SELECT status, attempts, category, importance FROM analyses").fetchone() \
        == ("failed", MAX, None, None)
    assert pick(conn) == []


def test_save_result_stores_all_fields(conn):
    add(conn, "m1")
    db.save_result(conn, "m1", V, "model-a", "security", "urgent", "Kurz.", "Warnung")
    row = conn.execute(
        "SELECT status, category, importance, summary, reason, model, prompt_version, attempts "
        "FROM analyses").fetchone()
    assert row == ("done", "security", "urgent", "Kurz.", "Warnung", "model-a", V, 1)


def test_save_result_after_a_failed_attempt_updates_the_same_row(conn):
    add(conn, "m1")
    db.record_failed_attempt(conn, "m1", V, "model-a", MAX)
    db.save_result(conn, "m1", V, "model-a", "other", "normal", "", "ok")
    assert conn.execute("SELECT status, attempts FROM analyses").fetchall() == [("done", 2)]


def test_saving_twice_creates_no_duplicate(conn):
    add(conn, "m1")
    save(conn, "m1")
    save(conn, "m1")
    assert conn.execute("SELECT count(*) FROM analyses").fetchone()[0] == 1


def test_archived_mail_is_not_changed_by_analysis(conn):
    add(conn, "m1")
    before = conn.execute("SELECT * FROM messages").fetchall()
    save(conn, "m1")
    db.record_failed_attempt(conn, "m1", "v2", "model-a", MAX)
    assert conn.execute("SELECT * FROM messages").fetchall() == before


def test_count_unanalyzed(conn):
    add(conn, "a")
    add(conn, "b")
    assert db.count_unanalyzed(conn, V, MAX) == 2
    save(conn, "a")
    assert db.count_unanalyzed(conn, V, MAX) == 1


def test_last_ok_time_is_none_then_set(conn):
    assert db.last_analyzer_ok(conn) is None
    db.touch_analyzer_ok(conn)
    first = db.last_analyzer_ok(conn)
    assert first is not None
    db.touch_analyzer_ok(conn)
    assert db.last_analyzer_ok(conn) >= first
