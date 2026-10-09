import os

import pytest

from mail_informer import cli


@pytest.fixture
def env(monkeypatch, conn):
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    return conn


def set_last_sync(conn, minutes_ago):
    conn.execute(
        "INSERT INTO sync_state (id, history_id, updated_at) "
        "VALUES (1, 'h', now() - make_interval(mins => %s))", (minutes_ago,))


def test_unhealthy_before_the_first_sync(env):
    assert cli.main(["health"]) == 1


def test_healthy_when_the_last_sync_is_recent(env):
    set_last_sync(env, minutes_ago=10)
    assert cli.main(["health"]) == 0


def test_unhealthy_after_three_missed_runs(env):
    # The poller runs every 5 minutes. 15 minutes without a sync means it is stuck.
    set_last_sync(env, minutes_ago=20)
    assert cli.main(["health"]) == 1
