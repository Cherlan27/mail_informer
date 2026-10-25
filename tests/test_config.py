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


def _clear_model_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    for name in ("MODEL_URL", "MODEL_API_KEY", "MODEL_REASONING_EFFORT", "ALLOW_REMOTE_MODEL", "OLLAMA_URL"):
        monkeypatch.delenv(name, raising=False)


def test_model_server_defaults_to_the_ollama_endpoint_on_the_host(monkeypatch):
    _clear_model_env(monkeypatch)
    assert load_config().model_url == "http://host.docker.internal:11434/v1"


def test_model_key_is_empty_by_default(monkeypatch):
    _clear_model_env(monkeypatch)
    assert load_config().model_api_key == ""


def test_reasoning_effort_is_empty_by_default(monkeypatch):
    _clear_model_env(monkeypatch)
    assert load_config().model_reasoning_effort == ""


def test_reasoning_effort_is_read_from_the_environment(monkeypatch):
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("MODEL_REASONING_EFFORT", "none")
    assert load_config().model_reasoning_effort == "none"


def test_remote_model_is_not_allowed_by_default(monkeypatch):
    _clear_model_env(monkeypatch)
    assert load_config().allow_remote_model is False


def test_remote_model_is_allowed_only_by_the_word_true(monkeypatch):
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("ALLOW_REMOTE_MODEL", "true")
    assert load_config().allow_remote_model is True
    monkeypatch.setenv("ALLOW_REMOTE_MODEL", "yes")
    assert load_config().allow_remote_model is False


def test_model_key_is_not_part_of_the_printed_config(monkeypatch):
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("MODEL_API_KEY", "sk-very-secret")
    assert "sk-very-secret" not in repr(load_config())


def test_analyzer_settings_from_environment(monkeypatch):
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("ANALYZER_MODEL", "some-model")
    monkeypatch.setenv("MODEL_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("MODEL_API_KEY", "k")
    cfg = load_config(require_model=True)
    assert (cfg.analyzer_model, cfg.model_url, cfg.model_api_key) == (
        "some-model", "http://localhost:11434/v1", "k")


def test_old_ollama_setting_without_the_new_one_fails_for_model_commands(monkeypatch):
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("OLLAMA_URL", "http://localhost:11434")
    with pytest.raises(RuntimeError, match="MODEL_URL"):
        load_config(require_model_server=True)


def test_old_ollama_setting_is_ignored_by_other_commands(monkeypatch):
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("OLLAMA_URL", "http://localhost:11434")
    assert load_config().model_url == "http://host.docker.internal:11434/v1"


def test_old_ollama_setting_is_fine_when_the_new_one_is_set(monkeypatch):
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("OLLAMA_URL", "http://localhost:11434")
    monkeypatch.setenv("MODEL_URL", "http://localhost:11434/v1")
    assert load_config(require_model_server=True).model_url.endswith("/v1")


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


def test_accounts_path_has_a_default(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.delenv("ACCOUNTS_PATH", raising=False)
    assert load_config().accounts_path == "secrets/accounts.toml"


def test_accounts_path_can_be_changed(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("ACCOUNTS_PATH", "/secrets/accounts.toml")
    assert load_config().accounts_path == "/secrets/accounts.toml"


def test_remote_address_without_permission_fails(monkeypatch):
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("MODEL_URL", "https://api.openai.com/v1")
    with pytest.raises(RuntimeError, match="ALLOW_REMOTE_MODEL"):
        load_config(require_model_server=True)


def test_remote_address_over_plain_http_fails_even_when_allowed(monkeypatch):
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("MODEL_URL", "http://api.example.com/v1")
    monkeypatch.setenv("ALLOW_REMOTE_MODEL", "true")
    with pytest.raises(RuntimeError, match="https"):
        load_config(require_model_server=True)


def test_remote_address_over_https_with_permission_passes(monkeypatch):
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("MODEL_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("ALLOW_REMOTE_MODEL", "true")
    assert load_config(require_model_server=True).model_url == "https://api.openai.com/v1"


def test_local_address_over_http_passes_without_permission(monkeypatch):
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("MODEL_URL", "http://192.168.1.5:8000/v1")
    assert load_config(require_model_server=True).allow_remote_model is False


def test_remote_address_is_not_checked_for_other_commands(monkeypatch):
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("MODEL_URL", "https://api.openai.com/v1")
    assert load_config().model_url == "https://api.openai.com/v1"


def test_remote_address_error_does_not_show_the_key(monkeypatch):
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("MODEL_URL", "https://user:pw-secret@api.openai.com/v1")
    monkeypatch.setenv("MODEL_API_KEY", "sk-very-secret")
    with pytest.raises(RuntimeError) as error:
        load_config(require_model_server=True)
    assert "sk-very-secret" not in str(error.value)
    assert "pw-secret" not in str(error.value)


def test_address_that_is_not_http_fails(monkeypatch):
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("MODEL_URL", "ftp://127.0.0.1/v1")
    with pytest.raises(RuntimeError, match="http"):
        load_config(require_model_server=True)
