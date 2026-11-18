## Why

Some rule values pass the start check but can never match a mail. A `sender` copied whole
from a `From` header (`LinkedIn <jobs@linkedin.com>`) or a `domain` like `.example.com`
does nothing, and nobody is told. Closes #24 (follow-up of finding R1 in #11).

## What Changes

- Refuse a `sender` that is not a plain address (the part of it that `parseaddr` reads must be the whole value).
- Refuse a `domain` with a leading or trailing `.` or with leading or trailing whitespace. The check looks at the value as written, before any trimming.
- The start error names the rule, as for the other checks.
- Trim the rule name before it goes into the error label (nit N1 from #11).

## Capabilities

### New Capabilities

### Modified Capabilities
- `sender-rules`: the "Rule file is checked at start" requirement refuses two more kinds of value.

## Impact

- Code: `mail_informer/analysis/sender_rules.py` and `tests/test_sender_rules.py`.
- A rule file that holds such a value now stops `analyze` and `evaluate` at start. Before, it started and the rule did nothing.
- No new dependency, migration, or ADR.

## Non-goals

- Checking that a domain has valid labels (`example..com`, spaces inside).
- Changing how mails are matched.
