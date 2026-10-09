import os
from datetime import datetime, timezone

import pytest

from mail_informer import cli, db
from mail_informer.parsing import Mail


@pytest.fixture
def env(monkeypatch, conn):
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    monkeypatch.delenv("ANALYZER_MODEL", raising=False)  # the healthcheck needs no model
    return conn


def add_mail(conn):
    db.insert_mails(conn, [Mail(
        gmail_id="m1", thread_id="t", internal_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        from_addr="a@example.org", to_addrs="b@example.org", subject="S", body_text="Text",
    )])


def set_last_ok(conn, minutes_ago):
    conn.execute(
        "INSERT INTO analyzer_state (id, last_ok_at) "
        "VALUES (1, now() - make_interval(mins => %s)) "
        "ON CONFLICT (id) DO UPDATE SET last_ok_at = EXCLUDED.last_ok_at",
        (minutes_ago,),
    )


def test_healthy_when_there_is_no_work_even_without_a_pass(env):
    assert cli.main(["analyzer-health"]) == 0


def test_healthy_when_there_is_work_and_the_last_pass_is_recent(env):
    add_mail(env)
    set_last_ok(env, minutes_ago=5)
    assert cli.main(["analyzer-health"]) == 0


def test_unhealthy_when_there_is_work_and_the_last_pass_is_old(env):
    add_mail(env)
    set_last_ok(env, minutes_ago=45)
    assert cli.main(["analyzer-health"]) == 1


def test_unhealthy_when_there_is_work_and_no_pass_ever_succeeded(env):
    add_mail(env)
    assert cli.main(["analyzer-health"]) == 1


def test_work_is_counted_per_prompt_version(env):
    add_mail(env)
    for _ in range(3):
        db.record_failed_attempt(env, "m1", "v-health", "m", 3)
    set_last_ok(env, minutes_ago=300)
    # A result for another prompt version does not hide the work of the current one.
    assert cli.main(["analyzer-health"]) == 1
    from mail_informer.analysis import prompts
    db.save_result(env, "m1", prompts.PROMPT_VERSION, "m", "other", "normal", "", "r")
    assert cli.main(["analyzer-health"]) == 0
