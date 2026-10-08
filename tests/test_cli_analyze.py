import os
from datetime import datetime, timezone

import pytest

from mail_informer import cli, db
from mail_informer.analysis.model import ModelUnavailable
from mail_informer.parsing import Mail


class StubModel:
    def __init__(self, error=None):
        self.error = error

    def chat_json(self, messages, schema):
        if self.error:
            raise self.error
        if "category" in schema["properties"]:
            return {"category": "other", "importance": "normal", "reason": "x"}
        return {"summary": "Kurz."}


@pytest.fixture
def env(monkeypatch, conn):
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    monkeypatch.setenv("ANALYZER_MODEL", "stub-model")
    # No Gmail settings at all: the analyzer must not need them.
    for name in ("TOKEN_PATH", "CLIENT_SECRET_PATH"):
        monkeypatch.delenv(name, raising=False)
    db.insert_mails(conn, [Mail(
        gmail_id="m1", thread_id="t", internal_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        from_addr="a@example.org", to_addrs="b@example.org", subject="S", body_text="Text",
    )])
    return conn


def use_model(monkeypatch, model):
    seen = {}

    def factory(url, name, *args, **kwargs):
        seen.update(url=url, name=name)
        return model

    monkeypatch.setattr(cli, "OllamaClient", factory)
    return seen


def test_analyze_returns_0_and_stores_results(env, monkeypatch):
    seen = use_model(monkeypatch, StubModel())
    assert cli.main(["analyze"]) == 0
    assert env.execute("SELECT status FROM analyses").fetchall() == [("done",)]
    assert seen["name"] == "stub-model"


def test_analyze_uses_the_configured_server_address(env, monkeypatch):
    monkeypatch.setenv("OLLAMA_URL", "http://example.invalid:1234")
    seen = use_model(monkeypatch, StubModel())
    cli.main(["analyze"])
    assert seen["url"] == "http://example.invalid:1234"


def test_analyze_returns_1_when_the_model_server_is_unavailable(env, monkeypatch):
    use_model(monkeypatch, StubModel(ModelUnavailable("down")))
    assert cli.main(["analyze"]) == 1
    assert env.execute("SELECT count(*) FROM analyses").fetchone()[0] == 0


def test_analyze_returns_1_without_a_model_name(env, monkeypatch):
    monkeypatch.delenv("ANALYZER_MODEL")
    use_model(monkeypatch, StubModel())
    assert cli.main(["analyze"]) == 1


def test_analyze_applies_migrations_itself(env, monkeypatch):
    env.execute("DROP TABLE IF EXISTS analyses, analyzer_state, messages, sync_state, schema_migrations")
    use_model(monkeypatch, StubModel())
    assert cli.main(["analyze"]) == 0
    assert env.execute("SELECT count(*) FROM analyses").fetchone()[0] == 0
