## ADDED Requirements

### Requirement: Model server settings
The system SHALL talk to one model server that speaks the OpenAI-compatible chat completions API. The server address SHALL be configurable and SHALL default to the Ollama server on the host. An access key SHALL be optional. If a key is set, it SHALL be sent with every request and SHALL NOT appear in logs or error messages. If the old setting `OLLAMA_URL` is set and the new address setting is not, the system SHALL refuse to start and name the new setting.

#### Scenario: Default address
- **WHEN** no model server address is configured
- **THEN** the analyzer uses the OpenAI-compatible endpoint of the Ollama server on the host

#### Scenario: Key is sent
- **WHEN** an access key is configured
- **THEN** every request to the model server carries it as a bearer token

#### Scenario: No key
- **WHEN** no access key is configured
- **THEN** requests carry no authorization header

#### Scenario: Key stays secret
- **WHEN** the model server rejects the key or cannot be reached
- **THEN** the logged error does not contain the key

#### Scenario: Old setting still in use
- **WHEN** `OLLAMA_URL` is set and the new address setting is not
- **THEN** the analyzer refuses to start and the error names the new setting

### Requirement: Answer follows the schema
The system SHALL ask the model server to return an answer that follows the JSON schema of the request in strict mode. It SHALL request a deterministic answer (temperature 0 and a fixed seed). It SHALL still check every answer itself, whatever the server promises.

#### Scenario: Request asks for the schema
- **WHEN** the analyzer asks the model about a mail
- **THEN** the request names the JSON schema in strict mode, temperature 0, and the fixed seed, and carries no tools

#### Scenario: Server ignores the schema
- **WHEN** the model server returns JSON that does not follow the schema
- **THEN** the answer is rejected and the attempt counts as failed

### Requirement: Reasoning effort is optional
The system SHALL offer an optional setting for the reasoning effort of the model. If the setting has a value, the system SHALL send it with every request. If it is empty, the system SHALL NOT send any reasoning field.

#### Scenario: Setting is used
- **WHEN** the reasoning effort is set to `none`
- **THEN** every request to the model server carries the reasoning effort `none`

#### Scenario: Setting is empty
- **WHEN** the reasoning effort is not set
- **THEN** the requests carry no reasoning field

### Requirement: Refused or cut-off answer
The system SHALL treat an answer that the model refused, or that was cut off before it was complete, as an invalid answer for that mail.

#### Scenario: Model refuses
- **WHEN** the model server returns a refusal instead of content
- **THEN** the attempt for that mail counts as failed and other mails are still analyzed

#### Scenario: Answer cut off
- **WHEN** the model server reports that the answer stopped at the length limit
- **THEN** the attempt for that mail counts as failed

## RENAMED Requirements

- FROM: `### Requirement: Mail content stays local`
- TO: `### Requirement: Mail content goes only to the configured model server`

## MODIFIED Requirements

### Requirement: Model server unavailable
If the model server cannot be reached, answers with an error status, rejects the access key, or limits the request rate, the system SHALL end the run with an error and a log message. It SHALL NOT count this as a failed attempt for any mail.

#### Scenario: Model server is off
- **WHEN** the model server cannot be reached during a run
- **THEN** the error is logged, no mail is marked failed, and the next run tries again

#### Scenario: Key rejected
- **WHEN** the model server answers that the access key is not valid
- **THEN** the run ends with an error, no mail is marked failed, and the next run tries again

#### Scenario: Rate limit
- **WHEN** the model server answers that too many requests were sent
- **THEN** the run ends with an error, no mail is marked failed, and the next run tries again

### Requirement: Mail content goes only to the configured model server
The system SHALL send mail content only to the one configured model server. It SHALL NOT send mail content to any other service. By default the model server SHALL be local: on this machine (loopback or the Docker host name) or at a private network IP address. The system SHALL use a model server at any other address only if remote use is explicitly allowed by a setting. A remote model server SHALL be reached over HTTPS only. These checks SHALL run before any mail is read.

#### Scenario: Configuration
- **WHEN** the analyzer starts
- **THEN** it uses only the configured model server address

#### Scenario: Local server
- **WHEN** the configured address is on this machine or at a private network IP address
- **THEN** the analyzer starts without the remote setting

#### Scenario: Remote server without permission
- **WHEN** the configured address is a public host name and remote use is not allowed
- **THEN** the analyzer and the evaluation refuse to start, no mail is read, and the error explains the remote setting

#### Scenario: Remote server with permission
- **WHEN** the configured address is a public host name with `https://` and remote use is allowed
- **THEN** the analyzer starts and sends mail content only to that address

#### Scenario: Remote server without HTTPS
- **WHEN** remote use is allowed but the configured remote address starts with `http://`
- **THEN** the analyzer refuses to start
