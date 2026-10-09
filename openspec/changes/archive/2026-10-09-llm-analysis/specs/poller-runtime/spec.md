## ADDED Requirements

### Requirement: Analyzer health reporting
The system SHALL report the analyzer as unhealthy if it has not completed a successful pass for more than a set time while unanalyzed mails exist.

#### Scenario: Analyzer stuck
- **WHEN** unanalyzed mails exist and no pass has succeeded for longer than the set time
- **THEN** the container healthcheck of the analyzer fails

#### Scenario: Nothing to analyze
- **WHEN** no unanalyzed mails exist
- **THEN** the analyzer is reported as healthy

## MODIFIED Requirements

### Requirement: Start with Compose
The system SHALL start Postgres, the poller, and the analyzer with a single `docker compose up`. The model server SHALL run on the host and SHALL NOT be part of the stack.

#### Scenario: Start the stack
- **WHEN** the user runs `docker compose up -d` after the authorization is done
- **THEN** Postgres, the poller, and the analyzer run and the data is kept in a persistent volume

#### Scenario: Model server not running yet
- **WHEN** the stack starts while the model server is off
- **THEN** the poller works as usual and the analyzer waits and tries again later
