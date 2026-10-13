## Why

The poller reads one Gmail account. The user also has three mailboxes at Strato, which offers IMAP with a password and no OAuth. Their mails should go through the same pipeline: archive, analysis, and phone message.

## What Changes

- New accounts file `secrets/accounts.toml` (git-ignored, mounted read-only like the other secrets). It lists every account: the existing Gmail account and the three Strato mailboxes. Each account has a unique name.
- New IMAP source for Strato. It reads only `INBOX`, only mails with a higher UID than the last one it saw, and never changes the server state (no "read" flag, no deletion).
- The sync point becomes one value per account and source. It is a plain text that only the source understands (Gmail: the history ID; IMAP: the UID validity and the last UID).
- Each stored mail knows its account. Existing mails move to the account named `gmail`.
- The first run of a new account stores the starting point and imports nothing. Only mails that arrive afterwards are imported, analyzed, and reported.
- One run syncs all accounts one after the other. A failing account does not stop the others.
- The phone message also names the account, so the user can tell the mailboxes apart.
- The poller healthcheck looks at every account. It is unhealthy when any account has no successful sync for more than 15 minutes.
- No new dependency. IMAP and mail parsing use the Python standard library.

## Non-goals

- No folders other than `INBOX`. No spam or sent folders.
- No IMAP IDLE (push). The 5-minute poll stays.
- No other login method than user name and password for IMAP.
- No per-account prompt, rating, or notification rule. All accounts use the same analysis.
- No commands to add or remove accounts. The user edits `accounts.toml`.
- No deletion, marking, or moving of mails on the server.
- No renaming of the `gmail_id` column. It stays the unique mail key for all accounts (see design).
- No follow-up of deleted or moved mails, as today.

## Capabilities

### New Capabilities
- `mail-accounts`: The accounts file, account names, secrets handling, and how one run treats several accounts, including failure isolation.
- `imap-sync`: How new mails are fetched from an IMAP mailbox: `INBOX` only, UID based, read-only, start from now, reset when the server changes the UID validity.

### Modified Capabilities
- `mail-sync`: The sync point and the start rule apply per account, not once for the system.
- `mail-storage`: Each mail has an account. The mail key stays unique across accounts. The sync state is kept per account.
- `mail-notification`: The message also contains the account name.
- `poller-runtime`: The poller healthcheck covers every account. The accounts file holds passwords and stays out of the repository.

## Impact

- New migration `005_accounts.sql`: column `messages.account` (existing rows get `gmail`), `sync_state` keyed by account instead of the single row.
- New modules: `mail_informer/accounts.py` (load and check the file), `mail_informer/imap.py` (IMAP access only, no database code). `parsing.py` gets a pure function for raw RFC 822 mails. `sync.py` loses the Gmail-specific cursor. `gmail.py` adapts to the new source protocol. `db.py`, `cli.py`, and `notify/` get the account.
- New setting `ACCOUNTS_PATH` (default `secrets/accounts.toml`). `TOKEN_PATH` moves into the accounts file as the Gmail token path.
- **BREAKING**: the poller needs `accounts.toml`. Without it, it fails at start. The README shows how to write it for the existing Gmail account.
- No new dependency. `tomllib` and `imaplib` are in the standard library.
- Analyzer logic and prompt do not change.
