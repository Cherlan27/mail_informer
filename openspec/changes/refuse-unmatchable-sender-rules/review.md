# Review: refuse-unmatchable-sender-rules

## Round 1

Base `origin/main` @ 27d028c · Head c9e6f20 · 2026-11-18 · Reviewer: claude-opus-5-5

### Summary
The change does what issue #24 asks: it refuses a non-plain `sender`, refuses a `domain` that has a dot or whitespace at either end, and trims the name in the error label. All three new scenarios have tests that fail without the code, and no existing test was changed. I found no defects.

### Verification
| step | result |
|---|---|
| `make check` (TEST_DATABASE_URL on 55432), run 1 | ✅ pytest passed; openspec 10 passed, 0 failed |
| `make check`, run 2 | ✅ 452 passed, 1 warning; openspec 10 passed, 0 failed |
| `trail check` | ✅ no conflicts |
| Probe: `load_rules('sender_rules.toml.example')` | ✅ 2 rules, example still loads |
| Probe: `parseaddr` on `"a b"@x.com`, `jobs+x@x.com`, `mailto:a@x.com`, `a@b@c.com` | quoted and plus addresses are kept; `mailto:` and double `@` are refused. Same parser as `match`, so the two stay consistent |
| Live stack: `D:/Projects/mail_informer/config/` and `.env` | no rule file, `SENDER_RULES_PATH` not set, so deploying this does not stop the analyzer |

Scenario → test: "Sender is not a plain address" → `test_sender_that_is_not_a_plain_address_is_refused`, `test_plain_address_is_still_accepted`; "Domain with a dot or whitespace at an end" → `test_domain_with_dot_or_whitespace_at_an_end_is_refused`; "Rule name with surrounding whitespace" → `test_error_label_uses_the_trimmed_name`. Extra checks (layering, read-only, idempotency, migrations, secrets, deps) are not touched: the diff only changes `sender_rules.py`, which has no I/O outside `load_rules`.

### Findings

None.

### Nits
- N1 · `mail_informer/analysis/sender_rules.py:56` — `sender` is set from `_text`, then set again with `.lower()` at line 60. One `sender = _text(...).lower()` after the `parseaddr` check reads more simply.
