## Purpose

Defines how analysis results are stored in Postgres, separate from the archived mail, so that results can be repeated and compared.

## Requirements

### Requirement: Results are stored apart from the archive
The system SHALL store analysis results in their own table and SHALL NOT change the archived mail when it analyzes it.

#### Scenario: Analysis of a mail
- **WHEN** a mail is analyzed
- **THEN** a result is written to the analysis table and the stored mail fields stay unchanged

### Requirement: Stored result fields
The system SHALL store, for each result, the Gmail message ID of the mail, the category, the importance level, the summary (empty if none), a short reason, the model name, the prompt version, the status, the number of attempts, and the time of the last change.

#### Scenario: Finished result
- **WHEN** an analysis finishes successfully
- **THEN** all listed fields are stored and the status is `done`

### Requirement: Status values
The system SHALL keep a status for each result with one of the values `pending`, `done`, or `failed`. Only `done` results SHALL contain a category and an importance level.

#### Scenario: Failed result
- **WHEN** all attempts for a mail have failed
- **THEN** the status is `failed` and the category and importance level are empty

### Requirement: One result per mail and prompt version
The system SHALL allow only one result for the same mail and the same prompt version. A new prompt version SHALL be able to produce a second result for the same mail without removing the first.

#### Scenario: New prompt version
- **WHEN** a mail is analyzed again with a new prompt version
- **THEN** both results exist and each shows its own model and prompt version

### Requirement: Result belongs to an existing mail
The system SHALL accept a result only for a mail that exists in the archive.

#### Scenario: Unknown mail
- **WHEN** a result is written for a message ID that is not in the archive
- **THEN** the write is rejected

### Requirement: Text fields are plain and bounded
The system SHALL store the summary and the reason as plain text with a maximum length. Longer model output SHALL be cut to that length.

#### Scenario: Overlong summary
- **WHEN** the model returns a summary longer than the maximum length
- **THEN** the stored summary is cut to the maximum length

### Requirement: Schema initialization
The system SHALL create or update the analysis tables by itself with a new migration, without changing earlier migrations.

#### Scenario: Existing database
- **WHEN** the analyzer starts against a database that already holds archived mails
- **THEN** the analysis tables are created and the archived mails are untouched
