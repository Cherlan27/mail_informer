## 1. Check the Strato mailbox

- [ ] 1.1 From a throwaway script (not committed), log in to one Strato mailbox with `imaplib.IMAP4_SSL`, read `STATUS INBOX (UIDVALIDITY UIDNEXT)`, and fetch one mail with `BODY.PEEK[]` in a read-only `SELECT`. Confirm the server name, the port, the login form, and that the mail stays unread. Do not print the password or mail content

## 2. Accounts file (`accounts.py`)

- [x] 2.1 Red: tests for a valid file with one Gmail and three IMAP accounts (names, kinds, host, user, relative token path resolved against the folder of the file, default port 993)
- [x] 2.2 Green: implement the loader with `tomllib` and frozen dataclasses. The password is excluded from `repr`
- [x] 2.3 Red: tests for the failures: missing file (message names the expected path), duplicate name, name with a colon or capital letter, unknown kind, missing value. Also a test that no message contains a password
- [x] 2.4 Green: implement the checks with messages that name the account and the key only
- [x] 2.5 Red: config test that `ACCOUNTS_PATH` defaults to `secrets/accounts.toml` and can be changed
- [x] 2.6 Green: extend `load_config`. `TOKEN_PATH` and `CLIENT_SECRET_PATH` stay for `authorize`

## 3. Parsing raw mails (`parsing.py`)

- [x] 3.1 Red: tests for a raw mail: plain text body, HTML-only body converted to text, attachment ignored, no text part gives an empty body, encoded subject and sender decoded, `List-Unsubscribe` sets the bulk flag, unknown charset does not fail
- [x] 3.2 Green: implement `parse_raw_message(raw: bytes, received: datetime, account: str)` as a pure function
- [x] 3.3 Red: tests for the key: from the Message-ID with the account prefix, the same Message-ID in two accounts gives two keys, a missing Message-ID gives a stable hash key that is the same on a second call
- [x] 3.4 Green: implement the key
- [x] 3.5 Red: tests for `thread_id` (first `References` entry, else `In-Reply-To`, else the own key), the label `INBOX`, and the snippet (200 characters, whitespace collapsed)
- [x] 3.6 Green: implement them
- [x] 3.7 Refactor: share the HTML conversion with the Gmail path. Check the module has no I/O

## 4. Database and migration

- [ ] 4.1 Write migration `005_accounts.sql` as in the design (`messages.account`, `sync_state` per account with a nullable `cursor`)
- [ ] 4.2 Red: migration test that starts from the schema of `004` with a mail, an analysis, a notification, and a sync row, then migrates: all rows stay, the mail has the account `gmail`, the sync row is `gmail` with the old history ID as the cursor
- [ ] 4.3 Green: fix the migration until the test passes
- [ ] 4.4 Red: tests for the per-account functions: register an account (no overwrite of an existing row), get and set the cursor, `updated_at` moves only on `set`, newest mail date of one account, `existing_ids`, and the oldest `updated_at` among a list of accounts
- [ ] 4.5 Green: implement them in `db.py` and make `insert_mails` store the account
- [ ] 4.6 Update the existing tests and the DROP TABLE lists in `conftest.py` for the new schema

## 5. Sync loop (`sync.py`)

- [ ] 5.1 Red: tests with a fake source for the account rules: first run stores the starting point and imports nothing, later run imports new mails and moves the cursor, a store error keeps the old cursor, a second account's cursor is not touched
- [ ] 5.2 Green: change the `MailSource` protocol to the opaque cursor and rewrite `run_sync(conn, account, source)` to match
- [ ] 5.3 Refactor: remove the history ID names from `sync.py`
- [ ] 5.4 Red: tests that `GmailClient` fits the new protocol: start cursor is the current history ID, expired history falls back to the date of the newest mail of the account
- [ ] 5.5 Green: adapt `gmail.py` behind the two methods. Gmail behavior stays the same

