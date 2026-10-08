import pytest

from mail_informer.config import load_config


def test_missing_database_url_fails_early(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        load_config()


def test_database_url_optional_for_auth(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert load_config(require_database=False).database_url == ""


def test_values_from_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("TOKEN_PATH", "/t.json")
    cfg = load_config()
    assert (cfg.database_url, cfg.token_path) == ("postgresql://x", "/t.json")
