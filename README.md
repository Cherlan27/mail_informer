# mail_informer

Polls your Gmail mailbox every 30 minutes and archives new mails (metadata + plain-text body) in Postgres. The import starts when you set it up. There is no backfill of old mails.

A second service, the analyzer, rates every archived mail with a local language model (Ollama): a category, an importance level, and for important and urgent mails a short German summary. Mail text never leaves your machine.

A third service, the notifier, sends each new `urgent` or `important` mail to your phone through a Home Assistant webhook: category, importance, sender, and the summary. Nothing else from the mail leaves the stack.

## Setup

### 1. Google Cloud (once)

1. Create a project at https://console.cloud.google.com.
2. Open "APIs & Services → Library" and enable the **Gmail API**.
3. OAuth consent screen: user type *External*, scope `https://www.googleapis.com/auth/gmail.readonly`, and set the status to **"In production"**. In "Testing" status the refresh token expires after 7 days.
4. Under "Credentials", create an **OAuth client ID** of type **Desktop app**. Download the JSON and save it as `secrets/client_secret.json`.

### 2. Configuration

```
copy .env.example .env     # set POSTGRES_PASSWORD
```

`ANALYZER_MODEL` is required (default in `.env.example`: `qwen3.5:4b`). `OLLAMA_URL` defaults to `http://host.docker.internal:11434`.

### 2b. Ollama (once, on the host)

1. Install Ollama for Windows and pull the model: `ollama pull qwen3.5:4b`.
2. Check that it runs on the GPU: `ollama run qwen3.5:4b hi`, then `ollama ps` should show `100% GPU`.
3. Check that containers can reach it: `docker run --rm curlimages/curl curl -s http://host.docker.internal:11434/` should print `Ollama is running`. If not, let Ollama listen on all interfaces (`OLLAMA_HOST=0.0.0.0`) and limit port 11434 to local traffic in the firewall.

### 2c. Home Assistant (once)

1. In Home Assistant, create an automation with a webhook trigger. Pick a long random webhook id and keep it secret. Example (for Home Assistant 2024.10 or newer; adjust the phone name):

```yaml
alias: Mail informer
triggers:
  - trigger: webhook
    webhook_id: <your-secret-id>
    allowed_methods: [POST]
    local_only: true
actions:
  - choose:
      - conditions: "{{ trigger.json.kind == 'mail' }}"
        sequence:
          - action: notify.mobile_app_<your_phone>
            data:
              title: >-
                {{ 'Dringende Mail' if trigger.json.importance == 'urgent' else 'Wichtige Mail' }}
                ({{ trigger.json.category }})
              message: "{{ trigger.json.sender }}: {{ trigger.json.summary }}"
      - conditions: "{{ trigger.json.kind == 'digest' }}"
        sequence:
          - action: notify.mobile_app_<your_phone>
            data:
              title: Weitere wichtige Mails
              message: "{{ trigger.json.count }} weitere Mails (Limit von 10 pro Stunde erreicht)"
```

2. Put the full address in `.env` as `HA_WEBHOOK_URL=http://homeassistant:8123/api/webhook/<your-secret-id>`. The id is a secret: never commit it. `docker compose` does not start until this is set.
3. Test the automation by hand. Home Assistant answers `200` even for a wrong id, so check the phone:

```
curl -X POST -H "Content-Type: application/json" -d '{"kind":"mail","category":"work","importance":"urgent","sender":"Test","summary":"Das ist ein Test."}' "$HA_WEBHOOK_URL"
```

### 3. Authorize (once, on the host)

```
python -m venv .venv
.venv\Scripts\pip install -e .
.venv\Scripts\python -m mail_informer auth
```

The browser opens. After you agree, `secrets/token.json` is ready. If you see the warning "unverified app", click *Advanced → Continue*.

### 4. Start

```
docker compose up -d
docker compose logs -f poller
```

A run starts right away (this catches up after sleep). After that, a run starts every 30 minutes. The very first run only sets the starting point. Mails that arrive after it are imported.

## Notes

