## 1. Project setup

- [x] 1.1 Create the Python project (pyproject, package structure `mail_informer/`, dependencies: Google API client/OAuth, psycopg, HTML-to-text library, pytest)
- [x] 1.2 Create `.gitignore` and `.env.example` (exclude secrets, `token.json`, `client_secret.json`)
- [x] 1.3 Load configuration from environment variables (database URL, paths to token and client secret)

## 2. Database

- [x] 2.1 Write the SQL migration for `messages` and `sync_state`
- [x] 2.2 Implement the migration runner that applies missing migrations at startup
- [x] 2.3 Repository functions: store mails with `ON CONFLICT DO NOTHING`, read/write the sync point, read the date of the last mail
- [x] 2.4 Tests against a test Postgres instance (idempotency, transaction for mails + sync point)

## 3. Gmail access and auth

- [x] 3.1 `auth` command: OAuth flow on the host with scope `gmail.readonly`, save the token
- [x] 3.2 Gmail client that loads the token, refreshes it, and writes the refreshed token back
- [x] 3.3 Retry/backoff on 429 and 5xx

## 4. Mail parsing

- [x] 4.1 Extract headers (sender, recipient, subject, date) into the data model
- [x] 4.2 Body extraction: prefer text/plain, recurse through multipart; fall back from HTML to text; empty body if there is no text; ignore attachments
- [x] 4.3 Tests with sample messages (plain, multipart/alternative, HTML only, no text, with attachment)

## 5. Sync logic

- [x] 5.1 First run: `getProfile`, store the `historyId`, import nothing
- [x] 5.2 Incremental run: `history.list` (only `messagesAdded`, pagination), deduplicate new IDs, fetch mails, skip 404
- [x] 5.3 Write mails and the new sync point (mails in batches, sync point after the last batch)
- [x] 5.4 Fallback when the history ID has expired: `messages.list` with a date filter, then a new sync point
- [x] 5.5 Advisory lock against parallel runs
- [x] 5.6 Tests with a mocked Gmail client (first run, delta, no new mails, error while storing, expired sync point)

## 6. Entry point and logging

- [x] 6.1 CLI with the subcommands `auth`, `run`, and `health`
- [x] 6.2 Logging; non-zero exit code on error

## 7. Container and operations

- [x] 7.1 Dockerfile for the poller with supercronic and a crontab (every 30 minutes)
- [x] 7.2 `docker-compose.yml` with Postgres (volume, healthcheck) and the poller (token volume, `depends_on` healthy, healthcheck)
- [x] 7.3 README: Google Cloud setup (Gmail API, OAuth client, "In production"), run `auth`, start the stack
- [ ] 7.4 End-to-end test: start the stack, send a test mail, check the database after one run
