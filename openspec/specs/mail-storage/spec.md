## Purpose

Defines which mail data is stored permanently in Postgres and how the state for sync and later analysis is kept.

## Requirements

### Requirement: Stored mail fields
The system SHALL store, for each mail, the account name, the mail ID, thread ID, received date, sender, recipients, subject, labels, snippet, `body_text`, and the fetch time. The mail ID SHALL identify the mail uniquely across all accounts. Mails stored before accounts existed SHALL belong to the account `gmail`.

#### Scenario: Normal mail
- **WHEN** a mail with a text/plain part is imported
- **THEN** all listed fields are stored and `body_text` contains the plain text

#### Scenario: Existing mails after the upgrade
- **WHEN** the database is upgraded and it holds mails from before accounts existed
- **THEN** they belong to the account `gmail`, and their analyses and notification records stay linked

### Requirement: Plain-text body only
The system SHALL store only plain text as the body and SHALL NOT store HTML. If a mail has only an HTML part, the system SHALL derive plain text from it and store that.

#### Scenario: HTML-only mail
- **WHEN** a mail contains only text/html
- **THEN** `body_text` is extracted from the HTML and no HTML is stored

#### Scenario: Mail without text
- **WHEN** a mail contains neither text/plain nor text/html
- **THEN** it is stored with an empty `body_text`

### Requirement: Complete body
The system SHALL store the body without truncation.

#### Scenario: Long mail
- **WHEN** a very long mail is imported
- **THEN** the whole text is stored

### Requirement: No attachments
The system SHALL NOT store attachments.

#### Scenario: Mail with attachment
- **WHEN** a mail with an attachment is imported
- **THEN** the attachment is not stored, but the text and metadata are

### Requirement: Analysis status
The system SHALL keep the analysis state of a mail in the analysis results, not in the archived mail. A mail without a finished analysis result SHALL count as not analyzed. Importing or analyzing a mail SHALL NOT change the archived mail fields after the import.

#### Scenario: New mail
- **WHEN** a mail is imported
- **THEN** it has no analysis result and counts as not analyzed

#### Scenario: Mail after analysis
- **WHEN** a mail has been analyzed
- **THEN** its archived fields are the same as at import

### Requirement: Persistent sync state
The system SHALL store the sync point of each account in the database so that it survives container restarts. The sync points of different accounts SHALL be independent.

#### Scenario: Restart
- **WHEN** the containers are restarted
- **THEN** the next run continues each account from its stored sync point

#### Scenario: One account advances
- **WHEN** the sync of one account succeeds and another fails
- **THEN** only the sync point of the successful account moves

### Requirement: Schema initialization
The system SHALL create or update the database schema by itself when needed.

#### Scenario: Empty database
- **WHEN** the poller starts against an empty database
- **THEN** the required tables are created

### Requirement: Bulk mail flag
The system SHALL store, for each mail, whether it is bulk mail. A mail SHALL count as bulk mail if it has a `List-Unsubscribe` header.

#### Scenario: Newsletter
- **WHEN** a mail with a `List-Unsubscribe` header is imported
- **THEN** it is stored as bulk mail

#### Scenario: Personal mail
- **WHEN** a mail without a `List-Unsubscribe` header is imported
- **THEN** it is stored as not bulk mail
