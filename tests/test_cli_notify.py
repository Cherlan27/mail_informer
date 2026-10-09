import os
from datetime import datetime, timezone

import pytest

from mail_informer import cli, db
from mail_informer.notify.client import NotifierUnavailable
from mail_informer.parsing import Mail

SECRET_URL = "http://homeassistant:8123/api/webhook/very-secret-id"


class StubNotifier:
    def __init__(self, error=None):
        self.error = error
        self.messages = []

    def send(self, message):
        if self.error:
            raise self.error
        self.messages.append(message)


@pytest.fixture
def env(monkeypatch, conn):
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    monkeypatch.setenv("HA_WEBHOOK_URL", SECRET_URL)
    # No Gmail and no model settings: the notifier must not need them.
    for name in ("TOKEN_PATH", "CLIENT_SECRET_PATH", "ANALYZER_MODEL"):
        monkeypatch.delenv(name, raising=False)
    return conn


def use_notifier(monkeypatch, notifier):
    seen = {}

    def factory(url, *args, **kwargs):
        seen["url"] = url
        return notifier

    monkeypatch.setattr(cli, "HaWebhookClient", factory)
    return seen


def add_important_mail_after_start(conn):
    conn.execute("INSERT INTO notifier_state (id, start_at) VALUES (1, now() - interval '1 hour')")
    db.insert_mails(conn, [Mail(
        gmail_id="m1", thread_id="t", internal_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        from_addr="a@example.org", to_addrs="b@example.org", subject="S", body_text="Text")])
    db.save_result(conn, "m1", "v1", "m", "work", "urgent", "Kurz.", "r")


def test_notify_returns_0_and_sends_the_message(env, monkeypatch):
    notifier = StubNotifier()
    seen = use_notifier(monkeypatch, notifier)
    add_important_mail_after_start(env)
    assert cli.main(["notify"]) == 0
    assert seen["url"] == SECRET_URL
    assert [m["importance"] for m in notifier.messages] == ["urgent"]


def test_notify_returns_1_when_home_assistant_is_unavailable(env, monkeypatch, caplog):
    use_notifier(monkeypatch, StubNotifier(NotifierUnavailable("down")))
    add_important_mail_after_start(env)
    assert cli.main(["notify"]) == 1
    assert env.execute("SELECT count(*) FROM notifications").fetchone()[0] == 0
    assert "very-secret-id" not in caplog.text


def test_notify_returns_1_without_a_webhook_address(env, monkeypatch, caplog):
    monkeypatch.delenv("HA_WEBHOOK_URL")
    use_notifier(monkeypatch, StubNotifier())
    assert cli.main(["notify"]) == 1
    assert "HA_WEBHOOK_URL" in caplog.text


def test_notify_applies_migrations_itself(env, monkeypatch):
    env.execute("DROP TABLE IF EXISTS notifications, notifier_state, analyses, analyzer_state, messages, sync_state, schema_migrations")
    use_notifier(monkeypatch, StubNotifier())
    assert cli.main(["notify"]) == 0
    assert env.execute("SELECT count(*) FROM notifier_state").fetchone()[0] == 1
