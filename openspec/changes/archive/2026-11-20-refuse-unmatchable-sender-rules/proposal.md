## Why

Some rule values pass the start check but can never match a mail. A `sender` copied whole
from a `From` header (`LinkedIn <jobs@linkedin.com>`) or a `domain` like `.example.com`
does nothing, and nobody is told. Closes #24 (follow-up of finding R1 in #11).

Scope extended at Gate 3 by the human: probes showed more values that are accepted
today and can never match (`exa mple.com`, `example..com`, `http://example.com`,
`a@x..com`, `a b@x.com`), and the checks are hard to read.

## What Changes

- Refuse a `sender` that is not a plain address (the part of it that `parseaddr` reads must be the whole value).
- Refuse a `domain` that is not a valid host name: each label is 1-63 characters of `a-z`, `0-9` and `-`, does not start or end with `-`, and there are at least two labels. This also refuses a leading or trailing `.`.
- The domain part of a `sender` gets the same host name check. Its local part must not be empty or contain whitespace.
- One whitespace rule: only `name` is trimmed. A `sender`, `domain`, `category` or `importance` with leading or trailing whitespace is refused; the error names the rule and the field.
- Rule names are compared without regard to case: `Ads` and `ads` are duplicates.
- The start error names the rule, as for the other checks. The rule name is trimmed before it goes into the error label (nit N1 from #11).
- Refactor: one parse helper per field; `SenderRule` holds `kind` (`sender` or `domain`) and `value` instead of two optional fields; importance is a `Literal`.
- Rule file errors use their own exception `RuleFileError` (a `ValueError`). The CLI catches only that one, so a bug is no longer reported as a broken rule file.

## Capabilities

### New Capabilities

### Modified Capabilities
- `sender-rules`: the "Rule file is checked at start" requirement refuses more kinds of value and compares names without regard to case.

## Impact

- Code: `mail_informer/analysis/sender_rules.py`, `mail_informer/cli.py`, and the `SenderRule(...)` calls in `tests/test_sender_rules.py`, `tests/test_analyzer.py`, `tests/test_evaluate.py`.
- A rule file that holds such a value now stops `analyze` and `evaluate` at start. Before, it started and the rule did nothing.
- No new dependency, migration, or ADR. Logs still never show sender addresses.

## Non-goals

- Internationalized domain names in Unicode form; write the `xn--` form instead.
- Checking that a domain exists or has mail records.
- Changing how mails are matched.
