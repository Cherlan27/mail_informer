## MODIFIED Requirements

### Requirement: Rule file is checked at start
Each rule SHALL have a unique name, exactly one of a sender address or a sender domain, a category from the known category list, and the importance `ignore` or `normal`. Rule names SHALL be compared without regard to case. A domain, and the domain part of a sender, SHALL be a valid host name: at least two labels, each 1-63 characters of `a-z`, `0-9` and `-`, not starting or ending with `-`. Only the rule name SHALL be trimmed; any other value with leading or trailing whitespace SHALL be refused. The system SHALL refuse a rule file that breaks any of these checks, has an unknown key, is not valid TOML, cannot be read, names the same address or domain in two rules, or gives a sender that is not a plain address. `analyze` and `evaluate` SHALL run this check before any mail is read, and SHALL exit with an error that names the broken rule. Only rule file errors SHALL be reported as a refused rule file; any other error SHALL stay visible as itself.

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

#### Scenario: Rule names that differ only in case
- **WHEN** one rule is named `Ads` and another `ads`
- **THEN** the analyzer refuses to start because the name is used twice

#### Scenario: Unknown key
- **WHEN** a rule contains a key that is not part of the rule format
- **THEN** the analyzer refuses to start and the error names the rule and the key

#### Scenario: Several unknown keys
- **WHEN** a rule contains two unknown keys `zeta` and `alpha`
- **THEN** the error names them in sorted order, the same on every run

#### Scenario: File missing
- **WHEN** `SENDER_RULES_PATH` names a file that does not exist
- **THEN** the analyzer refuses to start

#### Scenario: Evaluation with a broken rule file
- **WHEN** `evaluate` runs with a broken rule file
- **THEN** it refuses to start and no model call is made

#### Scenario: Sender is not a plain address
- **WHEN** a rule gives a sender such as `LinkedIn <jobs@linkedin.com>`, with a display name or other text around the address
- **THEN** the analyzer refuses to start and the error names the rule

#### Scenario: Sender with an invalid address part
- **WHEN** a rule gives a sender such as `a b@x.com`, `a@.com`, or `a@x..com`
- **THEN** the analyzer refuses to start and the error names the rule

#### Scenario: Domain is not a valid host name
- **WHEN** a rule gives a domain such as `.example.com`, `example.com.`, `exa mple.com`, `example..com`, `-example.com`, `example`, `http://example.com`, or `example.com/x`
- **THEN** the analyzer refuses to start and the error names the rule

#### Scenario: Valid domain still passes
- **WHEN** a rule gives a domain such as `Mail.Example-Shop.co.uk`
- **THEN** the rule is accepted and stored in lower case

#### Scenario: Value with surrounding whitespace
- **WHEN** a rule gives a sender, domain, category, or importance with a leading or trailing space, such as ` example.com` or `newsletter `
- **THEN** the analyzer refuses to start and the error names the rule and the field

#### Scenario: Rule name with surrounding whitespace
- **WHEN** a rule named ` shop-ads ` breaks a check
- **THEN** the error shows the name without the surrounding whitespace

#### Scenario: Other errors are not reported as a broken rule file
- **WHEN** loading the rules fails with an error that is not a rule file error
- **THEN** that error is raised as itself and is not reported as `SENDER_RULES_PATH is refused`
