import os
from datetime import datetime, timedelta, timezone

from mail_informer import db
from mail_informer.parsing import Mail

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)
MAX_AGE = 6


def add(conn, gmail_id, sender="a@example.org"):
    db.insert_mails(conn, [Mail(
        gmail_id=gmail_id, thread_id="t", internal_date=BASE, from_addr=sender,
        to_addrs="b@example.org", subject="Betreff", body_text="Text",
    )])


def analyze(conn, gmail_id, importance="important", version="v1", age_hours=0.0, summary="Kurz."):
    """Stores a done result and sets its time to ``age_hours`` ago."""
    db.save_result(conn, gmail_id, version, "m", "work", importance, summary, "r")
    conn.execute(
        "UPDATE analyses SET updated_at = now() - make_interval(secs => %s) "
        "WHERE gmail_id = %s AND prompt_version = %s",
        (age_hours * 3600, gmail_id, version),
    )


def start(conn, hours_ago=1):
    """Sets the start point of the notifier to ``hours_ago`` hours ago."""
    conn.execute(
        "INSERT INTO notifier_state (id, start_at) VALUES (1, now() - make_interval(hours => %s)) "
        "ON CONFLICT (id) DO UPDATE SET start_at = EXCLUDED.start_at", (hours_ago,))
    return db.notifier_start(conn)


def ids(conn, start_at):
    return [m.gmail_id for m in db.pick_reportable(conn, start_at, MAX_AGE)]


def test_picks_important_and_urgent_only(conn):
    for name, importance in [("u", "urgent"), ("i", "important"), ("n", "normal"), ("g", "ignore")]:
        add(conn, name)
        analyze(conn, name, importance)
    assert sorted(ids(conn, start(conn))) == ["i", "u"]


def test_skips_pending_and_failed_results(conn):
    add(conn, "p")
    add(conn, "f")
    db.record_failed_attempt(conn, "p", "v1", "m", 3)
    db.record_failed_attempt(conn, "f", "v1", "m", 1)
    assert ids(conn, start(conn)) == []


def test_skips_mails_first_analyzed_before_the_start(conn):
    add(conn, "old")
    analyze(conn, "old", age_hours=2)
    start_at = start(conn, hours_ago=1)
    add(conn, "new")
    analyze(conn, "new", age_hours=0.5)
    assert ids(conn, start_at) == ["new"]


def test_old_mail_analyzed_again_after_the_start_is_not_picked(conn):
    add(conn, "old")
    analyze(conn, "old", version="v1", age_hours=2)
    start_at = start(conn, hours_ago=1)
    analyze(conn, "old", version="v2", age_hours=0.1)
    assert ids(conn, start_at) == []


def test_skips_mails_whose_newest_analysis_is_older_than_the_age_limit(conn):
    add(conn, "stale")
    add(conn, "fresh")
    start_at = start(conn, hours_ago=10)
    analyze(conn, "stale", age_hours=7)
    analyze(conn, "fresh", age_hours=5)
    assert ids(conn, start_at) == ["fresh"]


def test_skips_mails_that_are_already_recorded(conn):
    add(conn, "a")
    add(conn, "b")
    analyze(conn, "a")
    analyze(conn, "b")
    start_at = start(conn)
    db.record_sent(conn, "a", "important")
    assert ids(conn, start_at) == ["b"]


def test_uses_the_newest_analysis_when_there_are_two_prompt_versions(conn):
    add(conn, "m")
    start_at = start(conn, hours_ago=10)
    analyze(conn, "m", importance="urgent", version="v1", age_hours=2)
    analyze(conn, "m", importance="normal", version="v2", age_hours=1)
    assert ids(conn, start_at) == []
    analyze(conn, "m", importance="urgent", version="v3", age_hours=0.5, summary="Neu.")
    picked = db.pick_reportable(conn, start_at, MAX_AGE)
    assert [(m.gmail_id, m.importance, m.summary) for m in picked] == [("m", "urgent", "Neu.")]


def test_picked_mail_has_the_fields_for_the_message(conn):
    add(conn, "m", sender="Anna <a@example.org>")
    start_at = start(conn)
    analyze(conn, "m", importance="urgent", summary="Zusammenfassung.")
    mail = db.pick_reportable(conn, start_at, MAX_AGE)[0]
    assert (mail.gmail_id, mail.category, mail.importance, mail.sender, mail.summary) == \
        ("m", "work", "urgent", "Anna <a@example.org>", "Zusammenfassung.")
    assert mail.analyzed_at is not None


def test_start_point_is_set_once(conn):
    first = db.set_notifier_start(conn)
    second = db.set_notifier_start(conn)
    assert first == second
    assert db.notifier_start(conn) == first


def test_start_point_is_none_before_the_first_pass(conn):
    assert db.notifier_start(conn) is None


def test_count_sent_in_the_last_hour(conn):
    for name in ("a", "b", "c", "d"):
        add(conn, name)
    db.record_sent(conn, "a", "urgent")
    db.record_sent(conn, "b", "important")
    db.record_sent(conn, "c", "important")
    conn.execute("UPDATE notifications SET created_at = now() - interval '2 hours' WHERE gmail_id = 'c'")
    db.record_suppressed(conn, [("d", "important")])
    assert db.count_sent_last_hour(conn) == 2


def test_record_suppressed_writes_all_rows_or_none(conn):
    add(conn, "a")
    try:
        db.record_suppressed(conn, [("a", "important"), ("missing", "important")])
    except Exception:
        pass
    assert conn.execute("SELECT count(*) FROM notifications").fetchone()[0] == 0
    db.record_suppressed(conn, [("a", "important")])
    assert conn.execute("SELECT status FROM notifications").fetchone()[0] == "suppressed"


def test_last_ok_time(conn):
    assert db.last_notifier_ok(conn) is None
    db.set_notifier_start(conn)
    assert db.last_notifier_ok(conn) is None
    db.touch_notifier_ok(conn)
    assert abs(db.last_notifier_ok(conn) - datetime.now(timezone.utc)) < timedelta(seconds=5)


def test_notifier_lock_blocks_a_second_connection_but_not_other_locks(conn):
    other = db.connect(os.environ["TEST_DATABASE_URL"])
    try:
        assert db.try_notifier_lock(conn)
        assert not db.try_notifier_lock(other)
        assert db.try_lock(other) and db.try_analyzer_lock(other)
        db.notifier_unlock(conn)
        assert db.try_notifier_lock(other)
    finally:
        other.close()


def test_count_reportable_is_zero_before_the_first_pass(conn):
    add(conn, "a")
    analyze(conn, "a", age_hours=2)
    assert db.count_reportable(conn, MAX_AGE) == 0
    start(conn, hours_ago=1)
    assert db.count_reportable(conn, MAX_AGE) == 0  # analyzed before the start
    add(conn, "b")
    analyze(conn, "b")
    assert db.count_reportable(conn, MAX_AGE) == 1
