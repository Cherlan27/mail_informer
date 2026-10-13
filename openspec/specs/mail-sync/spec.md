## Purpose

Describes how new Gmail mails are fetched from the Gmail account incrementally and idempotently, without loading old mails.

## Requirements

### Requirement: Initialize from now
On the very first run of an account, the system SHALL store the current sync point of that account as the starting point and SHALL NOT import any existing mails of it.

#### Scenario: First run
- **WHEN** no sync state exists for an account and the poller runs
- **THEN** the current sync point of this account is stored and no mail of it is written to the database

### Requirement: Incremental fetch of new mails
On each run, the system SHALL import, for each account, all mails that arrived since the stored sync point of that account, and then advance that sync point.

#### Scenario: New mails present
- **WHEN** three new mails arrived in an account since the last run
- **THEN** three mails are stored for this account and its sync point is set to the latest state

#### Scenario: No new mails
- **WHEN** nothing arrived since the last run
- **THEN** the stored mails do not change and the run ends successfully

### Requirement: Idempotency
The system SHALL store the same mail at most once, even if it appears in several runs or several times in one Gmail API response.

#### Scenario: Repeated run
- **WHEN** a run processes the same range again after an abort
- **THEN** no duplicate entries are created

### Requirement: Sync point only after a successful write
The system SHALL advance the sync point only after all mails that belong to it were stored successfully.

#### Scenario: Error while storing
- **WHEN** storing a mail fails
- **THEN** the old sync point is kept and the next run fetches the mail again

### Requirement: Fallback when the sync point has expired
If Gmail no longer accepts the stored sync point, the system SHALL reload mails based on the date of the last stored mail and then set a new sync point.

#### Scenario: Long pause
- **WHEN** the poller did not run for longer than the sync point stays valid
- **THEN** the mails that arrived in the meantime are loaded without duplicates and a new sync point is stored

### Requirement: New mails only, no follow-up
The system SHALL consider only mails added to the account. Deletions and label or status changes of existing mails SHALL NOT be applied to the database.

#### Scenario: Mail deleted
- **WHEN** an already stored mail is deleted in Gmail
- **THEN** it stays unchanged in the database
