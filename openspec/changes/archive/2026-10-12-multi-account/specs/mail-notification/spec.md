## MODIFIED Requirements

### Requirement: Message content
A message about a mail SHALL contain only the account name, the category, the importance level, the sender, and the summary. It SHALL NOT contain the mail ID, the subject, or any part of the body. The sender and the summary SHALL be cleaned of control characters and cut to a maximum length.

#### Scenario: Normal message
- **WHEN** a mail is reported
- **THEN** the message has the account name, the category, the importance, the sender, and the summary, and no other mail data

#### Scenario: Mails of different accounts
- **WHEN** an important mail arrives in each of two accounts
- **THEN** each message names its own account

#### Scenario: Long or unclean text
- **WHEN** the summary or the sender is longer than the maximum or has control characters
- **THEN** the message has the cleaned text, cut to the maximum
