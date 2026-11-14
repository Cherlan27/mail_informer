## Context

See proposal.md (Why). Current state: `run_analysis` picks waiting mails, calls `classify` for each, applies the bulk guard, and stores the result with `save_result` under `PROMPT_VERSION`. The analyzer container does not mount `secrets/` (llm-analysis decision 1). `evaluate` runs the model on labeled mails and writes nothing.

## Goals / Non-Goals

**Goals:** a cheap, local, reviewable pre-filter that can only lower a mail's importance.

**Non-Goals:** see proposal.md. Also no match on Gmail labels or headers other than `From`.

## Decisions

### 1. Match on the sender only (exact address or exact domain)
Address from `From` via `email.utils.parseaddr`, lower-cased. Domain rules match the exact domain, not subdomains; address rules win over domain rules.
- Why: the owner can see and predict every hit. Exact domains stop `example.com` from also swallowing `billing.example.com`.
- Rejected: `is_bulk` / `List-Unsubscribe` or Gmail `CATEGORY_PROMOTIONS`. Invoices and bank mails often come through bulk mailers; the label exists only for Gmail and is not stored.
- Rejected: subdomain match. Wider hits for little gain; a subdomain is one more rule.

### 2. Rule results use the current `PROMPT_VERSION`; no re-run on rule change
The rule result is a normal `done` row for `(gmail_id, PROMPT_VERSION)`, written with `save_result` (`model = 'rule'`, `reason = 'rule: <name>'`). Work selection, the notifier and the healthcheck need no change.
- A rule change affects only mails still waiting. A new `PROMPT_VERSION` re-runs everything anyway, and the rules then apply again.
- Rejected: a separate rule version in the key. Needs a migration and touches `PROMPT_VERSION`, a non-goal.
- Rejected: re-rate old results on rule change. Would overwrite model results and needs a rule hash; old mails are already rated.

### 3. Separate TOML file named by `SENDER_RULES_PATH`
Format: an array of tables `[[rule]]` with `name`, `sender` or `domain`, `category`, `importance`. Read with `tomllib`. Compose mounts `./config` read-only at `/config` in the analyzer; `SENDER_RULES_PATH` defaults to empty.
- Rejected: a section in `accounts.toml`. That file lives in `secrets/` with passwords, which the analyzer must not mount.
- Rejected: an environment variable with a list. Hard to read and review for more than a few rules.

### 4. Strict check at start, in a pure module
`analysis/sender_rules.py` holds `SenderRule`, `parse_rules(data)` (pure, raises `ValueError` naming the rule) and `match(rules, from_addr)` (pure); `load_rules(path)` only reads the file. `cli._analyze` and `cli._evaluate` load the rules before they open the database; an error becomes `RuntimeError` and exit code non-zero. Allowed importance is a separate constant `RULE_IMPORTANCE = ("ignore", "normal")`.
- Rejected: skip a broken rule and go on. A typo would silently send mails to the model or, worse, a half-read file would hide its mistake.

### 5. Rules first, then the model, within one pass
`run_analysis` takes the rules as a new argument (default: none). It splits the picked mails: rule hits are stored first, then the model rates the rest. So a model server outage does not block rule hits. The pass limit (50) counts both. The log line becomes `"%d mails analyzed, %d by rules (%s)"` with per-rule counts by name.
- Rejected: check the rule inside the per-mail loop. An outage on an earlier mail would end the pass before later rule hits.

### 6. `evaluate` adds a rule part and keeps the model part
`evaluate` gets the rules as an argument. It still runs the model on every label (decision of llm-analysis 9: measure the model). `Report` gets `rule_hits`, `rule_correct` (category and importance both match) and `rule_hits_important` (IDs). `format_report` prints the rule part only when rules are given.
- Rejected: skip the model for rule hits. The model numbers would change with the rule file and stop being comparable.

### ADR, dependency, migration
None. The pre-filter is a new pure module inside the existing `analysis/` layer, not a new layer or service. `tomllib` is standard library. `analyses.model` is free text, so `'rule'` fits without a schema change.

## Risks / Trade-offs

- [Forged `From` of a ruled sender] → The mail is rated `ignore`/`normal` and never reaches the phone. Rules can only lower, so the worst case is a missed notification for a spoofed mail, never a false one. The mail stays in the archive.
- [A domain rule swallows invoices or security mails of the same domain] → Prefer address rules. `evaluate` lists caught mails labeled `important`/`urgent`; the per-rule log count shows a rule that catches too much.
- [Crash mid-pass] → Each rule result is its own write, idempotent through `ON CONFLICT`. The next pass continues.
- [Duplicate passes] → The analyzer lock is unchanged.
- [Rule file deleted while configured] → Next start fails, analyzer becomes `unhealthy` after 30 minutes. Intended: fail loud.

## Migration Plan

Existing data is untouched. Deploy: add `config/sender_rules.toml`, set `SENDER_RULES_PATH=/config/sender_rules.toml` in `.env`, run `docker compose up -d --build`. Rollback: unset `SENDER_RULES_PATH`. Rule rows stay valid `done` results; to have them re-rated by the model, delete rows `WHERE model = 'rule'` by hand.
