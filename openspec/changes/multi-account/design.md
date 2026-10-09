## Context

See proposal.md for the motivation. Current state:

- The poller reads one Gmail account with a token from `TOKEN_PATH`. `sync.py` already depends on a `MailSource` protocol, but the protocol is shaped like Gmail: it passes a `history_id` around.
- `sync_state` has a single row (`id = 1`, `history_id`, `updated_at`). `messages.gmail_id` is the primary key. `analyses` and `notifications` link to it.
- The poller container has the `secrets/` volume (mounted at `/secrets`, writable because the OAuth token is refreshed there). The analyzer and notifier do not have it.
- Strato offers IMAP with a mailbox password. There is no OAuth. The user checks the server name in the Strato customer area (expected: `imap.strato.de`, port 993, TLS, login = full address).
- The last migration is `004_notifications.sql`. Migrations run inside a transaction each.

Constraints: passwords are secrets and must not reach logs or the database. Mail access is read-only. A run must be safe to repeat.

## Goals / Non-Goals

**Goals:**
- Three IMAP mailboxes and the Gmail account run through the same archive, analysis, and notification path.
- One broken account never blocks the others or hides behind a healthy one.
- Existing data and the existing Gmail sync point survive the upgrade.

**Non-Goals:**
- No generic provider plug-in system. Two sources (`gmail`, `imap`) are enough.
- No change to the analyzer or the prompt.
- No renaming of `gmail_id` (see decision 4).

## Decisions

### 1. Accounts file in TOML, read with `tomllib`
`secrets/accounts.toml`, found through `ACCOUNTS_PATH` (default `secrets/accounts.toml`; Compose sets `/secrets/accounts.toml`).

```
[[account]]
name = "gmail"
kind = "gmail"
token = "token.json"          # relative to the folder of this file

[[account]]
name = "privat"
kind = "imap"
host = "imap.strato.de"
user = "me@example.org"
password = "..."
# port = 993                  # optional
```

- A name matches `[a-z0-9][a-z0-9_-]*` (no colon, see decision 4). It is the key in the database, so renaming an account means a new account.
- Loading lives in `accounts.py` and returns frozen dataclasses. `password` is excluded from `repr` so a stray log line cannot print it. Error messages name the account and the missing key, never a value.
- A token path relative to the file works on the host and in the container. An absolute container path would not.
- Why TOML: a standard-library parser, comments, and a list of tables. No new dependency.
- Alternative: JSON. Rejected: no comments, easy to break by hand.
- Alternative: `.env` variables per account. Rejected: a list of accounts with several fields each is awkward in flat variables.
- Alternative: accounts in the database. Rejected for now: needs an add-account command and puts passwords next to the data and into backups.
- The file is required. Without it the poller fails at start (spec: `mail-accounts`). No silent fallback to a single `TOKEN_PATH` account, because a fallback hides a missing file.

### 2. Sources return an opaque cursor
```
class MailSource(Protocol):
    def start_cursor(self) -> str: ...
    def fetch_since(self, cursor: str, known_since: datetime | None)
        -> tuple[list[Mail], str]: ...
```

`sync.py` no longer knows about history IDs or UIDs. It stores and passes a text. `GmailClient` keeps its own logic (history, expiry fallback) behind these two methods. `ImapClient` implements them with the cursor `"<uidvalidity>:<last_uid>"`.

- `known_since` is the date of the newest stored mail of the account. Both sources use it for the expiry fallback, which replaces `latest_mail_date` being global.
- The "advance only after storing" rule stays in `sync.py`: it stores a batch, then saves the new cursor. A source returns mails in batches through a generator, so memory stays small. (The exact shape is a task detail; the contract is: cursor moves only after the mails of that cursor are stored.)
- Alternative: one subclass per source with its own table. Rejected: the sync loop would be written twice.

### 3. State per account, registered before the first sync
`sync_state` is keyed by `account`, with `cursor` nullable.

- At the start of each run, the poller inserts a row `(account, NULL, now())` for each account in the file (`ON CONFLICT DO NOTHING`). `cursor IS NULL` means "not started": the next sync stores the starting point and imports nothing.
- `updated_at` moves only on success. This makes the health check work for an account that never succeeds (wrong password): its row is created, `updated_at` stays old, and the check fails after 15 minutes. Without the pre-created row, such an account would have no row and never be flagged.
- Alternative: no row until the first success, flag accounts without a row by the file's modification time. Rejected: fragile.

### 4. Mail key and the `gmail_id` column
The column keeps its name `gmail_id`. It now holds the unique mail key of any account.

- Gmail account: the Gmail message ID, unchanged. This keeps every existing row, analysis, notification, and `eval/labels.jsonl` valid.
- IMAP account: `"<account>:<id>"` where `<id>` is the `Message-ID` header with the angle brackets removed. Without that header: the hex SHA-256 of `from`, `date`, `subject`, and the first 200 characters of the body. A Message-ID is not trusted to be unique across mailboxes, so the account name is part of the key. The UID is not part of the key, so a UID reset cannot create duplicates.
- The account name has no colon, so the prefix cannot be forged by another name, and no Gmail ID (hex) contains a colon.
- Why not rename to `mail_id`: it touches `messages`, `analyses`, `notifications`, about 100 code lines, the eval labels, and many tests, for no behavior. A rename can be its own `refactor` change. The column gets a comment in the migration.
- Alternative: composite primary key `(account, mail_id)`. Rejected: both child tables would need the pair, and every query and foreign key grows.

### 5. IMAP access with `imaplib`
`imap.py` uses `imaplib.IMAP4_SSL` with `ssl.create_default_context()` (certificate and host name are verified) and a socket timeout of 30 seconds. A hanging server must not hold the poller lock for ever.

