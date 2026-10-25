## Purpose

Defines how stored mails are rated for importance and summarized by a local language model, and which safety limits apply to the model output.

## Requirements

### Requirement: Analyze every stored mail
The system SHALL analyze each stored mail that has no finished result for the current prompt version. It SHALL work through such mails without a manual start.

#### Scenario: New mails are picked up
- **WHEN** three stored mails have no analysis result
- **THEN** the next analysis run produces a result for each of the three

#### Scenario: Nothing to do
- **WHEN** every stored mail already has a finished result
- **THEN** the run ends successfully without calling the model

### Requirement: Classification
For each analyzed mail, the system SHALL assign exactly one category and exactly one importance level. The category SHALL be one of: `security`, `personal`, `work`, `authority`, `appointment`, `invoice`, `delivery`, `job`, `newsletter`, `advertising`, `other`. The importance SHALL be one of: `ignore`, `normal`, `important`, `urgent`.

#### Scenario: Valid rating
- **WHEN** the model returns a known category and a known importance level
- **THEN** both values are stored for the mail

#### Scenario: Unknown value
- **WHEN** the model returns a category or importance level that is not in the allowed list
- **THEN** the answer is rejected, nothing is stored from it, and the attempt counts as failed

### Requirement: Classification input is limited
The system SHALL give the model only the sender, the subject, and a limited first part of the body for classification. Very long mails SHALL NOT be sent in full.

#### Scenario: Very long mail
- **WHEN** a mail body is longer than the configured limit
- **THEN** the model receives only the first part up to that limit

### Requirement: Summary for important mails only
The system SHALL create a summary only for mails rated `important` or `urgent`. The summary SHALL be written in German and SHALL be at most two sentences. Mails with other ratings SHALL have no summary.

#### Scenario: Important mail
- **WHEN** a mail is rated `important` or `urgent`
- **THEN** a German summary of at most two sentences is stored with the result

#### Scenario: Unimportant mail
- **WHEN** a mail is rated `ignore` or `normal`
- **THEN** no summary is created and the model is not asked for one

### Requirement: Bulk mail is never urgent
The system SHALL lower the importance of a mail from `urgent` to `important` if the mail is marked as bulk mail. This rule SHALL be applied by the system itself and SHALL NOT depend on the model following an instruction.

#### Scenario: Newsletter rated urgent
- **WHEN** the model rates a bulk mail as `urgent`
- **THEN** the stored importance is `important`

#### Scenario: Personal mail rated urgent
- **WHEN** the model rates a mail that is not bulk mail as `urgent`
- **THEN** the stored importance stays `urgent`

### Requirement: Model output triggers no action
The system SHALL treat all model output as data. The model SHALL NOT be given any tool, command, or way to call another system. Free text produced by the model (summary, reason) SHALL NOT be used to make a decision. Only the category and the importance level may be used for decisions.

#### Scenario: Mail contains instructions
- **WHEN** a mail contains text that tells the model to do something
- **THEN** the system performs no action except storing the rating and the summary

### Requirement: Retry and permanent failure
The system SHALL retry a failed analysis of a mail up to a fixed number of attempts. After the last attempt, the mail SHALL be marked as failed. A failing mail SHALL NOT block the analysis of other mails.

#### Scenario: One mail keeps failing
- **WHEN** the model gives an invalid answer for one mail on every attempt
- **THEN** that mail is marked failed after the last attempt and all other mails are still analyzed

#### Scenario: Retry succeeds
- **WHEN** the first attempt fails and the second attempt returns a valid answer
- **THEN** the mail is marked done with the valid result

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

### Requirement: Refused or cut-off answer
The system SHALL treat an answer that the model refused, or that was cut off before it was complete, as an invalid answer for that mail.

#### Scenario: Model refuses
- **WHEN** the model server returns a refusal instead of content
- **THEN** the attempt for that mail counts as failed and other mails are still analyzed

#### Scenario: Answer cut off
- **WHEN** the model server reports that the answer stopped at the length limit
- **THEN** the attempt for that mail counts as failed

### Requirement: Idempotency
The system SHALL store at most one result per mail and prompt version. Running the analysis again SHALL NOT create duplicate results.

#### Scenario: Repeated run
- **WHEN** a run is repeated after an abort
- **THEN** mails that already have a finished result are skipped and no duplicates appear

### Requirement: Mail content goes only to the configured model server
The system SHALL send mail content only to the one configured model server. It SHALL NOT send mail content to any other service. By default the model server SHALL be local: on this machine (loopback or the Docker host name) or at a private network IP address. The system SHALL use a model server at any other address only if remote use is explicitly allowed by a setting. A remote model server SHALL be reached over HTTPS only. The address SHALL use `http` or `https`. The system SHALL NOT follow redirects of the model server. These checks SHALL run before any mail is read.

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

#### Scenario: Address is not HTTP
- **WHEN** the configured address uses a scheme other than `http` or `https`
- **THEN** the analyzer refuses to start

#### Scenario: Server redirects
- **WHEN** the model server answers a request with a redirect to another address
- **THEN** the redirect is not followed, neither mail content nor the access key is sent to the other address, and the run ends as "model server unavailable"

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

### Requirement: Model quality can be measured
The system SHALL provide a way to run a set of hand-labeled mails through a chosen model and report how often its rating matches the label. A model SHALL be adopted only after such a measurement.

#### Scenario: Compare models
- **WHEN** the labeled set is run with two different models
- **THEN** the report shows, for each model, the share of correct categories and importance levels, and how many `urgent` mails were missed
