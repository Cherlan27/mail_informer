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

## Round 2

Base af46c65 · Head 37cd87a · 2026-11-20 · Reviewer: claude-opus-5-5 · Scope: Gate 3 extension (tasks 3-5)

### Summary
The extension matches the proposal, design and delta spec; `make check` passes twice and no test was deleted, skipped or loosened. The one non-`SenderRule(...)` test edit (`test_plain_address_is_still_accepted`: `.sender` → `.value`) is forced by task 4.4, which removes the `sender` field; the expected value is unchanged and the test still fails when lower-casing is removed (M14). The duplicate-target message no longer quotes the value; the spec only asks for a refusal, and design.md (Risks) and the proposal ("Logs still never show sender addresses") cover the change; `test_duplicate_domain`/`test_duplicate_address` still pass and the kind-in-key mutation (M12) fails them.

### Verification
| step | result |
|---|---|
| `make check` (TEST_DATABASE_URL on 55432), run 1 | ✅ pytest passed; openspec 10 passed, 0 failed |
| `make check`, run 2 | ✅ pytest passed; openspec 10 passed, 0 failed |
| `pytest -q` | ✅ 487 passed, 1 warning |
| `trail check` | ✅ no conflicts |
| Mutation probes on a scratchpad copy, `tests/test_sender_rules.py` + `tests/test_cli_sender_rules.py` | see below |

Scenario → test (mutation that makes it fail): "Rule names that differ only in case" → `test_names_that_differ_only_in_case_are_duplicates` (no casefold on add: 1 failed); "Several unknown keys" → `test_several_unknown_keys_are_named_in_sorted_order` (no `sorted`: fails on 4 of 6 hash seeds); "Sender with an invalid address part" → `test_sender_with_an_invalid_address_part_is_refused` (no host check: 4 failed; no local whitespace check: 1 failed); "Domain is not a valid host name" → `test_domain_that_is_not_a_host_name_is_refused` (no host check: 16 failed; `{0,62}`: 1 failed; one label allowed: 2 failed); "Valid domain still passes" → `test_valid_domain_is_stored_in_lower_case` (no `.lower()`: 1 failed); "Value with surrounding whitespace" → `test_value_with_surrounding_whitespace_is_refused` (no strip check: 4 failed); "Other errors are not reported as a broken rule file" → `test_other_errors_are_not_reported_as_a_broken_rule_file` (catch `ValueError`: 3 failed). Extra checks: layering unchanged (`cli.py` only swaps the caught type); no I/O, SQL, scope, migration or dependency change. Round 1 nit N1 (double assignment of `sender`) is gone with the refactor.

### Findings

#### R1 · MINOR · `mail_informer/analysis/sender_rules.py:86`
The `parseaddr` check has no test that fails without it. Removing the line (probe M11) leaves all 75 rule tests green: every current non-plain case is also refused by the local-part or host check. It is still the only check that refuses a value with a comment, for example `jobs(news)@linkedin.com` or `(x)jobs@linkedin.com` (probe: refused only by the "plain address" message; `parseaddr` reads `jobs@linkedin.com`). When someone drops the line as redundant, such a rule is accepted and never matches, and no test notices. Fix: add `"jobs(news)@linkedin.com"` to the parametrize list of `test_sender_that_is_not_a_plain_address_is_refused`.

- Recommendation: fix — one test value, pins a design decision ("the `parseaddr` check stays").
- Decision: fix (human approved the recommendation at Gate 2)
- Status: open

### Nits
- N2 · `tests/test_sender_rules.py` `test_names_that_differ_only_in_case_are_duplicates` — only the order `Ads`, `ads` is tested; with `casefold()` dropped from the lookup only (probe M1) it stays green. A second case `ads`, `Ads` closes that.
  - Decision: fix (human chose to include it at Gate 2)
  - Status: open
- N3 · `tests/test_sender_rules.py` `test_several_unknown_keys_are_named_in_sorted_order` — with two keys, the test passes without `sorted` on about half of the hash seeds (2 of 6). Four or five unknown keys make it fail almost always.
  - Decision: fix (human chose to include it at Gate 2)
  - Status: open
- N4 · `README.md:50` — "a unique `name`" does not say that names are compared without regard to case, and that values other than `name` must not have surrounding spaces.
  - Decision: fix (human chose to include it at Gate 2)
  - Status: open
