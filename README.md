# mail_informer

Polls your mail accounts every 5 minutes (one Gmail account plus any number of IMAP mailboxes, e.g. Strato) and archives new mails (metadata + plain text) in Postgres. No backfill of old mails.

- **analyzer**: rates every mail with a model: category, importance, and a short German summary for `urgent` mails. Any server with the OpenAI chat completions API works. By default this is Ollama on your machine, and mail text never leaves it. A cloud model is possible, but only if you allow it (see 2b).
- **notifier**: sends each new `urgent` or `important` mail to your phone via a Home Assistant webhook (account, category, importance, sender, summary).

## Setup

### 1. Google Cloud (once)

1. Create a project at https://console.cloud.google.com and enable the **Gmail API**.
2. OAuth consent screen: *External*, scope `https://www.googleapis.com/auth/gmail.readonly`, status **"In production"** (in "Testing" the refresh token expires after 7 days).
3. Create an **OAuth client ID** (Desktop app) and save the JSON as `secrets/client_secret.json`.

### 2. Configuration

```
copy .env.example .env     # set POSTGRES_PASSWORD
```

`ANALYZER_MODEL` is required (default `qwen3.5:4b`). `MODEL_URL` defaults to `http://host.docker.internal:11434/v1` (Ollama). For Ollama also set `MODEL_REASONING_EFFORT=none` (see 2b). The old `OLLAMA_URL` is gone: if it is still set, the analyzer refuses to start. Replace it with `MODEL_URL` (same address plus `/v1`).

### 2a. Mail accounts

Accounts live in `secrets/accounts.toml` (copy `accounts.toml.example`; the folder is git- and docker-ignored).

- The Gmail account **must be named `gmail`**, otherwise it counts as a new account and mails since the last run are skipped.
- Each IMAP mailbox needs `name`, `host`, `user`, `password` (Strato: `imap.strato.de`). TLS on port 993 only, certificate checked. Use a password you use nowhere else.
- Only `INBOX` is read; nothing is changed on the server.
- A **new account starts from now**: the first run only stores the current end of the inbox.
- Add an account: add a block, then `docker compose restart poller`. Remove: delete the block (stored mails stay).
- Names: lowercase letters, digits, `_`, `-`. Renaming makes a new account.

### 2b. Ollama (once, on the host)

1. Install Ollama and run `ollama pull qwen3.5:4b`. Set `OLLAMA_KEEP_ALIVE=10m` on the Ollama host and restart it, so the model stays loaded between the 5-minute passes. In `.env` set `MODEL_REASONING_EFFORT=none`: through `/v1`, Ollama lets `qwen3.5` think, which is about ten times slower and can run into the timeout.
2. `ollama run qwen3.5:4b hi`, then `ollama ps` should show `100% GPU`.
3. `docker run --rm curlimages/curl curl -s http://host.docker.internal:11434/` should print `Ollama is running`. If not, set `OLLAMA_HOST=0.0.0.0` and restrict port 11434 to local traffic.

To use another server (vLLM, llama.cpp, a cloud service), set `MODEL_URL`, `ANALYZER_MODEL` and, if needed, `MODEL_API_KEY` (a secret; keep it in `.env`). Leave `MODEL_REASONING_EFFORT` empty unless the server knows `reasoning_effort`; some answer an error.

- A server on this machine or at a private IP address (`192.168.x.x`, `10.x.x.x`, ...) needs nothing more. Give a LAN server by its IP: a host name like `nas.fritz.box` counts as remote.
- Any other address is **remote**. With a remote server, the sender, subject and first part of every mail body go to that service. It only starts if you set `ALLOW_REMOTE_MODEL=true` and `MODEL_URL` starts with `https://`. Redirects of the model server are never followed, so the key cannot be passed on to another host. Run `evaluate` with the model first.

### 2c. Home Assistant (once)

1. Create an automation with a webhook trigger and a long random id (Home Assistant 2024.10+, adjust the phone name):

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
                ({{ trigger.json.account }}, {{ trigger.json.category }})
              message: "{{ trigger.json.sender }}: {{ trigger.json.summary }}"
      - conditions: "{{ trigger.json.kind == 'digest' }}"
        sequence:
          - action: notify.mobile_app_<your_phone>
            data:
              title: Weitere wichtige Mails
              message: "{{ trigger.json.count }} weitere Mails (Limit von 10 pro Stunde erreicht)"
```

2. Set `HA_WEBHOOK_URL=http://<home-assistant-host>:8123/api/webhook/<your-secret-id>` in `.env`. The id is a secret; never commit it. The host name must resolve **inside the Compose network** (use a full name or an IP). Check:
   `docker compose run --rm --no-deps --entrypoint python notifier -c "import socket; print(socket.gethostbyname('<home-assistant-host>'))"`
3. Test by hand (HA answers `200` even for a wrong id, so check the phone):

```
curl -X POST -H "Content-Type: application/json" -d '{"kind":"mail","account":"privat","category":"work","importance":"urgent","sender":"Test","summary":"Das ist ein Test."}' "$HA_WEBHOOK_URL"
```

### 3. Authorize (once, on the host)

```
python -m venv .venv
.venv\Scripts\pip install -e .
.venv\Scripts\python -m mail_informer auth
```

