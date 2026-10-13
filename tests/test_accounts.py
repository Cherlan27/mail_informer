from pathlib import Path

import pytest

from mail_informer.accounts import load_accounts

VALID = """
[[account]]
name = "gmail"
kind = "gmail"
token = "token.json"

[[account]]
name = "privat"
kind = "imap"
host = "imap.example.org"
user = "me@example.org"
password = "s3cret-one"

[[account]]
name = "firma"
kind = "imap"
host = "imap.example.org"
user = "work@example.org"
password = "s3cret-two"
port = 1993
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "accounts.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_valid_file_gives_all_accounts(tmp_path):
    accounts = load_accounts(write(tmp_path, VALID))
    assert [a.name for a in accounts] == ["gmail", "privat", "firma"]
    assert [a.kind for a in accounts] == ["gmail", "imap", "imap"]


def test_token_path_is_relative_to_the_file(tmp_path):
    gmail = load_accounts(write(tmp_path, VALID))[0]
    assert Path(gmail.token_path) == tmp_path / "token.json"


def test_imap_values_and_default_port(tmp_path):
    _, privat, firma = load_accounts(write(tmp_path, VALID))
    assert (privat.host, privat.user, privat.password, privat.port) == (
        "imap.example.org", "me@example.org", "s3cret-one", 993)
    assert firma.port == 1993


def test_password_is_not_in_repr(tmp_path):
    privat = load_accounts(write(tmp_path, VALID))[1]
    assert "s3cret" not in repr(privat)


def test_missing_file_names_the_expected_path(tmp_path):
    missing = tmp_path / "nope.toml"
    with pytest.raises(RuntimeError, match="nope.toml"):
        load_accounts(missing)


def test_duplicate_name_is_rejected(tmp_path):
    text = VALID.replace('name = "firma"', 'name = "privat"')
    with pytest.raises(RuntimeError, match="duplicate.*privat"):
        load_accounts(write(tmp_path, text))


@pytest.mark.parametrize("name", ["a:b", "Privat", "", "-x", "a b"])
def test_bad_name_is_rejected(tmp_path, name):
    text = VALID.replace('name = "privat"', f'name = "{name}"')
    with pytest.raises(RuntimeError, match="name"):
        load_accounts(write(tmp_path, text))


def test_unknown_kind_is_rejected(tmp_path):
    text = VALID.replace('kind = "gmail"', 'kind = "pop3"')
    with pytest.raises(RuntimeError, match="kind.*gmail"):
        load_accounts(write(tmp_path, text))


@pytest.mark.parametrize("key", ["host", "user", "password"])
def test_missing_imap_value_names_account_and_key(tmp_path, key):
    # The first line with this key belongs to the account "privat".
    text = VALID.replace(
        next(ln for ln in VALID.splitlines() if ln.startswith(f"{key} = ")), "", 1)
    with pytest.raises(RuntimeError, match=rf"privat.*{key}"):
        load_accounts(write(tmp_path, text))


def test_missing_token_for_gmail_is_rejected(tmp_path):
    text = VALID.replace('token = "token.json"', "")
    with pytest.raises(RuntimeError, match="gmail.*token"):
        load_accounts(write(tmp_path, text))


def test_errors_never_contain_a_password(tmp_path):
    text = VALID.replace('host = "imap.example.org"\nuser = "me@example.org"', "", 1)
    with pytest.raises(RuntimeError) as err:
        load_accounts(write(tmp_path, text))
    assert "s3cret" not in str(err.value)


def test_file_without_accounts_is_rejected(tmp_path):
    with pytest.raises(RuntimeError, match="no accounts"):
        load_accounts(write(tmp_path, "# empty\n"))


def test_broken_toml_is_rejected_without_content(tmp_path):
    with pytest.raises(RuntimeError, match="not valid TOML") as err:
        load_accounts(write(tmp_path, 'password = "s3cret-x\n[[[\n'))
    assert "s3cret" not in str(err.value)
