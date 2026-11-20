"""Sender rules: rate mails from known bulk senders without the model.

A rule can only lower importance, so a rule never causes a notification.
Only ``load_rules`` does I/O.
"""

import re
import tomllib
from dataclasses import dataclass
from email.utils import parseaddr
from pathlib import Path
from typing import Literal, cast, get_args

from .rules import CATEGORIES

Kind = Literal["sender", "domain"]
Importance = Literal["ignore", "normal"]

RULE_IMPORTANCE = get_args(Importance)
_RULE_KEYS = {"name", "sender", "domain", "category", "importance"}
_HOST_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")


class RuleFileError(ValueError):
    """The rule file is broken. The message names the rule and the field."""


@dataclass(frozen=True)
class SenderRule:
    """One rule. ``value`` is a plain address or a domain, in lower case."""

    name: str
    kind: Kind
    value: str
    category: str
    importance: Importance


def _trimmed_name(item: dict) -> str:
    name = item.get("name")
    return name.strip() if isinstance(name, str) else ""


def _text(item: dict, key: str, label: str) -> str:
    """Returns the value as written. Only the rule name may have spaces around it."""
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RuleFileError(f"{label}: '{key}' is missing or not text")
    if value != value.strip():
        raise RuleFileError(f"{label}: '{key}' must not start or end with whitespace")
    return value


def _is_host_name(value: str) -> bool:
    labels = value.split(".")
    return len(labels) >= 2 and all(_HOST_LABEL.fullmatch(label) for label in labels)


def _parse_name(item: dict, label: str) -> str:
    name = _trimmed_name(item)
    if not name:
        raise RuleFileError(f"{label}: 'name' is missing or not text")
    return name


def _parse_category(item: dict, label: str) -> str:
    category = _text(item, "category", label)
    if category not in CATEGORIES:
        raise RuleFileError(f"{label}: unknown category {category!r}")
    return category


def _parse_importance(item: dict, label: str) -> Importance:
    importance = _text(item, "importance", label)
    if importance not in RULE_IMPORTANCE:
        raise RuleFileError(
            f"{label}: importance {importance!r} is not allowed "
            f"(use one of {', '.join(RULE_IMPORTANCE)})")
    return cast(Importance, importance)


def _parse_sender(item: dict, label: str) -> str:
    sender = _text(item, "sender", label)
    # parseaddr must read the whole value: a display name or other text would never match.
    # The message does not repeat the value, so an address never reaches a log.
    if parseaddr(sender)[1] != sender:
        raise RuleFileError(f"{label}: 'sender' must be a plain address, without a name or spaces")
    local, at, domain = sender.lower().partition("@")
    if (not at or not local or any(c.isspace() for c in local)
            or not _is_host_name(domain)):
        raise RuleFileError(f"{label}: 'sender' is not a valid address")
    return f"{local}@{domain}"


def _parse_domain(item: dict, label: str) -> str:
    domain = _text(item, "domain", label).lower()
    if not _is_host_name(domain):
        raise RuleFileError(f"{label}: 'domain' is not a valid host name")
    return domain


def _parse_rule(item: object, number: int) -> SenderRule:
    if not isinstance(item, dict):
        raise RuleFileError(f"rule {number}: is not a table")
    name = _trimmed_name(item)
    label = f"rule {name!r}" if name else f"rule {number}"
    unknown = sorted(item.keys() - _RULE_KEYS)
    if unknown:
        raise RuleFileError(f"{label}: unknown keys {unknown}")
    name = _parse_name(item, label)
    if ("sender" in item) == ("domain" in item):
        raise RuleFileError(f"{label}: give exactly one of 'sender' and 'domain'")
    category = _parse_category(item, label)
    importance = _parse_importance(item, label)
    if "sender" in item:
        return SenderRule(name, "sender", _parse_sender(item, label), category, importance)
    return SenderRule(name, "domain", _parse_domain(item, label), category, importance)


def parse_rules(data: dict) -> list[SenderRule]:
    """Checks decoded rule file data.

    Args:
        data: The decoded TOML. Rules are an array of tables named ``rule``.

    Returns:
        The rules in file order. Empty if the file has none.

    Raises:
        RuleFileError: If a rule breaks a check. The message names the rule.
    """
    unknown = set(data) - {"rule"}
    if unknown:
        raise RuleFileError(f"unknown key in rules file: {sorted(unknown)[0]!r}")
    items = data.get("rule", [])
    if not isinstance(items, list):
        raise RuleFileError("'rule' must be an array of tables")
    rules: list[SenderRule] = []
    names: set[str] = set()
    targets: set[tuple[str, str]] = set()
    for number, item in enumerate(items, 1):
        rule = _parse_rule(item, number)
        if rule.name.casefold() in names:
            raise RuleFileError(f"rule {rule.name!r}: name is used twice")
        if (rule.kind, rule.value) in targets:
            # Not the value itself: for a sender it is an address.
            raise RuleFileError(f"rule {rule.name!r}: the {rule.kind} is named in another rule")
        names.add(rule.name.casefold())
        targets.add((rule.kind, rule.value))
        rules.append(rule)
    return rules


def load_rules(path: str | Path) -> list[SenderRule]:
    """Reads and checks a rule file.

    Raises:
        RuleFileError: If the file cannot be read, is not valid TOML, or breaks a check.
    """
    path = Path(path)
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except OSError as e:
        raise RuleFileError(f"cannot read rule file {path}: {e.strerror or e}") from e
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as e:
        raise RuleFileError(f"rule file {path} is not valid TOML: {e}") from e
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
        if rule.kind == "sender" and rule.value == address:
            return rule
        if by_domain is None and rule.kind == "domain" and rule.value == domain:
            by_domain = rule
    return by_domain
