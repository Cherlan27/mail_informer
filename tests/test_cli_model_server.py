import pytest

from mail_informer import cli, db


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused")
    monkeypatch.setenv("ANALYZER_MODEL", "stub-model")
    for name in ("MODEL_URL", "MODEL_API_KEY", "MODEL_REASONING_EFFORT", "ALLOW_REMOTE_MODEL", "OLLAMA_URL"):
        monkeypatch.delenv(name, raising=False)

    def no_database(*args, **kwargs):
        raise AssertionError("the database must not be opened")

    monkeypatch.setattr(db, "connect", no_database)
    labels = tmp_path / "labels.jsonl"
    labels.write_text("")
    return str(labels)


def run(command: str, labels: str) -> int:
    return cli.main([command, "--labels", labels])


@pytest.mark.parametrize("command", ["analyze", "evaluate"])
def test_remote_server_without_permission_stops_before_the_database(env, monkeypatch, command):
    monkeypatch.setenv("MODEL_URL", "https://api.openai.com/v1")
    assert run(command, env) == 1


@pytest.mark.parametrize("command", ["analyze", "evaluate"])
def test_old_ollama_setting_stops_before_the_database(env, monkeypatch, command):
    monkeypatch.setenv("OLLAMA_URL", "http://localhost:11434")
    assert run(command, env) == 1


@pytest.mark.parametrize("command", ["analyze", "evaluate"])
def test_client_is_built_from_the_settings(env, monkeypatch, command):
    monkeypatch.setenv("MODEL_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("ALLOW_REMOTE_MODEL", "true")
    monkeypatch.setenv("MODEL_API_KEY", "sk-abc")
    monkeypatch.setenv("MODEL_REASONING_EFFORT", "none")
    seen = {}

    def factory(url, name, api_key="", reasoning_effort="", **kwargs):
        seen.update(url=url, name=name, api_key=api_key, reasoning_effort=reasoning_effort)
        raise StopIteration  # Stops right after the client is built; main() returns 1.

    monkeypatch.setattr(cli, "OpenAICompatibleClient", factory)
    assert run(command, env) == 1
    assert seen == {"url": "https://api.openai.com/v1", "name": "stub-model",
                    "api_key": "sk-abc", "reasoning_effort": "none"}
