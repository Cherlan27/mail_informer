## MODIFIED Requirements

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
