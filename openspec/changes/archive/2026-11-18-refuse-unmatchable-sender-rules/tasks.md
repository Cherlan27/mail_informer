## 1. Refuse unmatchable values

- [x] 1.1 Test, then code: scenario "Sender is not a plain address" (`LinkedIn <jobs@linkedin.com>` is refused, a plain address still passes).
- [x] 1.2 Test, then code: scenario "Domain with a dot or whitespace at an end" (`.example.com`, `example.com.`, ` example.com` are refused; the check uses the value before trimming).
- [x] 1.3 Test, then code: scenario "Rule name with surrounding whitespace" (the error label uses the trimmed name).

## 2. Verification

- [x] 2.1 Run `make check` (needs Postgres through `TEST_DATABASE_URL`); it passes twice in a row.
