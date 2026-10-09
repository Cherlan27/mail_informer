import os

import pytest

from mail_informer import cli, db

ACCOUNTS = """
[[account]]
name = "gmail"
kind = "gmail"
token = "token.json"

[[account]]
name = "privat"
kind = "imap"
host = "imap.example.org"
user = "me@example.org"
password = "s3cret-pw"
"""


@pytest.fixture
def env(monkeypatch, conn, tmp_path):
    path = tmp_path / "accounts.toml"
    path.write_text(ACCOUNTS, encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    monkeypatch.setenv("ACCOUNTS_PATH", str(path))
    return conn


def set_last_sync(conn, account, minutes_ago):
    db.register_account(conn, account)
    conn.execute(
        "UPDATE sync_state SET cursor = 'c', updated_at = now() - make_interval(mins => %s) "
        "WHERE account = %s", (minutes_ago, account))


def test_unhealthy_before_the_first_sync(env):
    assert cli.main(["health"]) == 1


def test_healthy_when_every_account_synced_recently(env):
    set_last_sync(env, "gmail", minutes_ago=2)
    set_last_sync(env, "privat", minutes_ago=10)
    assert cli.main(["health"]) == 0


def test_unhealthy_after_three_missed_runs(env):
    # The poller runs every 5 minutes. 15 minutes without a sync means it is stuck.
    set_last_sync(env, "gmail", minutes_ago=20)
    set_last_sync(env, "privat", minutes_ago=20)
    assert cli.main(["health"]) == 1


def test_one_old_account_is_enough_to_be_unhealthy(env):
    set_last_sync(env, "gmail", minutes_ago=1)
    set_last_sync(env, "privat", minutes_ago=30)
    assert cli.main(["health"]) == 1


def test_an_account_that_never_succeeded_turns_unhealthy_after_15_minutes(env):
    set_last_sync(env, "gmail", minutes_ago=1)
    db.register_account(env, "privat")
    assert cli.main(["health"]) == 0
    env.execute("UPDATE sync_state SET updated_at = now() - interval '16 minutes' "
                "WHERE account = 'privat'")
    assert cli.main(["health"]) == 1


def test_an_account_without_any_row_is_unhealthy(env):
    set_last_sync(env, "gmail", minutes_ago=1)
    assert cli.main(["health"]) == 1


def test_rows_of_removed_accounts_are_ignored(env):
    set_last_sync(env, "gmail", minutes_ago=1)
    set_last_sync(env, "privat", minutes_ago=1)
    set_last_sync(env, "removed", minutes_ago=600)
    assert cli.main(["health"]) == 0
