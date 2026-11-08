## Why

The analyzer sends every new mail to the model. Most mails are newsletters, job alerts and advertising from a few known senders. Each costs a model call and, with a remote model server, sends mail content off the machine. Closes #11.

## What Changes

- New optional sender rule file (TOML), named by `SENDER_RULES_PATH`. No setting means no rules and today's behavior.
- A rule matches the sender's exact address or its domain. It sets a category from the known list and the importance `ignore` or `normal`. `important` and `urgent` are refused, so a rule can never cause a phone notification.
- The analyzer checks the rules before the model call. A matching mail gets a `done` result with `model = 'rule'` and a reason that names the rule. No model call is made for it.
- An invalid rule file stops `analyze` and `evaluate` at start, before any mail is read.
- Each pass logs how many mails rules decided, per rule name.
- `evaluate` reports how many labeled mails the rules would catch and lists those labeled `important` or `urgent`.

## Non-goals

- No rules on subject or body text.
- No learning or automatic rule creation from past results.
- No per-account rule sets.
- No change to the model prompts, schemas or `PROMPT_VERSION`.
- No re-rating of mails that already have a result when the rules change.

## Capabilities

### New Capabilities
- `sender-rules`: the rule file, its checks, matching, the stored rule result, the pass log, and the rule report of `evaluate`.

### Modified Capabilities
None. Mails without a rule match follow the `mail-analysis` and `analysis-storage` specs unchanged.

## Impact

- Code: new pure module `mail_informer/analysis/sender_rules.py`; changes in `analysis/analyzer.py`, `analysis/evaluate.py`, `config.py`, `cli.py`.
- Deployment: `docker-compose.yml` passes `SENDER_RULES_PATH` and mounts `./config` read-only into the analyzer (not `secrets/`). README and an example rule file.
- No migration, no new dependency (`tomllib` is in the standard library), no ADR.
