## 1. Host setup and smoke test

- [ ] 1.1 Install Ollama on the Windows host, pull one small candidate model, and confirm with `ollama ps` that it runs on the GPU
- [ ] 1.2 From a throwaway container, call `http://host.docker.internal:11434/api/chat` with a JSON-schema `format` and confirm the answer follows the schema. If the host is not reachable, document the fix (listen address, firewall) in the README

## 2. Safe migrations for two containers

- [ ] 2.1 Red: test that two connections calling `db.migrate` at the same time apply each file exactly once
- [ ] 2.2 Green: make `db.migrate` take its own advisory lock before it applies files
- [ ] 2.3 Refactor: move lock keys into named constants and keep the docstrings up to date

## 3. Bulk mail flag

- [ ] 3.1 Red: parsing tests for a mail with and without a `List-Unsubscribe` header (header names are case-insensitive)
- [ ] 3.2 Green: add `is_bulk` to `Mail` and set it in `parse_message`
- [ ] 3.3 Write migration `002_bulk_flag.sql` (nullable `messages.is_bulk`, existing rows stay `NULL`)
- [ ] 3.4 Red: database test that `insert_mails` stores `is_bulk` true, false, and unknown
- [ ] 3.5 Green: store `is_bulk` in `db.insert_mails`

## 4. Analysis rules (pure functions)

- [ ] 4.1 Red: tests for the allowed categories and importance levels, including rejection of unknown values and of wrong types
- [ ] 4.2 Green: implement the enums and answer validation in `analysis/rules.py`
- [ ] 4.3 Red: tests for the bulk guard (`urgent` to `important` for bulk and for unknown, unchanged for known non-bulk, other levels never changed)
- [ ] 4.4 Green: implement the bulk guard
- [ ] 4.5 Red: tests that `summary` and `reason` are cut to their maximum length and that control characters are removed
- [ ] 4.6 Green: implement text cleaning and truncation
- [ ] 4.7 Red: tests that the classify input uses sender, subject, and only the first part of a long body
- [ ] 4.8 Green: implement the input builders for classify and summarize
- [ ] 4.9 Refactor: remove duplication and check the module has no I/O

## 5. Prompts and schemas

- [ ] 5.1 Red: tests that the JSON schemas list exactly the allowed enums and that the mail text is placed inside a marked data block, never in the instruction part
- [ ] 5.2 Green: write `analysis/prompts.py` with the classify prompt, the summarize prompt (German, at most two sentences), the schemas, and `PROMPT_VERSION`. The classify prompt names the five urgent topics from the proposal

## 6. Model client

- [ ] 6.1 Red: tests for the client against a small local fake HTTP server: valid answer, answer that is not valid JSON, HTTP error status, connection refused, and timeout
- [ ] 6.2 Green: implement the `ModelClient` protocol, `OllamaClient`, and `ModelUnavailable` in `analysis/model.py` using only the standard library. Settings come from `OLLAMA_URL` and `ANALYZER_MODEL`
- [ ] 6.3 Red: config tests that `ANALYZER_MODEL` is required for the analyzer and that the default address is the host address
- [ ] 6.4 Green: extend `load_config` for the analyzer settings and fail early when a required value is missing

## 7. Analysis tables

- [ ] 7.1 Write migration `003_analyses.sql`: `analyses`, `analyzer_state`, the checks and the unique key from the design, a partial index on `importance`, and the drop of `messages.analysis_status` with its index
- [ ] 7.2 Red: database tests for the constraints: unknown mail rejected, duplicate for the same mail and prompt version rejected, a second prompt version allowed, `done` needs category and importance, `failed` has none
- [ ] 7.3 Green: make the tests pass with the migration (adjust the SQL where a test shows a gap)
- [ ] 7.4 Red: database tests for the repository functions: pick unanalyzed mails (newest first, limit, skip finished, include `pending` below the attempt limit, skip failed), record an attempt, save a result, mark failed, and set `last_ok_at`
- [ ] 7.5 Green: implement these functions in `db.py`
- [ ] 7.6 Red: test that migrating a database that already holds mails and the old column keeps all mails unchanged

