import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

KINDS = ("gmail", "imap")
DEFAULT_IMAP_PORT = 993
# No colon: the name is the prefix of IMAP mail keys ("<name>:<id>").
_NAME = re.compile(r"[a-z0-9][a-z0-9_-]*")


@dataclass(frozen=True)
class Account:
    """One mail account from the accounts file."""

    name: str
    kind: str
    token_path: str | None = None
    host: str | None = None
    user: str | None = None
    # Kept out of repr so a stray log line cannot print it.
    password: str | None = field(default=None, repr=False)
    port: int = DEFAULT_IMAP_PORT


def _text(entry: dict, name: str, key: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"account {name!r}: {key} is missing")
    return value


def _account(entry: dict, base: Path) -> Account:
    name = entry.get("name")
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise RuntimeError("account name must be lowercase letters, digits, '_' or '-'")
    kind = entry.get("kind")
    if kind not in KINDS:
        raise RuntimeError(f"account {name!r}: kind must be one of {', '.join(KINDS)}")
    if kind == "gmail":
        return Account(name, kind, token_path=str(base / _text(entry, name, "token")))
    port = entry.get("port", DEFAULT_IMAP_PORT)
    if not isinstance(port, int):
        raise RuntimeError(f"account {name!r}: port must be a number")
    return Account(
        name, kind,
        host=_text(entry, name, "host"),
        user=_text(entry, name, "user"),
        password=_text(entry, name, "password"),
        port=port,
    )


def load_accounts(path: str | Path) -> list[Account]:
    """Reads the accounts file.

    A relative token path is resolved against the folder of the file, so the same
    file works on the host and in the container.

    Args:
        path: Path to the TOML file.

    Returns:
        The accounts in file order.

    Raises:
        RuntimeError: If the file is missing, broken, or an account is not valid.
            The message never contains a password.
    """
    path = Path(path)
    try:
        raw = path.read_bytes()
    except OSError:
        raise RuntimeError(f"accounts file not found or not readable: {path}") from None
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError):
        # The parser message can quote the offending line, which may hold a password.
        raise RuntimeError(f"accounts file is not valid TOML: {path}") from None
    entries = data.get("account", [])
    if not entries:
        raise RuntimeError(f"no accounts in {path}")
    accounts = [_account(e, path.parent) for e in entries]
    seen: set[str] = set()
    for account in accounts:
        if account.name in seen:
            raise RuntimeError(f"duplicate account name: {account.name}")
        seen.add(account.name)
    return accounts
