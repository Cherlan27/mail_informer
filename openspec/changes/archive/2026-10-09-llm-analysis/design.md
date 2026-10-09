## Context

See proposal.md for the motivation. Current state:

- The poller runs one-shot every 30 minutes (supercronic), writes to `messages`, and keeps a sync point in `sync_state`. Migrations are numbered SQL files, applied by `db.migrate` at the start of a run.
- `messages.analysis_status` exists, but nothing ever changes it. The archive has 32 mails, mostly newsletters, alerts, and marketing. The longest body is about 27,000 characters.
- Gmail access is read-only. The Compose stack has `postgres` and `poller`. The poller mounts `secrets/` for the OAuth token.
- The GPU (RTX 5090, 32 GB) is on the Windows host, which also runs Docker Desktop. Ollama is not installed yet.

Constraints: mail content must stay on this machine. Model output must never trigger an action (see mail-analysis spec).

## Goals / Non-Goals

**Goals:**
- Analyze every stored mail once per prompt version, safely and repeatably.
- Keep the analyzer independent of the poller. They share only the database.
- Make the model replaceable: no model name in the code, only in configuration.

**Non-Goals:**
- No streaming, no parallel model calls, no queue service. Volume is a few dozen mails a day.
- No fine-tuning and no training on the mails.
- No web interface for the results. They are read from the database.

## Decisions

### 1. Separate container, same image
The analyzer is a second service in Compose. It uses the same image as the poller and starts a different command (`python -m mail_informer analyze`). `entrypoint.sh` reads two variables, `RUN_COMMAND` and `CRONTAB`, so the first run and the schedule differ per service.

- Why: one build, one set of pinned dependencies, and the poller stays unchanged and read-only toward Gmail.
- The analyzer does **not** mount `secrets/`. It has no Gmail token and cannot reach Gmail. A broken or tricked analyzer cannot touch the mailbox.
- Alternative: run the analysis inside the poller. Rejected: a slow or hanging model would delay mail import, and the poller would need access to the model server.
- Alternative: a separate image. Rejected: no gain for this size, and two builds to keep in sync.

### 2. Schedule: every 5 minutes with supercronic
A pass starts every 5 minutes and ends when no work is left or the pass limit is reached (50 mails). A pass that finds nothing exits at once without calling the model.

- Why: same pattern as the poller, so one way to operate both. The poller imports every 30 minutes, so new mails are analyzed within about 35 minutes.
- Alternative: Postgres `LISTEN/NOTIFY` or a queue (Redis). Rejected: more moving parts for no gain at this volume.
- Alternative: an endless loop in the process. Rejected: needs its own restart and error handling, and cron already gives both.

### 3. Work selection and attempts
The analyzer picks mails with no `analyses` row for the current `prompt_version`, or with a `pending` row whose attempts are below the limit (3). Newest mails come first, so recent important mail is rated before old backlog.

- A row is written after each attempt, in its own transaction. A crash loses at most the current mail.
- An **invalid model answer** raises the attempt count. At the limit the status becomes `failed`.
- A **connection error or timeout** raises `ModelUnavailable`. No row is changed and the pass ends with exit code 1 (see mail-analysis spec: model server unavailable).
- Uniqueness comes from `UNIQUE (gmail_id, prompt_version)`, so repeated or parallel work cannot create duplicates.
- A dedicated advisory lock (different key from the poller) prevents two analyzer passes from running together.

### 4. Two model calls, both with a fixed JSON schema
1. **Classify** (every mail): input is sender, subject, and the first 2,000 characters of the body. The schema allows `category`, `importance`, and `reason` (max 200 characters). Category and importance are enums.
2. **Summarize** (only `important` and `urgent`): input is sender, subject, and up to 8,000 characters. The schema allows one field, `summary`.

- Why two calls: most mails (about 90% in the archive) are not important. They never need the long input or the summary. A short classify call also keeps the small model focused.
- Alternative: one call that returns everything. Rejected: longer input for every mail and more chance that the model skips the rating when it writes prose.
- Alternative: regex or sender rules first. Rejected as the main method (brittle, never complete). It may come later as a cheap pre-filter.

### 5. Talk to Ollama over plain HTTP
The model client is a small class on top of Python's standard library (`urllib`), calling `POST /api/chat` with `stream: false`, `format` set to the JSON schema, `temperature: 0`, a fixed seed, and `keep_alive` of 10 minutes. The address and the model name come from `OLLAMA_URL` and `ANALYZER_MODEL`. The default address is `http://host.docker.internal:11434`.