## 8. Analyzer pass

- [ ] 8.1 Red: tests with a fake model for the happy path: `urgent` mail gets a summary, `normal` mail gets no summary and no second call
- [ ] 8.2 Green: implement the pass in `analysis/analyzer.py` (classify, optional summarize, save)
- [ ] 8.3 Red: tests for an invalid answer: attempt counted, mail marked `failed` after the last attempt, other mails still analyzed
- [ ] 8.4 Green: implement retry and permanent failure
- [ ] 8.5 Red: test that `ModelUnavailable` ends the pass with an error and changes no attempt count or status
- [ ] 8.6 Green: implement the unavailable path
- [ ] 8.7 Red: tests that a bulk `urgent` answer is stored as `important`, that a mail whose text tells the model to act causes nothing except a stored rating, and that a repeated pass creates no duplicates
- [ ] 8.8 Green: apply the rules in the pass and write each mail in its own transaction
- [ ] 8.9 Red: test that a second pass cannot run while the first holds the analyzer lock, and that the pass limit is respected
- [ ] 8.10 Green: add the analyzer advisory lock and the limit
- [ ] 8.11 Refactor: make sure the analyzer depends only on the `ModelClient` protocol and on `db`

## 9. Commands, scheduling, and containers

- [ ] 9.1 Red: CLI tests that `analyze` returns 0 on success and 1 on `ModelUnavailable`, and that `analyze` does not need Gmail settings
- [ ] 9.2 Green: add the `analyze` command to `cli.py`
- [ ] 9.3 Make `entrypoint.sh` read `RUN_COMMAND` and `CRONTAB` (defaults keep the poller behavior) and add `crontab.analyzer` with a 5-minute schedule
- [ ] 9.4 Add the `analyzer` service to `docker-compose.yml`: same image, no `secrets/` volume, `depends_on` Postgres healthy, `extra_hosts` for the host address, settings from the environment, non-root user
- [ ] 9.5 Add the new settings to `.env.example` and make sure the label file path is git-ignored and Docker-ignored

## 10. Health reporting

- [ ] 10.1 Red: tests for `analyzer-health`: healthy with no work, healthy with work and a recent `last_ok_at`, unhealthy with work and an old or missing `last_ok_at`
- [ ] 10.2 Green: implement the `analyzer-health` command and set `last_ok_at` after each successful pass (also when there was no work)
- [ ] 10.3 Add the healthcheck to the analyzer service in `docker-compose.yml`

## 11. Model evaluation and choice

- [ ] 11.1 Red: tests for the evaluation report using a fake model and a small label file: share of correct categories and importance levels, and the number of missed `urgent` mails
- [ ] 11.2 Green: implement `evaluate` (`analysis/evaluate.py` and the CLI command). It reads only IDs and labels from the file, reads the mail text from the database, and writes nothing to `analyses`
- [ ] 11.3 Label about 40 real mails by hand, covering all five urgent topics, newsletters, and ads. Keep the file out of git
- [ ] 11.4 Run `evaluate` for at least two candidate models and write the result and the choice into design.md. A model qualifies only if it misses no `urgent` mail
- [ ] 11.5 Set the chosen model as the default in `.env.example`

## 12. End-to-end check and wrap-up

- [ ] 12.1 Rebuild and start the stack. Confirm that the migrations ran and that the existing mails get results in `analyses`, that no `urgent` result exists for them (bulk unknown), and that `messages` is unchanged apart from the new flag
- [ ] 12.2 Stop Ollama and confirm that the pass fails with a log message, no mail turns `failed`, and the analyzer becomes `unhealthy` after the set time. Then start Ollama again and confirm it recovers
- [ ] 12.3 Send a test mail that is not bulk and contains an urgent topic. Confirm it is rated `urgent` with a German summary
- [ ] 12.4 Run the full test suite with `TEST_DATABASE_URL` set and show the result
- [ ] 12.5 Update the README: Ollama setup, the new settings, how to read results from `analyses`, how to run `evaluate`, and the rollback steps
