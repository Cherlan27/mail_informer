## Purpose

Defines which mail data is stored permanently in Postgres and how the state for sync and later analysis is kept.

## ADDED Requirements

### Requirement: Stored mail fields
The system SHALL store, for each mail, the Gmail message ID, thread ID, received date, sender, recipients, subject, labels, snippet, `body_text`, and the fetch time. The Gmail message ID SHALL identify the mail uniquely.

#### Scenario: Normal mail
- **WHEN** a mail with a text/plain part is imported
- **THEN** all listed fields are stored and `body_text` contains the plain text

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
The system SHALL keep an analysis status for each mail. New mails SHALL have the value `pending`. The poller SHALL never change it.

#### Scenario: New mail
- **WHEN** a mail is imported
- **THEN** its analysis status is `pending`

### Requirement: Persistent sync state
The system SHALL store the sync point in the database so that it survives container restarts.

#### Scenario: Restart
- **WHEN** the containers are restarted
- **THEN** the next run continues from the stored sync point

### Requirement: Schema initialization
The system SHALL create or update the database schema by itself when needed.

#### Scenario: Empty database
- **WHEN** the poller starts against an empty database
- **THEN** the required tables are created