- Why: no new dependency to pin, and the API is small. Schema-constrained output makes invalid JSON rare.
- The analyzer depends on a `ModelClient` protocol, not on Ollama. Tests use a fake client, as `run_sync` does with `MailSource`.
- Alternative: the `ollama` Python package. Rejected: a dependency for one endpoint.
- Alternative: a cloud model. Rejected: mail content must stay local.
- Alternative: Ollama as a Compose service. Rejected for now: GPU pass-through under Docker Desktop adds setup work, and a host install is easier to update and to share with other tools.
- `extra_hosts: host.docker.internal:host-gateway` is added so the address also works on Linux.

### 6. Safety rules live in code, not in the prompt
All of these are plain functions in a module without I/O, tested without a model:

- Validate the model answer against the allowed enums. Anything else is an invalid answer.
- Cut `summary` and `reason` to their maximum length and remove control characters.
- **Bulk guard:** `urgent` becomes `important` if the mail is bulk. A mail whose bulk flag is unknown (`NULL`) counts as bulk.
- The mail text is put in the prompt as quoted data with a clear boundary, and the prompt says it must not be followed as instructions. This is a help, not a protection. The protection is that the model has no tools and that later stages read only the enums.

### 7. Database changes (two new migrations)
- `002_bulk_flag.sql`: add `messages.is_bulk boolean` (nullable). The poller sets it from the `List-Unsubscribe` header for new mails. Old mails stay `NULL` because the header was not stored. `NULL` counts as bulk (decision 6). Old mails therefore can never be `urgent`, which is the safe default. No backfill is needed.
- `003_analyses.sql`:
  - `analyses(gmail_id → messages, prompt_version, status, category, importance, summary, reason, model, attempts, created_at, updated_at)` with `UNIQUE (gmail_id, prompt_version)`, a check on `status` and `importance`, and a check that `done` rows have a category and an importance.
  - A partial index on `importance` for `done` rows, for the later notifier.
  - `analyzer_state(id = 1, last_ok_at)` for the healthcheck.
  - Drop `messages.analysis_status` and its index. Nothing ever changed it, so every row still holds the default `pending`. No information is lost.
- Both containers call `db.migrate` at start. Two containers can start at the same moment, so `migrate` takes its own advisory lock first. Without it, two runners could apply the same file twice.

### 8. Code layout
A new package `mail_informer/analysis/` next to the existing modules:

| Module | Job | I/O |
|---|---|---|
| `rules.py` | enums, validation, truncation, bulk guard | none |
| `prompts.py` | prompt text, JSON schemas, `PROMPT_VERSION` | none |
| `model.py` | `ModelClient` protocol, Ollama client, `ModelUnavailable` | HTTP |
| `analyzer.py` | pick work, call model, write results | via `db` |
| `evaluate.py` | compare a model with hand labels | reads DB |

`db.py` gets the new SQL. The `cli.py` gets the commands `analyze`, `analyzer-health`, and `evaluate`. This follows the existing rule: `db.py` holds all SQL, `cli.py` only wires things.

### 9. Model choice by measurement
`evaluate` reads a file of labeled mails (message ID, expected category and importance), runs a chosen model on them, and prints accuracy for category and importance, a table of importance mistakes, and the number of missed `urgent` mails. It writes nothing to `analyses`. The label file holds IDs only, never mail text, and is git-ignored. About 40 mails are labeled by hand, including all five urgent topics. A model is adopted only if it misses no `urgent` mail in the set.

- Alternative: pick a well-known model and trust it. Rejected: the mix of German and English mails and the personal urgent rules are specific, and the cost of a bad rating is a missed important mail.

**Measurement (provisional).** Set: the 36 real mails of the archive plus 13 sample mails written for the test (6 urgent, 2 important-looking, 1 phishing, 1 prompt-injection newsletter, and others). All labels are proposals and still need a review by the owner. The runs used a throwaway database, never the real archive. The GPU was an RTX 5090 and both models ran fully on it.

| Model | Prompt | Importance correct | Category correct | Missed urgent | False urgent | Time for 49 mails |
|---|---|---|---|---|---|---|
| qwen3:8b | v1 | 27/49 | 33/49 | 1 | 1 | 2 min 17 s |
| gemma3:12b | v1 | 32/49 | 34/49 | 2 | 2 | 53 s |
| gemma3:12b | v2 | 42/49 | 34/49 | 0 | 2 | not measured |
| qwen3:8b | v2 | 45/49 | 32/49 | 0 | 1 | not measured |
| qwen3:8b, `think: false` | v2 | 40/49 | 33/49 | 0 | 2 | 2 min 0 s |
| qwen3.5:9b, `think: false` | v2 | 43/49 | 29/49 | 0 | 1 | 2 min 6 s |
| qwen3.5:4b, `think: false` | v2 | 44/49 | 30/49 | 0 | 2 | 2 min 3 s |

