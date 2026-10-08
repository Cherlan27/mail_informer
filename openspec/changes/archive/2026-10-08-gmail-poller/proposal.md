## Why

Gmail mails should be stored in a structured way in our own Postgres database. Later, a local LLM can check them, summarize them, and trigger a Home Assistant message for certain mails. The first thing we need is a reliable, periodic import.

## What Changes

- New Python poller. Every 30 minutes it fetches new Gmail mails through the Gmail API (incremental, using `historyId`) and writes them to Postgres.
- It stores metadata and only `body_text`. For HTML-only mails, the text is extracted from the HTML. There is no `body_html`.
- The database is a pure archive. There is no backfill of old mails: the import starts when the poller is initialized. Deletions and status changes in Gmail are not followed.
- One interactive `auth` step on the host for the OAuth consent. The token is given to the container through a volume or secret.
- `docker-compose` with Postgres and a poller container. An internal scheduler (supercronic) starts a one-shot run every 30 minutes.
- Fallback when the `historyId` has expired: reload with `messages.list` and a date filter. This is idempotent because of `ON CONFLICT DO NOTHING`.
- Each mail has an `analysis_status` field (default `pending`) as the hand-over point for the later LLM stage.

Non-goals: LLM analysis, Home Assistant notification, attachments, backfill of old mails.

## Capabilities

### New Capabilities
- `mail-sync`: Incremental fetch of new Gmail mails through the API, initialization of the sync point, fallback when the history ID has expired, idempotent writes.
- `mail-storage`: Postgres schema and storage rules for mails (metadata, `body_text`, sync state, `analysis_status`).
- `poller-runtime`: Operation with docker-compose, first OAuth authorization on the host, and 30-minute scheduling.

### Modified Capabilities
<!-- none -->

## Impact

- New project without existing code. New files: Python package, Dockerfile, `docker-compose.yml`, database migration/schema.
- Dependencies: Google API client and OAuth libraries, Postgres driver, HTML-to-text library.
- External requirements: a Google Cloud project with the Gmail API enabled and an OAuth client. The app status must be "In production". Otherwise the refresh token expires after 7 days.
- Runs on the Windows PC with Docker Desktop. Gaps caused by sleep are caught up through the history ID.
