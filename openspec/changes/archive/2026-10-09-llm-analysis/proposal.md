## Why

The archive in Postgres now fills with real mail, but most of it is newsletters, job alerts, and marketing. Nobody can read all of it. A local LLM can sort the mails by importance and summarize the important ones, so a later stage can notify the phone about the few mails that matter. This change builds the analysis stage. It does not send any notification.

## What Changes

- New `analyzer` container. It reads mails that are not analyzed yet, asks a small local model, and writes the results to the database. It runs on the same Docker Compose stack as the poller.
- Two steps per mail:
  1. **Classify** every mail: a category and an importance level (`ignore`, `normal`, `important`, `urgent`). The model gets sender, subject, and the first part of the body.
  2. **Summarize** only mails rated `important` or `urgent`: a short German summary (1-2 sentences).
- The model runs in Ollama on the Windows host with the GPU (RTX 5090). The analyzer reaches it over HTTP. The model answers in a fixed JSON schema. Which model to use is decided by a measurement on hand-labeled real mails, not by assumption.
- New tables, separate from `messages`: `analyses` holds category, importance, summary, a short reason, model name, prompt version, status, and attempt count. The archive in `messages` stays unchanged.
- Failed analyses are retried a limited number of times, then marked `failed`. A mail never blocks the others.
- **Safety rule: the model output is data only.** The model has no tools and triggers no action. Later stages read only the enum fields, never the free text.
- Deterministic guard in code (not in the prompt): a mail that looks like bulk mail (has a `List-Unsubscribe` header) can never be `urgent`. It is lowered to `important`. This limits the damage of a newsletter that tries to talk the model into a high rating.
- The poller stores the `List-Unsubscribe` presence as a flag on each mail, with a new migration.
- Urgent topics the prompt must recognize: security or bank alerts, personal mail from real people, work and customer mail, appointments with a deadline, and replies from authorities (approval or rejection).
- The prompt and the schema are versioned (`prompt_version`) so a re-analysis with a new model or prompt is possible and results can be compared.

## Non-goals

- No notification to Home Assistant or the phone. That is the next change (`ha-notifications`).
- No bundling or digest of messages.
- No automatic actions of any kind based on mail content.
- No changes to Gmail access. It stays read-only.
- No re-analysis of old mails on a schedule. A manual re-run is possible, but not part of this change.
- No cloud model. Mail content stays on this machine.

## Capabilities

### New Capabilities
- `mail-analysis`: Classifying mails, summarizing important ones, retry and failure handling, the bulk-mail guard, and the rule that model output never triggers actions.
- `analysis-storage`: Schema and storage rules for analysis results, prompt versions, and analysis status, kept separate from the archived mail.

### Modified Capabilities
- `mail-storage`: Each mail also records whether it is bulk mail (`List-Unsubscribe` present). The requirement on the analysis status changes: the analyzer, not only the archive, owns the analysis state, and the poller still never sets it.
- `poller-runtime`: The Compose stack includes the analyzer container, and the analyzer needs access to the model server on the host.

## Impact

- New code: analyzer package or module, prompt and schema files, a model client (HTTP to Ollama), repository functions for the new tables.
- New migrations: `analyses` table, bulk flag on `messages`. Existing migrations are not edited.
- `docker-compose.yml`: new `analyzer` service (non-root, healthcheck, access to the host model server).
- `parsing.py` and `db.py` change a little to store the bulk flag.
- New dependency: an HTTP client library, only if the standard library is not enough. Pinned in `constraints.txt`.
- External requirement: Ollama installed on the host, with a model pulled and the GPU in use.
- Tests: unit tests with a fake model client, database tests, and an evaluation script that compares models on hand-labeled mails.
- Privacy: mail content is sent only to the local model server and never leaves the machine.
