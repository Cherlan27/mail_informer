## ADDED Requirements

### Requirement: Notifier health reporting
The system SHALL report the notifier as unhealthy if it has not completed a successful pass for more than a set time while reportable mails exist.

#### Scenario: Notifier stuck
- **WHEN** reportable mails exist and no pass has succeeded for longer than the set time
- **THEN** the container healthcheck of the notifier fails

#### Scenario: Nothing to report
- **WHEN** no reportable mails exist
- **THEN** the notifier is reported as healthy

## MODIFIED Requirements

### Requirement: Start with Compose
The system SHALL start Postgres, the poller, the analyzer, and the notifier with a single `docker compose up`. The model server SHALL run on the host and SHALL NOT be part of the stack. The notifier SHALL NOT need the model server, and the analyzer SHALL NOT need Home Assistant.

#### Scenario: Start the stack
- **WHEN** the user runs `docker compose up -d` after the authorization is done
- **THEN** Postgres, the poller, the analyzer, and the notifier run and the data is kept in a persistent volume

#### Scenario: Model server not running yet
- **WHEN** the stack starts while the model server is off
- **THEN** the poller and the notifier work as usual and the analyzer waits and tries again later

#### Scenario: Home Assistant not running yet
- **WHEN** the stack starts while Home Assistant is off
- **THEN** the poller and the analyzer work as usual and the notifier waits and tries again later
