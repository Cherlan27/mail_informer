"""Sender rules: rate mails from known bulk senders without the model.

A rule can only lower importance, so a rule never causes a notification.
Only ``load_rules`` does I/O.
"""

import tomllib
from dataclasses import dataclass
from email.utils import parseaddr
from pathlib import Path

from .rules import CATEGORIES

RULE_IMPORTANCE = ("ignore", "normal")
_RULE_KEYS = {"name", "sender", "domain", "category", "importance"}


@dataclass(frozen=True)
class SenderRule:
    """One rule. Exactly one of ``sender`` and ``domain`` is set, in lower case."""

    name: str
    sender: str | None
    domain: str | None
    category: str
    importance: str


def _text(item: dict, key: str, label: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}: '{key}' is missing or not text")
    return value.strip()


def _parse_rule(item: object, number: int) -> SenderRule:
    if not isinstance(item, dict):
        raise ValueError(f"rule {number}: is not a table")
    name = item.get("name")
    label = f"rule {name.strip()!r}" if isinstance(name, str) and name.strip() else f"rule {number}"
    for key in item:
        if key not in _RULE_KEYS:
            raise ValueError(f"{label}: unknown key {key!r}")
    name = _text(item, "name", label)
    if ("sender" in item) == ("domain" in item):
        raise ValueError(f"{label}: give exactly one of 'sender' and 'domain'")
    category = _text(item, "category", label)
    if category not in CATEGORIES:
        raise ValueError(f"{label}: unknown category {category!r}")
    importance = _text(item, "importance", label)
    if importance not in RULE_IMPORTANCE:
        raise ValueError(
            f"{label}: importance {importance!r} is not allowed "
            f"(use one of {', '.join(RULE_IMPORTANCE)})")
    if "sender" in item:
        sender = _text(item, "sender", label)
        # Compare the raw value: a display name or stray space would never match a mail.
        if parseaddr(item["sender"])[1] != item["sender"]:
            raise ValueError(f"{label}: 'sender' must be a plain address, without a name or spaces")
        sender = sender.lower()
        if sender.count("@") != 1 or sender.startswith("@") or sender.endswith("@"):
            raise ValueError(f"{label}: 'sender' is not an address")
        return SenderRule(name, sender, None, category, importance)
    domain = _text(item, "domain", label).lower()
    raw = item["domain"]
    if raw != raw.strip() or raw.startswith(".") or raw.endswith("."):
        raise ValueError(f"{label}: 'domain' must not start or end with a dot or a space")
    if "@" in domain:
        raise ValueError(f"{label}: 'domain' must not contain '@'")
    return SenderRule(name, None, domain, category, importance)


def parse_rules(data: dict) -> list[SenderRule]:
    """Checks decoded rule file data.

    Args:
        data: The decoded TOML. Rules are an array of tables named ``rule``.

    Returns:
        The rules in file order. Empty if the file has none.

    Raises:
        ValueError: If a rule breaks a check. The message names the rule.
    """
    unknown = set(data) - {"rule"}
    if unknown:
        raise ValueError(f"unknown key in rules file: {sorted(unknown)[0]!r}")
    items = data.get("rule", [])
    if not isinstance(items, list):
        raise ValueError("'rule' must be an array of tables")
    rules: list[SenderRule] = []
    names, targets = set(), set()
    for number, item in enumerate(items, 1):
        rule = _parse_rule(item, number)
        target = rule.sender or rule.domain
        if rule.name in names:
            raise ValueError(f"rule {rule.name!r}: name is used twice")
        if (rule.sender is None, target) in targets:
            raise ValueError(f"rule {rule.name!r}: {target!r} is named in another rule")
        names.add(rule.name)
        targets.add((rule.sender is None, target))
        rules.append(rule)
    return rules


def load_rules(path: str | Path) -> list[SenderRule]:
    """Reads and checks a rule file.

    Raises:
        ValueError: If the file cannot be read, is not valid TOML, or breaks a check.
    """
    path = Path(path)
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except OSError as e:
        raise ValueError(f"cannot read rule file {path}: {e.strerror or e}") from e
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as e:
        raise ValueError(f"rule file {path} is not valid TOML: {e}") from e
    return parse_rules(data)


def match(rules: list[SenderRule], from_addr: str | None) -> SenderRule | None:
    """Finds the rule for a sender.

    Args:
        rules: Checked rules.
        from_addr: The ``From`` header value. Only the address is used.

    Returns:
        The matching rule (an address rule before a domain rule), or None.
    """
    address = parseaddr(from_addr or "")[1].lower()
    if address.count("@") != 1:
        return None
    domain = address.rsplit("@", 1)[1]
    by_domain = None
    for rule in rules:
        if rule.sender == address:
            return rule
        if by_domain is None and rule.domain == domain:
            by_domain = rule
    return by_domain
