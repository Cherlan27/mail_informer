## Purpose

Describes how new mails are fetched from an IMAP mailbox, incrementally and without changing anything on the server.

## ADDED Requirements

### Requirement: Inbox only
The system SHALL read only the `INBOX` folder of an IMAP account.

#### Scenario: Other folders
- **WHEN** the mailbox has mails in `Spam` or `Sent`
- **THEN** they are not imported

### Requirement: Incremental fetch by UID
On each run, the system SHALL import the `INBOX` mails with a UID higher than the stored last UID, and then store the highest UID it handled.

#### Scenario: New mails
- **WHEN** three mails with higher UIDs arrived since the last run
- **THEN** three mails are stored and the last UID is the highest of them

#### Scenario: No new mails
- **WHEN** no mail has a higher UID than the stored one
- **THEN** nothing is stored and the run ends successfully, even if the server returns the newest old mail

### Requirement: Start from now
On the first run, the system SHALL store the current end of `INBOX` as the starting point and SHALL NOT import any existing mail.

#### Scenario: First run
- **WHEN** an IMAP account has no sync point and the mailbox holds old mails
- **THEN** the starting point is stored and no mail is written to the database

### Requirement: Read-only access
The system SHALL NOT change anything on the IMAP server. It SHALL NOT set flags (such as "read"), delete, move, or write mails.

#### Scenario: Unread mail
- **WHEN** an unread mail is imported
- **THEN** it is still unread on the server

### Requirement: Encrypted connection
The system SHALL connect to the IMAP server only through a TLS-encrypted connection and SHALL verify the server certificate.

#### Scenario: Invalid certificate
- **WHEN** the server certificate cannot be verified
- **THEN** the account fails and no login data is sent to the server

### Requirement: Stable mail key
The system SHALL give each imported mail a key that is unique across all accounts and does not depend on the UID, so that the same mail is never stored twice, even after the UID numbers change.

#### Scenario: Same mail twice
- **WHEN** the same mail is fetched again under a new UID
- **THEN** no second entry is created

#### Scenario: Same Message-ID in two accounts
- **WHEN** one mail is delivered to two of the accounts
- **THEN** each account stores its own entry

#### Scenario: No Message-ID
- **WHEN** a mail has no `Message-ID` header
- **THEN** it still gets a stable key from other header values

### Requirement: Mail data
For each imported IMAP mail, the system SHALL store the same fields as for other mails: key, thread, received date (the server receive time), sender, recipients, subject, folder as label, a short text snippet, the plain-text body, and the bulk flag. The body rules of `mail-storage` apply (plain text only, no HTML, no attachments, not truncated). A mail with a `List-Unsubscribe` header SHALL count as bulk mail.

#### Scenario: Text mail
- **WHEN** a mail with a text/plain part is imported
- **THEN** the fields are stored and the body is the plain text

#### Scenario: Encoded headers
- **WHEN** the subject or the sender uses an encoded word, for example for an umlaut
- **THEN** the stored value is the decoded text

### Requirement: Reset when the UID numbers change
If the server reports a different UID validity than the stored one, the system SHALL NOT trust the stored UID. It SHALL reload the mails of `INBOX` since the date of the last stored mail of this account (with a one-day buffer), skip mails that are already stored, and store a new sync point.

#### Scenario: Mailbox rebuilt
- **WHEN** the UID validity of `INBOX` has changed
- **THEN** mails that arrived in the meantime are loaded without duplicates and a new sync point is stored

### Requirement: Sync point only after a successful write
The system SHALL advance the sync point of an IMAP account only after all mails up to it were stored.

#### Scenario: Error while storing
- **WHEN** storing a mail fails
- **THEN** the old sync point is kept and the next run fetches the mail again