- To connect to the database from the host, use `127.0.0.1:5432`, not `localhost`. On Windows, `localhost` tries IPv6 and the connection hangs.
- If Gmail no longer knows the sync point (pause longer than about one week), the poller reloads mails by date.
- The analyzer rates mails that have no result yet, newest first, at most 50 per pass. A pass runs every 5 minutes and ends at once when there is no work. Only importance `urgent` leads to a summary. The model only returns a rating; nothing is done on the basis of a mail's text.
- A mail without a `List-Unsubscribe` header is not bulk. Bulk mail (`is_bulk = true`) and mails imported before the flag existed (`is_bulk` is `NULL`) can never be `urgent`: an `urgent` answer is stored as `important`.
- The notifier runs every 5 minutes. It reports a mail at most once and only mails that were first analyzed after the notifier first ran (the existing archive is not sent). At most 10 single messages go out per hour. If more mails are ready, one collective message tells how many. A mail whose analysis is older than 6 hours is no longer reported.
- The notifier decides only from the importance level. The summary is sent as plain text for display and decides nothing.

## Reading results

Results are in the table `analyses`, one row per mail and prompt version (`status` is `done`, `pending`, or `failed`):

```
docker compose exec postgres psql -U mail_informer -c "SELECT m.subject, a.category, a.importance, a.summary FROM analyses a JOIN messages m USING (gmail_id) WHERE a.status = 'done' AND a.importance IN ('urgent','important') ORDER BY m.internal_date DESC LIMIT 20"
```

Importance levels: `ignore`, `normal`, `important`, `urgent`. `reason` holds a short justification from the model. A changed prompt gets a new `PROMPT_VERSION` and is analyzed again next to the old rows.

To see what was reported:

```
docker compose exec postgres psql -U mail_informer -c "SELECT n.created_at, n.status, n.importance, m.from_addr FROM notifications n JOIN messages m USING (gmail_id) ORDER BY n.created_at DESC LIMIT 20"
```

`sent` means a single message, `suppressed` means the mail was only counted in a collective message.

## Choosing a model

`evaluate` compares a model with hand labels in `eval/labels.jsonl` (message ID, category, importance; the file holds no mail text and is git-ignored). It reads the mail text from the database and writes nothing to `analyses`:

```
set DATABASE_URL=postgresql://mail_informer:<password>@127.0.0.1:5432/mail_informer
set OLLAMA_URL=http://localhost:11434
.venv\Scripts\python -m mail_informer evaluate --model qwen3.5:4b
```

It prints the share of correct categories and importance levels, the wrong importance ratings, and the number of missed `urgent` mails. A model qualifies only if it misses none. Results of the first round are in `openspec/changes/llm-analysis/design.md`. Then set `ANALYZER_MODEL` in `.env` and run `docker compose up -d`.

## Operations

- `docker compose ps` shows the poller as `unhealthy` if the last successful sync is older than 90 minutes (`python -m mail_informer health`).
- `docker compose ps` shows the analyzer as `unhealthy` if mails wait for analysis and the last successful pass is older than 30 minutes (`python -m mail_informer analyzer-health`). An idle analyzer stays healthy. If Ollama is stopped, a pass fails with the log line `Model server unavailable`. No mail is marked `failed`, and the analyzer recovers on its own when Ollama is back.
- `docker compose ps` shows the notifier as `unhealthy` if mails wait to be reported and the last successful pass is older than 30 minutes (`python -m mail_informer notifier-health`). If Home Assistant is not reachable, a pass fails with the log line `Home Assistant unavailable`. Nothing is recorded, and the next pass tries again until the 6-hour limit. If a crash happens between sending and recording, that one message is sent again.
- Rollback of the notifier: `docker compose stop notifier`; the poller and the analyzer do not depend on it. To undo its migration by hand: drop `notifications` and `notifier_state`.
- Rollback of the analyzer: stop the analyzer (`docker compose stop analyzer`); the poller works without it. To undo the migrations by hand: drop `analyses` and `analyzer_state`, drop `messages.is_bulk`, and re-add `messages.analysis_status text NOT NULL DEFAULT 'pending'` with an index on it.
- The container runs as a non-root user (UID 1000). `secrets/` is mounted writable because the poller rewrites the OAuth token when it refreshes it. On Linux hosts, the directory must be writable for UID 1000 (`chown -R 1000 secrets`). `secrets/` is listed in `.gitignore` and `.dockerignore`.
- Dependencies are pinned in `constraints.txt` (Docker build and CI). To update it: install the project in a fresh venv with `pip install -e .`, then write `pip freeze` to `constraints.txt`. Leave out the project itself and the dev packages.

## Development

```
.venv\Scripts\pip install -e ".[dev]"
docker compose up -d postgres
set TEST_DATABASE_URL=postgresql://mail_informer:<password>@127.0.0.1:5432/mail_informer
.venv\Scripts\python -m pytest
```

Tests that need Postgres are skipped when `TEST_DATABASE_URL` is not set.
