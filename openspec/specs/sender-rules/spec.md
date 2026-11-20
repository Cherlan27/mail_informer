## Purpose

Lets the owner rate mails from known bulk senders with local rules, so that these mails need no model call and their content is not sent to the model server.

## Requirements

### Requirement: Sender rules are optional
The system SHALL read sender rules only from the file named by the setting `SENDER_RULES_PATH`. If the setting is empty or not set, the system SHALL use no rules and SHALL analyze every mail with the model as before.

#### Scenario: No rule file configured
- **WHEN** `SENDER_RULES_PATH` is not set and the analyzer runs a pass
- **THEN** every waiting mail is rated by the model and no result has the model `rule`

### Requirement: Rule file is checked at start
Each rule SHALL have a unique name, exactly one of a sender address or a sender domain, a category from the known category list, and the importance `ignore` or `normal`. The system SHALL refuse a rule file that breaks any of these checks, has an unknown key, is not valid TOML, cannot be read, or names the same address or domain in two rules. `analyze` and `evaluate` SHALL run this check before any mail is read, and SHALL exit with an error that names the broken rule.

#### Scenario: Rule raises importance
- **WHEN** a rule sets the importance `important` or `urgent`
- **THEN** the analyzer refuses to start, no mail is read, and the error names the rule

#### Scenario: Unknown category
- **WHEN** a rule sets a category that is not in the known list
- **THEN** the analyzer refuses to start and the error names the rule

#### Scenario: Address and domain in one rule
- **WHEN** a rule gives both a sender address and a sender domain, or neither
- **THEN** the analyzer refuses to start and the error names the rule

#### Scenario: Duplicate rule
- **WHEN** two rules have the same name or name the same address or domain
- **THEN** the analyzer refuses to start

#### Scenario: Unknown key
- **WHEN** a rule contains a key that is not part of the rule format
- **THEN** the analyzer refuses to start and the error names the rule and the key

#### Scenario: File missing
- **WHEN** `SENDER_RULES_PATH` names a file that does not exist
- **THEN** the analyzer refuses to start

#### Scenario: Evaluation with a broken rule file
- **WHEN** `evaluate` runs with a broken rule file
- **THEN** it refuses to start and no model call is made

### Requirement: Rule matching
A rule SHALL match a mail by the address in its `From` header, without the display name, compared without regard to case. An address rule SHALL match only that exact address. A domain rule SHALL match only addresses whose domain is exactly that domain; subdomains SHALL NOT match. If both an address rule and a domain rule match, the address rule SHALL win. A mail without a readable sender address SHALL match no rule. Subject and body SHALL NOT be used.

#### Scenario: Exact address
- **WHEN** a rule names `jobs@example.com` and a mail comes from `"Example Jobs" <Jobs@Example.com>`
- **THEN** the rule matches

#### Scenario: Domain
- **WHEN** a rule names the domain `example.com` and a mail comes from `news@example.com`
- **THEN** the rule matches

#### Scenario: Subdomain does not match
- **WHEN** a rule names the domain `example.com` and a mail comes from `news@mail.example.com`
- **THEN** the rule does not match

#### Scenario: Address rule wins
- **WHEN** an address rule and a domain rule both match a mail
- **THEN** the mail is rated by the address rule

#### Scenario: No sender address
- **WHEN** a mail has no `From` header or no readable address in it
- **THEN** no rule matches and the model rates the mail

### Requirement: A matching rule rates the mail without the model
For a waiting mail that matches a rule, the system SHALL store a `done` result for the current prompt version with the rule's category and importance, an empty summary, the model name `rule`, and a reason that names the rule. The system SHALL NOT send any part of that mail to the model server. A rule result SHALL replace a `pending` result of the same mail and prompt version.

#### Scenario: Rule result is stored
- **WHEN** a waiting mail matches the rule `linkedin-jobs` with category `job` and importance `ignore`
- **THEN** the stored result is `done` with category `job`, importance `ignore`, no summary, model `rule`, and a reason that contains `linkedin-jobs`, and the model received no request for that mail

#### Scenario: Pending result is replaced
- **WHEN** a mail has a `pending` result after one invalid model answer and now matches a rule
- **THEN** the result becomes the `done` rule result and no second row exists

#### Scenario: Rule mails without a model server
- **WHEN** the model server cannot be reached and a pass picks one mail that matches a rule and one that does not
- **THEN** the matching mail gets its rule result, the other mail keeps no finished result, and the pass ends as "model server unavailable"

### Requirement: Rule changes affect only waiting mails
The system SHALL apply the rules only to mails that have no finished result for the current prompt version. A change of the rule file SHALL NOT change or re-rate existing `done` or `failed` results.

#### Scenario: Rule added later
- **WHEN** a mail already has a `done` model result and a rule for its sender is added
- **THEN** the next pass leaves that result unchanged

### Requirement: Rule decisions are logged
After each pass the system SHALL log how many mails rules decided, in total and per rule name. The log SHALL NOT contain sender addresses or mail content.

#### Scenario: Pass with rule hits
- **WHEN** a pass rates two mails by the rule `shop-ads` and one mail by the model
- **THEN** the log shows two mails decided by rules, two for `shop-ads`, and no sender address

### Requirement: Evaluation reports rule hits
If rules are configured, `evaluate` SHALL report how many labeled mails the rules would catch, how many of those match the label's category and importance, and the IDs of caught mails labeled `important` or `urgent`. The model SHALL still rate every labeled mail, so the model numbers stay the same with and without rules. Without rules the report SHALL have no rule part.

#### Scenario: Rule catches an important mail
- **WHEN** a rule matches a labeled mail whose label is `important`
- **THEN** the report lists that mail's ID among the caught important or urgent mails

#### Scenario: Model numbers unchanged
- **WHEN** the same labels are evaluated with the same model once without rules and once with rules
- **THEN** the model part of both reports is the same

#### Scenario: No rules
- **WHEN** `evaluate` runs without `SENDER_RULES_PATH`
- **THEN** the report has no rule part
