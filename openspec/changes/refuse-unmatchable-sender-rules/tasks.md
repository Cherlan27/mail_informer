## 1. Refuse unmatchable values

- [x] 1.1 Test, then code: scenario "Sender is not a plain address" (`LinkedIn <jobs@linkedin.com>` is refused, a plain address still passes).
- [x] 1.2 Test, then code: scenario "Domain with a dot or whitespace at an end" (`.example.com`, `example.com.`, ` example.com` are refused; the check uses the value before trimming).
- [x] 1.3 Test, then code: scenario "Rule name with surrounding whitespace" (the error label uses the trimmed name).

## 2. Verification

- [x] 2.1 Run `make check` (needs Postgres through `TEST_DATABASE_URL`); it passes twice in a row.

## 3. Scope extension from Gate 3: stricter values

- [x] 3.1 Test, then code: scenarios "Domain is not a valid host name" and "Valid domain still passes" (host name check per label, after lower-casing). This scenario replaces the one of 1.2; the 1.2 test stays.
- [x] 3.2 Test, then code: scenario "Sender with an invalid address part" (`a b@x.com`, `a@.com`, `a@x..com` refused; the `parseaddr` check stays).
- [x] 3.3 Test, then code: scenario "Value with surrounding whitespace" for sender, domain, category and importance; the error names the rule and the field.
- [x] 3.4 Test, then code: scenario "Rule names that differ only in case" (`Ads` and `ads` are duplicates; the stored name keeps its case).

## 4. Scope extension from Gate 3: refactor and error type

- [x] 4.1 Test, then code: scenario "Other errors are not reported as a broken rule file". Add `RuleFileError(ValueError)`, raise it from `parse_rules`/`load_rules`, catch only it in `cli._load_sender_rules`. Update the `Raises:` sections.
- [x] 4.2 Test, then code: scenario "Several unknown keys" (found by `item.keys() - _RULE_KEYS`, reported sorted).
- [x] 4.3 Refactor with all tests green: one `_parse_<field>` helper per field that returns the finished value; no raw-vs-trimmed double read, no double assignment of `sender`, no duplicated name logic in the label.
- [x] 4.4 Refactor: `SenderRule(name, kind, value, category, importance)` with `kind: Literal["sender", "domain"]` and importance `Literal["ignore", "normal"]`. Update `match`, the duplicate check in `parse_rules` (key `(kind, value)`), and the `SenderRule`/module docstrings. Only the `SenderRule(...)` calls in `tests/test_sender_rules.py`, `tests/test_analyzer.py` and `tests/test_evaluate.py` may change; no other test is changed, deleted or loosened.

## 5. Verification (extension)

- [x] 5.1 Run `make check` (needs Postgres through `TEST_DATABASE_URL`, a throwaway container on a free port); it passes twice in a row.
