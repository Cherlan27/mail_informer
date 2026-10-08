## Context

Greenfield project, see proposal.md. It runs on a Windows PC with Docker Desktop that is not always on. A later stage (local LLM, Home Assistant) will build on the stored mails.

## Goals / Non-Goals

**Goals:**
- A robust, idempotent import that catches up after outages and sleep by itself.
- A clear hand-over to a later analysis stage, only through the database.

**Non-Goals:**
- No daemon, no push notifications (Gmail Pub/Sub), no web interface.

## Decisions

- **Gmail API instead of IMAP.** `history.list` with `historyId` gives efficient deltas. Labels and threads are native. Scope is `gmail.readonly`. IMAP is easier to set up, but worse for deltas and labels.
- **Python, one-shot process.** One run = read the sync point, fetch new mails, write them in one transaction, set the sync point, exit. The process keeps no state. A crash costs at most one run.
- **Scheduling with supercronic in the poller container.** Everything is in the repo and `docker compose up -d` is enough. The alternative is the Windows Task Scheduler with `docker compose run --rm`. It is more robust against hangs, but the setup lives outside the repo. To prevent overlapping runs, we also use a Postgres advisory lock (`pg_try_advisory_lock`). A run that does not get the lock exits quietly.
- **Initialization with `users.getProfile`.** The returned `historyId` is stored as the starting point. No backfill.
- **Only `messagesAdded` from the history** is used. For each new message ID, we call `messages.get(format=full)`. If the mail is gone by then (404, for example deleted), it is skipped.
- **Fallback on 404 from history.list:** `messages.list` with `q=after:<date of the last mail minus a safety buffer>`, then a new sync point from `getProfile`. `ON CONFLICT (gmail_id) DO NOTHING` absorbs duplicates.
- **Body extraction:** prefer text/plain (recursively through multipart). Otherwise convert text/html with an HTML-to-text library. No HTML is stored (local LLM, fewer tokens).
- **Schema (Postgres):**
  - `messages(gmail_id PK, thread_id, internal_date, from_addr, to_addrs, subject, labels text[], snippet, body_text, fetched_at, analysis_status default 'pending')`
  - `sync_state(id=1 PK, history_id, updated_at)`
  - The schema is created when the poller starts (simple versioned SQL migrations instead of an ORM).
- **Auth:** the `auth` command runs on the host (InstalledAppFlow, local redirect) and writes `token.json` to a directory that is mounted as a volume into the container. The poller writes refreshed tokens back to it. Secrets live in `.env` and `secrets/`. Both are in `.gitignore`.
- **Transactions and batches:** mails are stored in batches. The new `history_id` is written only after the last batch. The insert is idempotent, so after a crash the next run repeats the work safely. The sync point never moves ahead of the data.

## Risks / Trade-offs

- OAuth app in Testing status → the refresh token expires after 7 days → set the app to "In production" (unverified is enough). The error is logged.
- History ID older than about one week → fallback by date query.
- Gmail API rate limits for large deltas → sequential requests with retry and backoff on 429/5xx.
- Docker Desktop is not running → the run is skipped and caught up at the next start.
- Mails without text keep an empty body → irrelevant for the later LLM, but visible in the archive.
- Deleted or relabeled mails are not followed (on purpose: this is an archive).
