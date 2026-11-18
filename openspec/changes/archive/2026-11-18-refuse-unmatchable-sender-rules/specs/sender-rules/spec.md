## MODIFIED Requirements

### Requirement: Rule file is checked at start
Each rule SHALL have a unique name, exactly one of a sender address or a sender domain, a category from the known category list, and the importance `ignore` or `normal`. The system SHALL refuse a rule file that breaks any of these checks, has an unknown key, is not valid TOML, cannot be read, names the same address or domain in two rules, gives a sender that is not a plain address, or gives a domain with a leading or trailing dot or whitespace. `analyze` and `evaluate` SHALL run this check before any mail is read, and SHALL exit with an error that names the broken rule.

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

#### Scenario: Sender is not a plain address
- **WHEN** a rule gives a sender such as `LinkedIn <jobs@linkedin.com>`, with a display name or other text around the address
- **THEN** the analyzer refuses to start and the error names the rule

#### Scenario: Domain with a dot or whitespace at an end
- **WHEN** a rule gives a domain such as `.example.com`, `example.com.`, or ` example.com`
- **THEN** the analyzer refuses to start and the error names the rule

#### Scenario: Rule name with surrounding whitespace
- **WHEN** a rule named ` shop-ads ` breaks a check
- **THEN** the error shows the name without the surrounding whitespace