## 6. IMAP client (`imap.py`)

- [ ] 6.1 Red: tests with a fake IMAP connection: start cursor is `<validity>:<UIDNEXT-1>`, fetch returns only UIDs above the cursor, the "newest old mail" answer of `n:*` is dropped, the cursor is the highest UID returned, the mailbox is selected read-only, and the fetch uses `BODY.PEEK[]`
- [ ] 6.2 Green: implement `ImapClient` with batches of 20 UIDs
- [ ] 6.3 Red: tests that a changed UID validity triggers the date based reload (`SINCE` with the date one day before, English month name independent of the locale), and that the new cursor uses the new validity
- [ ] 6.4 Green: implement the reset path
- [ ] 6.5 Red: tests for the connection: TLS context with certificate check is used, a timeout is set, a refused login raises an error that names no password
- [ ] 6.6 Green: implement the connection and the error type

## 7. Run with several accounts (`cli.py`)

- [ ] 7.1 Red: tests that `_run` registers every account, syncs all of them, continues after a failing account, returns 1 when any failed, and logs the account name but never a password
- [ ] 7.2 Green: implement the loop with one commit or rollback per account
- [ ] 7.3 Red: test that an account removed from the file is not synced and its mails stay
- [ ] 7.4 Green: make it pass (the loop reads only the file)
- [ ] 7.5 Red: test for the warning when a `gmail` sync row exists but no account with that name is in the file
- [ ] 7.6 Green: implement the warning

## 8. Health

- [ ] 8.1 Red: tests that `health` is 0 when all accounts synced in the last 15 minutes and 1 when one account is older, when an account has never succeeded, and that rows of removed accounts are ignored
- [ ] 8.2 Green: implement it with the accounts file and the oldest `updated_at`

## 9. Account in the message

- [ ] 9.1 Red: tests that the mail message has the keys `kind`, `account`, `category`, `importance`, `sender`, `summary`, and that two mails of different accounts carry their own account. The digest message stays unchanged
- [ ] 9.2 Green: add `account` to `ReportableMail` (join on `messages`), to `mail_message`, and to the notifier pass
- [ ] 9.3 Update the notifier tests that build mails

## 10. Compose, config, and docs

- [ ] 10.1 Compose: set `ACCOUNTS_PATH: /secrets/accounts.toml` for the poller. Keep `TOKEN_PATH` out of the poller environment if nothing reads it. Check that `secrets/` stays in `.gitignore` and `.dockerignore`
- [ ] 10.2 Add `ACCOUNTS_PATH` to `.env.example`. Add an `accounts.toml.example` (no real values) to the repo root
- [ ] 10.3 README: accounts file with the Strato example, the rule that the Gmail account is named `gmail`, the first-run rule (new accounts start from now), a password hint, how to add and remove an account, the `account` field in the Home Assistant example, and the rollback SQL
- [ ] 10.4 Update `openspec/config.yaml` context: several accounts, Gmail and IMAP, and the layer for `imap.py` and `accounts.py`

## 11. Check the real stack

- [ ] 11.1 Back up the database with `pg_dump`. Write `secrets/accounts.toml` with the Gmail account and the three Strato mailboxes. Do not print the file
- [ ] 11.2 Rebuild and start. Check: migration applied, the Gmail sync point carried over, the three new accounts stored their starting point and imported nothing, healthcheck green
- [ ] 11.3 Send a test mail to each Strato mailbox. Check that it is stored with the right account and that it stays unread on the server
- [ ] 11.4 Make one account fail (wrong password in a copy of the file). Check that the other accounts still sync, the run returns an error, and the healthcheck turns unhealthy after 15 minutes
- [ ] 11.5 Check that a test mail rated `important` reaches the phone with the account name

## 12. Finish

- [ ] 12.1 Run the full test suite with `TEST_DATABASE_URL` and show the result
- [ ] 12.2 Run `openspec validate multi-account --strict`. Check the README against the final behavior
