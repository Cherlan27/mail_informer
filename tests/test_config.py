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


def test_analyzer_requires_a_model_name(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.delenv("ANALYZER_MODEL", raising=False)
    with pytest.raises(RuntimeError, match="ANALYZER_MODEL"):
        load_config(require_model=True)


def test_model_name_is_not_required_for_other_commands(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.delenv("ANALYZER_MODEL", raising=False)
    assert load_config().analyzer_model == ""


def test_model_server_defaults_to_the_host_address(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.delenv("OLLAMA_URL", raising=False)
    assert load_config().ollama_url == "http://host.docker.internal:11434"


def test_analyzer_settings_from_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("ANALYZER_MODEL", "some-model")
    monkeypatch.setenv("OLLAMA_URL", "http://localhost:11434")
    cfg = load_config(require_model=True)
    assert (cfg.analyzer_model, cfg.ollama_url) == ("some-model", "http://localhost:11434")


def test_notifier_requires_a_webhook_address(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.delenv("HA_WEBHOOK_URL", raising=False)
    with pytest.raises(RuntimeError, match="HA_WEBHOOK_URL"):
        load_config(require_webhook=True)


def test_webhook_address_must_be_an_http_address(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("HA_WEBHOOK_URL", "ftp://secret-id")
    with pytest.raises(RuntimeError) as error:
        load_config(require_webhook=True)
    assert "HA_WEBHOOK_URL" in str(error.value)
    assert "secret-id" not in str(error.value)


def test_webhook_address_is_not_required_for_other_commands(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.delenv("HA_WEBHOOK_URL", raising=False)
    assert load_config().ha_webhook_url == ""


def test_webhook_address_is_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("HA_WEBHOOK_URL", "http://homeassistant:8123/api/webhook/abc")
    assert load_config(require_webhook=True).ha_webhook_url.endswith("/abc")