- Cursor start: `STATUS INBOX (UIDVALIDITY UIDNEXT)` gives `"<validity>:<UIDNEXT - 1>"`.
- Fetch: `SELECT INBOX` with `readonly=True` (the server cannot set flags), then `UID FETCH <last+1>:* (BODY.PEEK[] INTERNALDATE)`. `PEEK` and read-only are a belt-and-braces pair for the "stay unread" rule.
- Known pitfall: `n:*` returns the newest mail even if its UID is lower than `n`, when there is nothing new. The client drops every UID `<= last`.
- Batches of 20 UIDs per fetch limit memory for large mails.
- The highest UID that was stored becomes the new cursor. UIDs are fetched in ascending order, so a failure in the middle keeps the cursor behind the first mail that failed.
- UID validity changed: build the list with `UID SEARCH SINCE <date>`, where `<date>` is `known_since - 1 day` formatted by hand (`02-Oct-2026`) so the month name does not depend on the locale. IMAP `SINCE` has day precision, hence the buffer. Duplicates are dropped by the key (decision 4). The new cursor uses the new validity and the highest UID seen.
- Alternative: `imap-tools` or `imapclient`. Rejected: a new dependency for about 80 lines of calls.
- Alternative: IDLE. Rejected: needs a permanent connection and process, for no gain at a 5-minute poll.

### 6. Parsing raw mails with the `email` package
A new pure function in `parsing.py` turns bytes plus the server date into a `Mail`. It uses `email.message_from_bytes(..., policy=email.policy.default)`, which decodes encoded words in headers.

- Body: all non-attachment `text/plain` parts joined, else `text/html` parts converted by the existing `_html_to_text`. The same rule as for Gmail, so the analyzer sees comparable text.
- An unknown charset falls back to UTF-8 with replacement characters instead of failing the mail.
- `thread_id`: the first entry of `References`, else `In-Reply-To`, else the own Message-ID key.
- `labels`: `["INBOX"]`. `snippet`: the first 200 characters of the body with whitespace collapsed. `is_bulk`: a `List-Unsubscribe` header exists.
- `internal_date`: the `INTERNALDATE` of the server, not the `Date` header, which senders can set freely.

### 7. One run, many accounts, one lock
`_run` keeps the single advisory lock and loops over the accounts. For each account it opens its source, runs `run_sync`, and catches errors. Failures are collected and the run returns 1 at the end. The loop logs only the account name and the error text. IMAP errors from `imaplib` contain the server answer, not the password.

- A failure inside the database transaction of one account must not poison the next one. Each account's work commits or rolls back on its own.
- Order is the file order. Gmail and three mailboxes take seconds, so sequential is fine.
- Alternative: one cron job and one container per account. Rejected: four times the containers and four locks for the same code.

### 8. Health per account
`last_sync_at` becomes "oldest `updated_at` among the accounts in the file". `_health` loads the accounts file (the poller container has it), reads the rows of those accounts, and fails if the oldest is older than 15 minutes. Rows of removed accounts are ignored. Because of decision 3, every configured account has a row after the first run attempt.

### 9. Account in the phone message
`ReportableMail` gets `account` (a join on `messages`). The mail message payload gets a new field `account`. The digest message is unchanged (it only has a count). The change is additive: the existing Home Assistant automation keeps working and the README example shows how to use the new field in the title.

### 10. Migration `005_accounts.sql`
In one transaction:

1. `messages`: add `account text NOT NULL DEFAULT 'gmail'`, then drop the default so new code must set it. Add an index on `(account, internal_date)`.
2. `sync_state`: drop the `id = 1` check and the primary key, add `account` (existing row becomes `'gmail'`), rename `history_id` to `cursor` and allow NULL, drop `id`, make `account` the primary key.

- **The Gmail account in the file must be named `gmail`.** Otherwise it is a new account: it would start from now and the mails between the last run and the first new run would be skipped. The README says so, and the file example uses that name.
- Alternative: let the user name the account and map it in the migration. Rejected: the migration cannot know the name.

## Risks / Trade-offs

- [Mails in the gap are lost if the Gmail account is named differently] → README example and a startup warning when a `sync_state` row `gmail` exists but no account with that name is in the file.
- [Password in a plain file] → The file is git-ignored and docker-ignored, only the poller mounts it, and it is excluded from logs and reprs. Same exposure as the OAuth token today. The mailbox password is a full login, so the README tells the user to use a password only for this mailbox and notes that Strato lets them change it.
- [The server changes UID validity] → Handled by the date based reload (decision 5). Residual risk: a mail that arrived and was moved out of `INBOX` within the same day before the reload is missed. Acceptable.
- [A mail is moved out of `INBOX` by a server filter before the poll] → Not seen. Accepted: the user chose `INBOX` only.
- [A big mail or a slow server] → Socket timeout and batches of 20. The lock is held for the whole run, so a 30-second hang per account at most delays the next run.
- [Crash mid-run] → Mails are stored with `ON CONFLICT DO NOTHING` and the cursor moves only after the batch is stored. A repeat is safe.
- [Two mailboxes receive the same mail] → Stored twice (one per account) and analyzed twice, and may be reported twice. Accepted: they are different mailboxes.
- [Existing tests assume `id = 1` and `history_id`] → They change with the schema in the same task.

## Migration Plan

1. Back up the volume (`pg_dump`), then deploy the new image. The poller applies `005` on start.
2. Create `secrets/accounts.toml` **before** the deploy. Put the Gmail account first with the name `gmail` and add the three mailboxes.
3. The three new accounts start from now at their first run. Nothing old is imported.
4. Watch the logs: one line per account per run, with counts only.

Rollback: restore the dump and run the old image. The migration is not reversible in place because `sync_state` loses its single-row form. The README documents the reverse SQL for the case that only the `gmail` account has data.
