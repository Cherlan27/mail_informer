## Context

See proposal.md. All checks live in `mail_informer/analysis/sender_rules.py`; `analyzer.py`
and `evaluate.py` only call `match` and read `name`, `category`, `importance`.

## Decisions

**Host name check with one regex per label, after lower-casing.** Split on `.`, need at least
two labels, each matching `[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?`. One check covers a dot at an
end, empty labels, spaces, `/`, `:` and `@`. Rejected: `ipaddress`/`idna` or a URL parser,
which accept values that never match a `From` domain or add a dependency.

**Sender: split at the one `@`, check the domain part with the same host check, refuse an
empty local part or whitespace in it.** The host check alone would accept `a b@x.com`, since
`parseaddr` keeps it whole. Rejected: a full RFC 5322 local-part grammar; too large for the gain.
The `parseaddr` check from #24 stays.

**Refuse surrounding whitespace instead of trimming it.** One rule for every field except
`name`, so the value in the file is the value that is matched. Rejected: trim all fields
silently; it hides a typo and is what made `domain` and `category` behave differently.

**Names compared with `casefold()`; the stored name keeps its case.** Rejected: store the name
in lower case; it would change the `rule: <name>` text in results and logs.

**`SenderRule(name, kind, value, category, importance)` with `kind: Literal["sender", "domain"]`.**
Duplicate targets are found by the key `(kind, value)`. Rejected: keep two optional fields;
every reader must know that exactly one is set.

**`RuleFileError(ValueError)` for every refusal.** It stays a `ValueError`, so existing
`pytest.raises(ValueError)` tests still pass unchanged. `cli._load_sender_rules` catches only
`RuleFileError`. Rejected: an unrelated base class; it would force test changes.

**One `_parse_<field>` helper per field, each returns the finished value.** Unknown keys are
found by `item.keys() - _RULE_KEYS` and reported sorted.

## Risks / Trade-offs

- [A rule file that starts today is refused after the update] → The error names the rule and
  the field; the owner fixes the file. No data is touched, no migration. Rollback is the old image.
- [Unicode domains are refused] → Write the `xn--` form; noted as a non-goal.
- New error messages keep the form `rule '<name>': '<field>' ...` (existing tests match on it)
  and do not quote the refused sender value. No new log line is added.