The three `think: false` rows are a second round, run after the client started to send `think: false`. The 2-minute times are mostly model loading. The earlier qwen3:8b row ran with thinking on, so it is not comparable with the later rows.

- Both models missed approval and rejection letters from authorities with prompt v1. The cause was a vague prompt, not the models. Prompt v2 names the authorities and says that every decision letter is urgent.
- Most remaining mistakes are newsletters rated `normal` instead of `ignore`. This is harmless: neither level leads to a notification.
- The only false `urgent` of qwen3:8b is the phishing sample. It is a bulk mail, so the bulk guard lowers it to `important`. The guard works as designed.
- **Caveat:** prompt v2 was written after looking at the mistakes on this same set, and the sample mails were written by the same author as the prompt. The numbers are therefore too good. They must be confirmed on new, real mails before the stage is trusted.
- Most category mistakes (15 of 20 for qwen3.5:9b) are advertising or LinkedIn notices rated `newsletter`. Their importance is still `ignore`, so no rating changes. Two real mistakes remain: authority letters rated `personal` instead of `authority`, with the right importance.
- The two false `urgent` answers of qwen3.5:4b are the phishing sample and a real Google security notice. Both are bulk mails, so the bulk guard lowers them to `important`.
- **Choice:** qwen3.5:4b with prompt v2. It meets the bar (no missed urgent mail), is level with qwen3.5:9b and ahead of qwen3:8b and gemma3:12b on importance, and needs about 3 to 4 GB instead of 5 to 8 GB. The gap is one to four mails of 49, so this is a preference, not a clear win. qwen3.5:9b and gemma3:12b are the fallbacks. Larger models (27b and up) were not tried: the volume is small and they would take 18 GB or more of the shared GPU.

### 10. Healthcheck
`analyzer-health` fails when unanalyzed mails exist and `last_ok_at` is older than 30 minutes. With no work it passes. A switched-off model server therefore shows up as `unhealthy` after half an hour, but an idle analyzer does not.

## Risks / Trade-offs

- [A tricked model rates a personal-looking spam mail as `urgent`] → The model has no tools and the bulk guard blocks newsletters. A hand-made fake personal mail can still get through. The next change adds a limit on immediate notifications per hour.
- [The model misses a truly urgent mail] → Measured on labeled mails before adoption, with zero misses as the bar. The `reason` field and the archive let you review misses later. Changing the prompt creates a new `prompt_version` and re-analyzes.
- [Ollama is not reachable from the container] → On Docker Desktop, `host.docker.internal` normally reaches host services. If it does not, Ollama must listen on all interfaces with the firewall limited to local traffic. This is checked by a smoke test task before any other work depends on it.
- [The GPU is busy with another program] → Calls can be slow or fail. A timeout turns this into `ModelUnavailable`, and the pass is retried 5 minutes later. `keep_alive` is limited so the model leaves the GPU memory after a pause.
- [A long backlog on the first run or after a new prompt version] → The pass limit (50) keeps each run short. A backlog is worked off over several passes.
- [Crash in the middle of a pass] → Each mail is written in its own transaction and the uniqueness key makes repeats safe. The next pass continues.
- [Two analyzers run together by mistake] → The advisory lock stops the second one.
- [Failed migration after the column drop] → The drop is the last statement of `003` and runs in the same transaction as the rest, so it is all or nothing.
- [Old mails count as bulk] → They cannot become `urgent`. This is intended. Only the 32 existing mails are affected.
- [Re-analysis costs GPU time] → A new prompt version re-analyzes every mail. At a few thousand mails this takes minutes to an hour, which is acceptable.

## Migration Plan

1. Install Ollama on the host, pull the chosen model, and check with `ollama ps` that it runs on the GPU.
2. Label the sample mails and run `evaluate` for the candidate models. Pick one.
3. Merge the change. Rebuild with `docker compose up -d --build`. The poller applies migrations `002` and `003` at start.
4. The analyzer starts, analyzes the existing 32 mails, and the results can be read from `analyses`.

Rollback: stop the analyzer service. The poller works without it. Migrations are forward-only. To undo them by hand: drop `analyses` and `analyzer_state`, drop `messages.is_bulk`, and re-add `messages.analysis_status text NOT NULL DEFAULT 'pending'` with its index. All old rows were `pending`, so this restores the old state exactly.

## Open Questions

- Which model wins the measurement. This changes only a setting, not the design.
- The exact limits (3 attempts, 50 mails per pass, 2,000 and 8,000 characters, 30 minutes for the healthcheck). They can be tuned in configuration after the first real runs.
