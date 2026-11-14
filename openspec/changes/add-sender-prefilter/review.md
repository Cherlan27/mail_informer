# Review: add-sender-prefilter

## Round 1

Base `main` @ 2215fa3 · Head 13df5a1 · 2026-11-14 · Reviewer: claude-opus-5-5

### Summary
The change matches the proposal, design and all 21 scenarios; each scenario has a named test, and the analyzer split (rules first, then model) is proved by `test_rule_mails_without_a_model_server`. Layering, read-only access, idempotent writes (`save_result` ON CONFLICT), no migration, no new dependency and no secrets in logs all hold. One MINOR finding on rule value checks; no blocker.

### Verification
| step | result |
|---|---|
| `make check` (with `TEST_DATABASE_URL`) | ✅ pytest passed, openspec 9/9 passed |
| `pytest -q -rs` | ✅ 441 passed, 0 skipped |
| `POSTGRES_PASSWORD=x ANALYZER_MODEL=m HA_WEBHOOK_URL=http://x docker compose config` | ✅ analyzer gets `SENDER_RULES_PATH: ""` and `/config` mount |
| `trail check` | ✅ no conflicts |

### Findings

#### R1 · MINOR · `mail_informer/analysis/sender_rules.py:56-62`
`sender` and `domain` values are only checked for `@`. A value copied from a `From` header (`sender = "LinkedIn <jobs@linkedin.com>"`) or a wildcard-style domain (`domain = ".example.com"`) is accepted but can never match. When the owner writes such a rule, `analyze` starts fine, the rule silently catches nothing, and those mails keep going to the model. Proof: `parse_rules` accepted both values and `match` returned `None` for `jobs@x.com` and `a@sub.example.com` (python probe). Fail-safe (today's behavior), so no data or safety impact. Fix: refuse a `sender` unless `parseaddr(value)[1] == value`, and a `domain` with a leading/trailing `.` or whitespace.

- Recommendation: defer — fail-safe, and `evaluate` shows low hit counts; cheap to add with a test later.
- Decision: pending
- Status: open

### Nits
- N1 · `mail_informer/analysis/sender_rules.py:40` — the error label uses the unstripped name (`rule ' x '`), the rule itself stores `x`.
