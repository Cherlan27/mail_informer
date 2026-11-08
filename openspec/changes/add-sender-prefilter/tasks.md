Tasks marked (Postgres) need a running Postgres and `TEST_DATABASE_URL`; without it those tests are skipped, so run them with it set.

## 1. Rule file and matching (pure module)

- [ ] 1.1 Test, then code `parse_rules` in `analysis/sender_rules.py`: valid file gives rules; refusals for "Rule raises importance", "Unknown category", "Address and domain in one rule", "Duplicate rule", "Unknown key". Each error names the rule.
- [ ] 1.2 Test, then code `load_rules(path)`: "File missing" and invalid TOML raise `ValueError`.
- [ ] 1.3 Test, then code `match(rules, from_addr)`: "Exact address", "Domain", "Subdomain does not match", "Address rule wins", "No sender address".

## 2. Setting and start check

- [ ] 2.1 Test, then code `Config.sender_rules_path` from `SENDER_RULES_PATH` (default empty) in `config.py`.
- [ ] 2.2 Test, then code the start check in `cli._analyze`: a broken rule file exits non-zero before the database is opened ("Rule raises importance" at the CLI level, no mail read).

## 3. Analyzer pre-filter (Postgres)

- [ ] 3.1 Test, then code: `run_analysis` with no rules behaves as before ("No rule file configured").
- [ ] 3.2 Test, then code: rule hits are stored with `model = 'rule'` and a reason naming the rule, and the fake model gets no request for them ("Rule result is stored").
- [ ] 3.3 Test, then code: "Pending result is replaced".
- [ ] 3.4 Test, then code: rule hits are stored before model calls ("Rule mails without a model server").
- [ ] 3.5 Test, then code: "Rule added later" leaves an existing `done` result unchanged.
- [ ] 3.6 Test, then code the pass log with totals and per-rule counts and no sender address ("Pass with rule hits", via `caplog`).
- [ ] 3.7 Wire the loaded rules from `cli._analyze` into `run_analysis`; test with a rule file in `tmp_path`.

## 4. Evaluation (Postgres)

- [ ] 4.1 Test, then code the rule part of `Report` and `evaluate`: "Rule catches an important mail".
- [ ] 4.2 Test, then code: "Model numbers unchanged" (same fake model, with and without rules).
- [ ] 4.3 Test, then code `format_report`: "No rules" prints no rule part; with rules it prints hits, correct, and the important/urgent IDs.
- [ ] 4.4 Test, then code `cli._evaluate`: loads rules from the setting; "Evaluation with a broken rule file" makes no model call.

## 5. Deployment and docs

- [ ] 5.1 `docker-compose.yml`: pass `SENDER_RULES_PATH: ${SENDER_RULES_PATH:-}` and mount `./config:/config:ro` in the analyzer only. Check with `docker compose config` (needs Docker).
- [ ] 5.2 Add `sender_rules.toml.example` and a README section (format, allowed importance, exact-domain match, rollback by deleting `model = 'rule'` rows).

## 6. Verification

- [ ] 6.1 Run `make check` with `TEST_DATABASE_URL` set (needs Postgres); it passes twice in a row.
- [ ] 6.2 Manual check: run `evaluate` with the example rule file against a throwaway database and read the rule part of the report.
