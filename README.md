# mail_informer

Polls your Gmail mailbox every 30 minutes and archives new mails (metadata + plain-text body) in Postgres. The import starts when you set it up. There is no backfill of old mails.

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
- New mails have `analysis_status = 'pending'`. This is the hand-over to the later LLM stage.

## Operations

- `docker compose ps` shows the poller as `unhealthy` if the last successful sync is older than 90 minutes (`python -m mail_informer health`).
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
