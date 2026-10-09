## MODIFIED Requirements

### Requirement: Health reporting
The system SHALL report the poller as unhealthy when the last successful sync of any account in the accounts file is older than 15 minutes.

#### Scenario: Syncs keep failing
- **WHEN** no run has succeeded for any account for more than 15 minutes
- **THEN** the container healthcheck fails

#### Scenario: One account keeps failing
- **WHEN** one account has had no successful sync for more than 15 minutes while the others are fine
- **THEN** the container healthcheck fails

#### Scenario: New account without a sync yet
- **WHEN** an account was just added and its first run has not finished
- **THEN** it counts as unhealthy only after 15 minutes

### Requirement: Secrets outside the repository
The system SHALL NOT keep the client secret, token, IMAP passwords, accounts file, or database password in the repository.

#### Scenario: Repository content
- **WHEN** the repository is checked
- **THEN** secrets and the accounts file are excluded by ignore rules and only example configuration is included
