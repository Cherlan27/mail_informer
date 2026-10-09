## Purpose

Describes operation and setup of the poller: the container stack, the one-time OAuth authorization, and the 30-minute scheduling.

## Requirements

### Requirement: Start with Compose
The system SHALL start Postgres, the poller, and the analyzer with a single `docker compose up`. The model server SHALL run on the host and SHALL NOT be part of the stack.

#### Scenario: Start the stack
- **WHEN** the user runs `docker compose up -d` after the authorization is done
- **THEN** Postgres, the poller, and the analyzer run and the data is kept in a persistent volume

#### Scenario: Model server not running yet
- **WHEN** the stack starts while the model server is off
- **THEN** the poller works as usual and the analyzer waits and tries again later
### Requirement: Periodic execution
The system SHALL start the fetch every 30 minutes as a separate run that ends when it is done.

#### Scenario: Schedule
- **WHEN** the stack is running
- **THEN** a run starts about every 30 minutes

#### Scenario: No parallel runs
- **WHEN** a run is still active when the next one starts
- **THEN** the new run does not start in parallel

### Requirement: One-time OAuth authorization on the host
The system SHALL provide a command that performs the Gmail OAuth consent in the browser on the host and stores the credentials for the poller container. The access SHALL be limited to reading mails.

#### Scenario: First authorization
- **WHEN** the user runs the auth command and agrees in the browser
- **THEN** a token is stored that the container uses, and it grants read access only

### Requirement: Token refresh
The system SHALL refresh the access token by itself using the refresh token and SHALL keep the updated token persistent.

#### Scenario: Expired access token
- **WHEN** the access token has expired during a run
- **THEN** it is refreshed and the run continues normally

### Requirement: Error behavior
On errors (network, API, database, auth), the system SHALL end the run with an error status and a log message, without stopping the scheduler, so that the next run tries again.

#### Scenario: Gmail not reachable
- **WHEN** the Gmail API cannot be reached during a run
- **THEN** the error is logged, nothing is advanced, and the next scheduled run tries again

### Requirement: Health reporting
The system SHALL report the poller as unhealthy when the last successful sync is older than 90 minutes.

#### Scenario: Syncs keep failing
- **WHEN** no run has succeeded for more than 90 minutes
- **THEN** the container healthcheck fails

### Requirement: Secrets outside the repository
The system SHALL NOT keep the client secret, token, or database password in the repository.

#### Scenario: Repository content
- **WHEN** the repository is checked
- **THEN** secrets are excluded by ignore rules and only example configuration is included

### Requirement: Analyzer health reporting
The system SHALL report the analyzer as unhealthy if it has not completed a successful pass for more than a set time while unanalyzed mails exist.

#### Scenario: Analyzer stuck
- **WHEN** unanalyzed mails exist and no pass has succeeded for longer than the set time
- **THEN** the container healthcheck of the analyzer fails

#### Scenario: Nothing to analyze
- **WHEN** no unanalyzed mails exist
- **THEN** the analyzer is reported as healthy
