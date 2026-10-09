## Purpose

Defines which analyzed mails are sent to the phone through Home Assistant, what the message contains, and which limits and safety rules apply to it.

## ADDED Requirements

### Requirement: Report important and urgent mails
The system SHALL send one message to Home Assistant for each analyzed mail that is rated `urgent` or `important`. Mails with any other rating SHALL NOT be reported. Each message SHALL be sent on its own, without bundling.

#### Scenario: Urgent mail
- **WHEN** a mail is analyzed and rated `urgent`
- **THEN** one message for this mail is sent to Home Assistant

#### Scenario: Important mail
- **WHEN** a mail is analyzed and rated `important`
- **THEN** one message for this mail is sent to Home Assistant

#### Scenario: Other ratings
- **WHEN** a mail is rated `normal` or `ignore`
- **THEN** no message is sent for it

#### Scenario: Failed analysis
- **WHEN** a mail has no finished analysis result
- **THEN** no message is sent for it

### Requirement: Message content
A message about a mail SHALL contain only the category, the importance level, the sender, and the summary. It SHALL NOT contain the mail ID, the subject, or any part of the body. The sender and the summary SHALL be cleaned of control characters and cut to a maximum length.

#### Scenario: Normal message
- **WHEN** a mail is reported
- **THEN** the message has the category, the importance, the sender, and the summary, and no other mail data

#### Scenario: Long or unclean text
- **WHEN** the summary or the sender is longer than the maximum or has control characters
- **THEN** the message has the cleaned text, cut to the maximum

### Requirement: Report each mail once
The system SHALL report a mail at most once. It SHALL record a reported mail in storage that is separate from the analysis results. A new analysis of the same mail, for example with a new prompt version, SHALL NOT cause a second message.

#### Scenario: Repeated pass
- **WHEN** a pass runs again after a mail was reported
- **THEN** no second message is sent for that mail

#### Scenario: Re-analysis
- **WHEN** a reported mail is analyzed again with a new prompt version
- **THEN** no second message is sent for it

### Requirement: Start point
The system SHALL report only mails whose analysis finished after the notifier first ran. Mails analyzed before that SHALL NOT be reported.

#### Scenario: First start with an existing archive
- **WHEN** the notifier runs for the first time and the archive holds analyzed `important` mails
- **THEN** no message is sent for those mails

#### Scenario: Mail analyzed after the start
- **WHEN** a mail is analyzed after the notifier first ran and is rated `important`
- **THEN** it is reported

### Requirement: Hourly limit
The system SHALL send at most 10 single messages in any hour. If more mails are ready, it SHALL send one collective message with the number of the remaining mails, and it SHALL NOT report those mails again.

#### Scenario: Flood of mails
- **WHEN** 25 reportable mails are ready and no message was sent in the last hour
- **THEN** 10 single messages and one collective message with the number 15 are sent

#### Scenario: Limit already used
- **WHEN** 10 single messages were sent in the last hour and one more mail is ready
- **THEN** it is not sent as a single message and a collective message with the number 1 is sent

### Requirement: Age limit
The system SHALL NOT report a mail whose analysis finished more than 6 hours ago.

#### Scenario: Home Assistant down for a long time
- **WHEN** a reportable mail has waited for more than 6 hours because Home Assistant was not reachable
- **THEN** it is not reported when Home Assistant is back

### Requirement: Home Assistant not reachable
If Home Assistant cannot be reached or answers with an error, the system SHALL record nothing for the mails of that message, end the pass with an error status and a log message, and try again in the next pass. It SHALL NOT lose or skip any mail because of the error.

#### Scenario: Home Assistant is off
- **WHEN** a pass cannot reach Home Assistant
- **THEN** the error is logged, no mail is recorded as reported, and the pass ends with an error status

#### Scenario: Recovery
- **WHEN** Home Assistant is reachable again in a later pass within the age limit
- **THEN** the waiting mails are reported

### Requirement: Only the rating decides
The system SHALL decide whether to report a mail only from the importance level. The summary and other model text SHALL be sent as plain text for display and SHALL NOT be used to make any decision or to trigger any action.

#### Scenario: Summary tells to act
- **WHEN** the summary of an `important` mail contains text that tells the receiver to do something
- **THEN** the message is sent as usual and nothing else is done

### Requirement: Webhook address is a secret
The system SHALL read the Home Assistant webhook address from the environment and SHALL fail early if it is missing or is not an HTTP address. It SHALL NOT write the address to the log.

#### Scenario: Address missing
- **WHEN** the notifier starts without a webhook address
- **THEN** it stops with an error that names the missing setting

#### Scenario: Log content
- **WHEN** a message is sent or fails
- **THEN** the log does not contain the webhook address or any mail text
