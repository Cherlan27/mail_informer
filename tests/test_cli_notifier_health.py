import os
from datetime import datetime, timezone

import pytest

from mail_informer import cli, db
from mail_informer.parsing import Mail


@pytest.fixture
def env(monkeypatch, conn):
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    monkeypatch.delenv("HA_WEBHOOK_URL", raising=False)  # the healthcheck needs no address
    return conn


def add_waiting_mail(conn, analyzed_hours_ago=0.0):
    """A reportable mail. The start point lies before its analysis."""
    db.insert_mails(conn, [Mail(
        gmail_id="m1", thread_id="t", internal_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        from_addr="a@example.org", to_addrs="b@example.org", subject="S", body_text="Text")])
    db.save_result(conn, "m1", "v1", "m", "work", "important", "Kurz.", "r")
    conn.execute("UPDATE analyses SET updated_at = now() - make_interval(secs => %s)",
                 (analyzed_hours_ago * 3600,))


def set_state(conn, last_ok_minutes_ago, start_hours_ago=48):
    conn.execute(
        "INSERT INTO notifier_state (id, start_at, last_ok_at) VALUES (1, "
        "now() - make_interval(hours => %s), now() - make_interval(mins => %s)) "
        "ON CONFLICT (id) DO UPDATE SET start_at = EXCLUDED.start_at, "
        "last_ok_at = EXCLUDED.last_ok_at",
        (start_hours_ago, last_ok_minutes_ago))


def test_healthy_when_there_is_no_work_even_without_a_pass(env):
    assert cli.main(["notifier-health"]) == 0


def test_healthy_when_there_is_work_and_the_last_pass_is_recent(env):
    add_waiting_mail(env)
    set_state(env, last_ok_minutes_ago=5)
    assert cli.main(["notifier-health"]) == 0


def test_unhealthy_when_there_is_work_and_the_last_pass_is_old(env):
    add_waiting_mail(env)
    set_state(env, last_ok_minutes_ago=45)
    assert cli.main(["notifier-health"]) == 1


def test_healthy_when_the_only_waiting_mails_are_older_than_the_age_limit(env):
    add_waiting_mail(env, analyzed_hours_ago=7)
    set_state(env, last_ok_minutes_ago=300)
    assert cli.main(["notifier-health"]) == 0


def test_unhealthy_when_there_is_work_and_the_state_has_no_successful_pass(env):
    add_waiting_mail(env)
    set_state(env, last_ok_minutes_ago=0)
    env.execute("UPDATE notifier_state SET last_ok_at = NULL")
    assert cli.main(["notifier-health"]) == 1
