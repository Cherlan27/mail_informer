from types import SimpleNamespace

import pytest

from mail_informer import cli


def cfg(path):
    return SimpleNamespace(sender_rules_path=str(path))


def test_broken_rule_file_is_reported_as_refused(tmp_path):
    f = tmp_path / "rules.toml"
    f.write_text('[[rule]]\nname = "ads"\ndomain = ".example.com"\n'
                 'category = "advertising"\nimportance = "ignore"\n', encoding="utf-8")
    with pytest.raises(RuntimeError, match=r"SENDER_RULES_PATH is refused: rule 'ads'"):
        cli._load_sender_rules(cfg(f))


def test_other_errors_are_not_reported_as_a_broken_rule_file(monkeypatch, tmp_path):
    def boom(path):
        raise ValueError("a bug, not a rule file error")

    monkeypatch.setattr(cli, "load_rules", boom)
    with pytest.raises(ValueError, match="a bug") as e:
        cli._load_sender_rules(cfg(tmp_path / "rules.toml"))
    assert not isinstance(e.value, RuntimeError)
    assert "SENDER_RULES_PATH" not in str(e.value)
