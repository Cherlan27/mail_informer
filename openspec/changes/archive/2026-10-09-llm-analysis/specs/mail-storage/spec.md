## ADDED Requirements

### Requirement: Bulk mail flag
The system SHALL store, for each mail, whether it is bulk mail. A mail SHALL count as bulk mail if it has a `List-Unsubscribe` header.

#### Scenario: Newsletter
- **WHEN** a mail with a `List-Unsubscribe` header is imported
- **THEN** it is stored as bulk mail

#### Scenario: Personal mail
- **WHEN** a mail without a `List-Unsubscribe` header is imported
- **THEN** it is stored as not bulk mail

## MODIFIED Requirements

### Requirement: Analysis status
The system SHALL keep the analysis state of a mail in the analysis results, not in the archived mail. A mail without a finished analysis result SHALL count as not analyzed. Importing or analyzing a mail SHALL NOT change the archived mail fields after the import.

#### Scenario: New mail
- **WHEN** a mail is imported
- **THEN** it has no analysis result and counts as not analyzed

#### Scenario: Mail after analysis
- **WHEN** a mail has been analyzed
- **THEN** its archived fields are the same as at import
