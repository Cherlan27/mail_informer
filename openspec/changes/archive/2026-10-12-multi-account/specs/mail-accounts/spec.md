## Purpose

Defines how the mail accounts are configured and how one poller run treats several accounts, so that one broken account does not block the others.

## ADDED Requirements

### Requirement: Accounts file
The system SHALL read the list of mail accounts from one accounts file. Each account SHALL have a unique name and a kind (`gmail` or `imap`). The system SHALL fail at start with a clear message if the file is missing, cannot be read, has a duplicate name, has an unknown kind, or lacks a value that its kind needs. The message SHALL NOT contain a password.

#### Scenario: Valid file
- **WHEN** the file lists one Gmail account and three IMAP accounts with different names
- **THEN** all four accounts are used

#### Scenario: Duplicate name
- **WHEN** two accounts have the same name
- **THEN** the start fails and the message names the duplicate

#### Scenario: Missing value
- **WHEN** an IMAP account has no password
- **THEN** the start fails and the message names the account and the missing value, without showing other values

#### Scenario: Missing file
- **WHEN** the accounts file does not exist
- **THEN** the start fails and the message says where the file is expected

### Requirement: Passwords stay secret
The system SHALL NOT write passwords from the accounts file to logs, error messages, or the database.

#### Scenario: Login fails
- **WHEN** the login of an IMAP account is refused
- **THEN** the log names the account but not the password

### Requirement: All accounts in one run
One poller run SHALL sync every account in the file, one after the other.

#### Scenario: Four accounts
- **WHEN** a run starts and all four accounts are reachable
- **THEN** new mails of all four accounts are stored

### Requirement: One failing account does not stop the others
If an account fails during a run, the system SHALL log the error with the account name, SHALL continue with the next account, and SHALL end the run with an error status. The failing account SHALL keep its old sync point.

#### Scenario: One mailbox down
- **WHEN** the server of one IMAP account is not reachable and the other accounts are fine
- **THEN** the other accounts are synced, the failing account keeps its sync point, and the run ends with an error status

### Requirement: New account starts from now
The first run of an account without a sync point SHALL store the starting point and SHALL NOT import existing mails of this account. This SHALL NOT change the state of other accounts.

#### Scenario: Account added later
- **WHEN** the user adds a fourth account to the file and the poller runs
- **THEN** only the starting point of the new account is stored, and the other accounts continue as before

### Requirement: Removed account keeps its data
If an account is removed from the file, the system SHALL stop syncing it and SHALL keep its stored mails and analyses.

#### Scenario: Account removed
- **WHEN** an account is no longer in the file
- **THEN** it is not synced and its stored mails stay unchanged
