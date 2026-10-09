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
If the model server cannot be reached, the system SHALL end the run with an error and a log message. It SHALL NOT count this as a failed attempt for any mail.

#### Scenario: Model server is off
- **WHEN** the model server cannot be reached during a run
- **THEN** the error is logged, no mail is marked failed, and the next run tries again

### Requirement: Idempotency
The system SHALL store at most one result per mail and prompt version. Running the analysis again SHALL NOT create duplicate results.

#### Scenario: Repeated run
- **WHEN** a run is repeated after an abort
- **THEN** mails that already have a finished result are skipped and no duplicates appear

### Requirement: Mail content stays local
The system SHALL send mail content only to the model server that is configured for the local machine. It SHALL NOT send mail content to any other service.

#### Scenario: Configuration
- **WHEN** the analyzer starts
- **THEN** it uses only the configured local model server address

### Requirement: Model quality can be measured
The system SHALL provide a way to run a set of hand-labeled mails through a chosen model and report how often its rating matches the label. A model SHALL be adopted only after such a measurement.

#### Scenario: Compare models
- **WHEN** the labeled set is run with two different models
- **THEN** the report shows, for each model, the share of correct categories and importance levels, and how many `urgent` mails were missed
