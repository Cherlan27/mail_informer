## MODIFIED Requirements

### Requirement: Stored mail fields
The system SHALL store, for each mail, the account name, the mail ID, thread ID, received date, sender, recipients, subject, labels, snippet, `body_text`, and the fetch time. The mail ID SHALL identify the mail uniquely across all accounts. Mails stored before accounts existed SHALL belong to the account `gmail`.

#### Scenario: Normal mail
- **WHEN** a mail with a text/plain part is imported
- **THEN** all listed fields are stored and `body_text` contains the plain text

#### Scenario: Existing mails after the upgrade
- **WHEN** the database is upgraded and it holds mails from before accounts existed
- **THEN** they belong to the account `gmail`, and their analyses and notification records stay linked

### Requirement: Persistent sync state
The system SHALL store the sync point of each account in the database so that it survives container restarts. The sync points of different accounts SHALL be independent.

#### Scenario: Restart
- **WHEN** the containers are restarted
- **THEN** the next run continues each account from its stored sync point

#### Scenario: One account advances
- **WHEN** the sync of one account succeeds and another fails
- **THEN** only the sync point of the successful account moves
