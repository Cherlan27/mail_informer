import logging
import os
from datetime import datetime, timezone

import pytest

from mail_informer import cli, db
from mail_informer.parsing import Mail

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

[[account]]
name = "firma"
kind = "imap"
host = "imap.example.org"
user = "work@example.org"
password = "s3cret-pw-2"
"""


def mail(key):
    return Mail(gmail_id=key, thread_id="t",
                internal_date=datetime(2026, 10, 9, tzinfo=timezone.utc),
                from_addr="a@example.org", to_addrs="b@example.org", subject="S",
                labels=["INBOX"], snippet="s", body_text="Text")


class FakeSource:
    def __init__(self, name, mails=(), error=None):
        self.name, self.mails, self.error = name, list(mails), error
        self.closed = False

    def start_cursor(self):
        return "start"

    def fetch_since(self, cursor, fallback_since, is_known):
        if self.error:
            raise self.error
        yield self.mails, "next"

    def close(self):
        self.closed = True


@pytest.fixture
def env(monkeypatch, conn, tmp_path):
    path = tmp_path / "accounts.toml"
    path.write_text(ACCOUNTS, encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    monkeypatch.setenv("ACCOUNTS_PATH", str(path))
    return conn


def use_sources(monkeypatch, sources: dict):
    opened = []

    def open_source(account):
        source = sources[account.name]
        if isinstance(source, Exception):
            raise source
        opened.append(account.name)
        return source

    monkeypatch.setattr(cli, "_open_source", open_source)
    return opened


def states(conn):
    return dict(conn.execute("SELECT account, cursor FROM sync_state").fetchall())


def test_first_run_registers_and_starts_every_account(env, monkeypatch):
    sources = {n: FakeSource(n) for n in ("gmail", "privat", "firma")}
    use_sources(monkeypatch, sources)
    assert cli.main(["run"]) == 0
    assert states(env) == {"gmail": "start", "privat": "start", "firma": "start"}


def test_new_mails_of_all_accounts_are_stored(env, monkeypatch):
    sources = {n: FakeSource(n) for n in ("gmail", "privat", "firma")}
    use_sources(monkeypatch, sources)
    cli.main(["run"])
    for name in sources:
        sources[name].mails = [mail(f"{name}:1")]
    assert cli.main(["run"]) == 0
    rows = env.execute("SELECT account, gmail_id FROM messages ORDER BY account").fetchall()
    assert rows == [("firma", "firma:1"), ("gmail", "gmail:1"), ("privat", "privat:1")]


def test_a_failing_account_does_not_stop_the_others(env, monkeypatch):
    sources = {n: FakeSource(n) for n in ("gmail", "privat", "firma")}
    use_sources(monkeypatch, sources)
    cli.main(["run"])
    sources["gmail"].mails = [mail("g1")]
    sources["privat"].error = RuntimeError("server down")
    sources["firma"].mails = [mail("firma:1")]
    assert cli.main(["run"]) == 1
    assert states(env) == {"gmail": "next", "privat": "start", "firma": "next"}
    assert env.execute("SELECT count(*) FROM messages").fetchone()[0] == 2


def test_an_account_that_cannot_connect_does_not_stop_the_others(env, monkeypatch):
    sources = {"gmail": FakeSource("gmail"), "privat": ConnectionError("no route"),
               "firma": FakeSource("firma")}
    opened = use_sources(monkeypatch, sources)
    assert cli.main(["run"]) == 1
    assert opened == ["gmail", "firma"]
    assert states(env)["firma"] == "start"


def test_the_log_names_the_account_but_never_a_password(env, monkeypatch, caplog):
    sources = {n: FakeSource(n) for n in ("gmail", "privat", "firma")}
    sources["privat"] = RuntimeError("login refused")
    use_sources(monkeypatch, sources)
    with caplog.at_level(logging.INFO):
        cli.main(["run"])
    assert "privat" in caplog.text
    assert "s3cret" not in caplog.text


def test_sources_are_closed_after_the_sync(env, monkeypatch):
    sources = {n: FakeSource(n) for n in ("gmail", "privat", "firma")}
    sources["privat"].error = RuntimeError("boom")
    use_sources(monkeypatch, sources)
    cli.main(["run"])
    cli.main(["run"])
    assert all(s.closed for s in sources.values())


def test_a_removed_account_is_not_synced_and_keeps_its_mails(env, monkeypatch, tmp_path):
    sources = {n: FakeSource(n) for n in ("gmail", "privat", "firma")}
    opened = use_sources(monkeypatch, sources)
    cli.main(["run"])
    db.insert_mails(env, [mail("firma:old")], "firma")
    only_gmail = tmp_path / "only.toml"
    gmail_block = ACCOUNTS[:ACCOUNTS.index('[[account]]\nname = "privat"')]
    only_gmail.write_text(gmail_block, encoding="utf-8")
    monkeypatch.setenv("ACCOUNTS_PATH", str(only_gmail))
    opened.clear()
    assert cli.main(["run"]) == 0
    assert opened == ["gmail"]
    assert env.execute("SELECT count(*) FROM messages WHERE account = 'firma'"
                       ).fetchone()[0] == 1


def test_warns_when_a_gmail_sync_point_exists_but_the_file_has_no_such_account(
        env, monkeypatch, tmp_path, caplog):
    db.register_account(env, "gmail")
    renamed = tmp_path / "renamed.toml"
    renamed.write_text(ACCOUNTS.replace('name = "gmail"', 'name = "main-gmail"'),
                       encoding="utf-8")
    monkeypatch.setenv("ACCOUNTS_PATH", str(renamed))
    use_sources(monkeypatch, {n: FakeSource(n) for n in ("main-gmail", "privat", "firma")})
    with caplog.at_level(logging.WARNING):
        cli.main(["run"])
    assert "gmail" in caplog.text and "renamed" in caplog.text.lower()


def test_missing_accounts_file_fails_with_the_expected_path(env, monkeypatch, caplog):
    monkeypatch.setenv("ACCOUNTS_PATH", "/nowhere/accounts.toml")
    assert cli.main(["run"]) == 1
    assert "accounts.toml" in caplog.text