After you agree in the browser, `secrets/token.json` is ready. On "unverified app" click *Advanced → Continue*.

### 4. Start

```
docker compose up -d
docker compose logs -f poller
```

A run starts right away, then every 5 minutes.

## Notes

- Connect to the database from the host via `127.0.0.1:5432`, not `localhost` (IPv6 hangs on Windows).
- If Gmail no longer knows the sync point (pause over about a week), the poller reloads by date. IMAP does the same when the UID validity changes.
- One run syncs all accounts in turn. A failing account is logged by name (never the password), the others still run, and the run ends with an error.
- A mail delivered to two of your mailboxes is stored once per mailbox and may be reported twice.
- The analyzer rates unrated mails newest first, at most 50 per pass. Only `urgent` gets a summary. The model only returns a rating; nothing is done based on a mail's text.
- A mail without `List-Unsubscribe` is not bulk. Bulk mail (`is_bulk = true`) and mails from before the flag (`NULL`) can never be `urgent`; such an answer is stored as `important`.
- The notifier reports a mail at most once, only mails first analyzed after its first run, at most 10 per hour (then one collective message). Analyses older than 6 hours are not reported. It decides only from the importance level.

## Reading results

Results are in `analyses` (one row per mail and prompt version; `status` is `done`, `pending` or `failed`):

```
docker compose exec postgres psql -U mail_informer -c "SELECT m.subject, a.category, a.importance, a.summary FROM analyses a JOIN messages m USING (gmail_id) WHERE a.status = 'done' AND a.importance IN ('urgent','important') ORDER BY m.internal_date DESC LIMIT 20"
```

Importance: `ignore`, `normal`, `important`, `urgent`. A changed prompt gets a new `PROMPT_VERSION` and is analyzed again.

Reported mails (`sent` = single message, `suppressed` = only counted in a collective message):

```
docker compose exec postgres psql -U mail_informer -c "SELECT n.created_at, m.account, n.status, n.importance, m.from_addr FROM notifications n JOIN messages m USING (gmail_id) ORDER BY n.created_at DESC LIMIT 20"
```

## Choosing a model

`evaluate` compares a model with hand labels in `eval/labels.jsonl` (message ID, category, importance; git-ignored). It reads mail text from the database and writes nothing to `analyses`:

```
set DATABASE_URL=postgresql://mail_informer:<password>@127.0.0.1:5432/mail_informer
set MODEL_URL=http://localhost:11434/v1
set MODEL_REASONING_EFFORT=none
.venv\Scripts\python -m mail_informer evaluate --model qwen3.5:4b
```

A model qualifies only if it misses no `urgent` mail. First-round results: `openspec/changes/archive/2026-10-09-llm-analysis/design.md`. Then set `ANALYZER_MODEL` in `.env` and run `docker compose up -d`.

## Operations

- `docker compose ps` shows a service as `unhealthy` when it has work but no successful pass for too long: poller (an account without sync for 15 min), analyzer and notifier (30 min). An idle service stays healthy.
- Model server down, wrong key or rate limit: the pass fails with `Model server unavailable`; nothing is marked `failed` and the analyzer recovers on its own. A refused or cut-off answer counts as a failed attempt for that one mail.
- Home Assistant down: the pass fails with `Home Assistant unavailable`; nothing is recorded and the next pass retries until the 6-hour limit. A crash between sending and recording resends that one message.
- Rollback of multi-account: restore the dump from before the upgrade and run the old image. By hand, if only `gmail` has data (in `psql`; deletes IMAP mails and their sync points first):
  `DELETE FROM messages WHERE account <> 'gmail'; DELETE FROM sync_state WHERE account <> 'gmail'; ALTER TABLE sync_state ADD COLUMN id integer; UPDATE sync_state SET id = 1; ALTER TABLE sync_state DROP CONSTRAINT sync_state_pkey, DROP COLUMN account, ALTER COLUMN id SET NOT NULL, ADD PRIMARY KEY (id), ADD CHECK (id = 1); ALTER TABLE sync_state RENAME COLUMN cursor TO history_id; ALTER TABLE sync_state ALTER COLUMN history_id SET NOT NULL; ALTER TABLE messages DROP COLUMN account; DELETE FROM schema_migrations WHERE name = '005_accounts.sql';`
- Rollback of the notifier: `docker compose stop notifier`; to undo its migration drop `notifications` and `notifier_state`.
- Rollback of the analyzer: `docker compose stop analyzer`; to undo its migrations drop `analyses` and `analyzer_state` and `messages.is_bulk`, and re-add `messages.analysis_status text NOT NULL DEFAULT 'pending'` with an index.
- Containers run as non-root (UID 1000). `secrets/` is mounted writable (the poller rewrites the OAuth token); on Linux run `chown -R 1000 secrets`.
- Dependencies are pinned in `constraints.txt`. To update: `pip install -e .` in a fresh venv, then write `pip freeze` to it without the project and dev packages.

## Development

```
.venv\Scripts\pip install -e ".[dev]"
docker compose up -d postgres
set TEST_DATABASE_URL=postgresql://mail_informer:<password>@127.0.0.1:5432/mail_informer
.venv\Scripts\python -m pytest
```

Tests needing Postgres are skipped without `TEST_DATABASE_URL`.
