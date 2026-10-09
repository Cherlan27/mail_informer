## 1. Check Home Assistant

- [x] 1.1 Create a webhook automation in Home Assistant that writes the received JSON to a persistent notification, and put its address in `.env` as `HA_WEBHOOK_URL`
- [x] 1.2 From a throwaway container, `POST` a test message to the webhook and confirm that Home Assistant shows it. Try a wrong id and note what Home Assistant answers

## 2. Pure rules (`notify/rules.py`)

- [x] 2.1 Red: tests that sender and summary lose control characters and are cut to their maximum (200 and 500 characters)
- [x] 2.2 Green: implement text cleaning and cutting (reuse the analysis helper if it fits)
- [x] 2.3 Red: tests that a mail message has exactly the keys `kind`, `category`, `importance`, `sender`, `summary`, and that a digest message has exactly `kind` and `count`
- [x] 2.4 Green: implement the message builders
- [x] 2.5 Red: tests for the free places: 10 minus sent in the last hour, never below 0, and the split of a list of mails into single messages and the remaining count
- [x] 2.6 Green: implement the limit rules and the order (`urgent` first, then newest first)
- [x] 2.7 Refactor: check the module has no I/O and no import of `db`

## 3. Configuration

- [x] 3.1 Red: config tests that `HA_WEBHOOK_URL` is required for `notify`, must start with `http://` or `https://`, and is not needed for the other commands
- [x] 3.2 Green: extend `load_config` and fail early with a message that names the setting but not its value
- [x] 3.3 Add `HA_WEBHOOK_URL` to `.env.example` with a comment that it is a secret

## 4. Database

- [x] 4.1 Write migration `004_notifications.sql`: `notifications` (primary key `gmail_id` referencing `messages`, `status` check `sent` or `suppressed`, `importance`, `created_at`) and `notifier_state` (single row, `start_at`, `last_ok_at`)
- [x] 4.2 Red: database tests for the constraints: unknown mail rejected, a second row for the same mail rejected, unknown status rejected
- [x] 4.3 Green: make the tests pass with the migration
- [x] 4.4 Red: tests for "reportable mails": only `done` with `urgent` or `important`, only mails first analyzed at or after `start_at` (also not after a re-analysis of an older mail), newest analysis not older than 6 hours, not already in `notifications`, and the newest analysis is used when there are two prompt versions
- [x] 4.5 Green: implement the selection in `db.py`
- [x] 4.6 Red: tests for the other functions: set the start point once (a second call keeps the first value), count `sent` rows of the last hour, record `sent`, record a list as `suppressed` in one transaction, set `last_ok_at`, and an advisory lock with its own key
- [x] 4.7 Green: implement these functions in `db.py`
- [x] 4.8 Red: test that migrating a database with mails and results keeps all existing rows unchanged
- [x] 4.9 Green: fix the migration if the test shows a gap

## 5. Client (`notify/client.py`)

- [x] 5.1 Red: tests against a small local fake HTTP server: valid post, error status, connection refused, and timeout. Also a test that the error text does not contain the address
- [x] 5.2 Green: implement the `Notifier` protocol, `HaWebhookClient` on `urllib`, and `NotifierUnavailable`

## 6. Pass (`notify/notifier.py`)

- [x] 6.1 Red: tests with a fake notifier for the happy path: an `urgent` and an `important` mail are sent as single messages, a `normal` mail is not sent, and each sent mail is recorded
- [x] 6.2 Green: implement the pass (select, send, record, one transaction per mail)
- [x] 6.3 Red: tests that a second pass sends nothing again, and that a re-analysis with a new prompt version sends nothing again
- [x] 6.4 Green: make them pass without new code, or fix the selection
- [x] 6.5 Red: tests for the start point: on the first pass `start_at` is set, and a mail analyzed before it is not sent
- [x] 6.6 Green: set the start point at the beginning of a pass
- [x] 6.7 Red: tests for the limit: 25 ready mails give 10 single messages and one digest with 15, and the 15 are recorded as `suppressed`; with 10 already sent in the last hour one ready mail gives only a digest with 1; a failed digest records nothing
- [x] 6.8 Green: implement the limit and the digest
- [x] 6.9 Red: tests that a mail older than 6 hours is not sent
- [x] 6.10 Green: apply the age limit in the selection
- [x] 6.11 Red: tests that `NotifierUnavailable` ends the pass with an error, records nothing for that message, and that the same mail is sent in the next pass
- [x] 6.12 Green: implement the unavailable path
- [x] 6.13 Red: tests that a summary with instructions in it is sent as plain text and causes nothing else, and that the log has no address and no mail text
- [x] 6.14 Green: make them pass, and check the log calls
- [x] 6.15 Red: tests that a second pass cannot run while the first holds the notifier lock
- [x] 6.16 Green: add the notifier lock
- [x] 6.17 Refactor: make sure the pass depends only on the `Notifier` protocol and on `db`

## 7. Commands and health

- [x] 7.1 Red: CLI tests that `notify` returns 0 on success and 1 on `NotifierUnavailable`, and that it does not need Gmail or model settings
- [x] 7.2 Green: add the `notify` command to `cli.py`
- [x] 7.3 Red: tests for `notifier-health`: healthy with no work, healthy with work and a recent `last_ok_at`, unhealthy with work and an old or missing `last_ok_at`, and healthy when the only waiting mails are older than 6 hours
- [x] 7.4 Green: implement `notifier-health` and set `last_ok_at` after every pass without error (also when there was no work)

## 8. Compose

- [x] 8.1 Add `crontab.notifier` (every 5 minutes) and the `notifier` service to `docker-compose.yml`: same image, `RUN_COMMAND: notify`, no `secrets/` volume, `depends_on` Postgres healthy, `HA_WEBHOOK_URL` required from `.env`, non-root user, healthcheck with `notifier-health`
- [x] 8.2 Make sure `.env` is git-ignored and Docker-ignored, and that the address is not printed by `docker compose config` in any file in the repo

## 9a. Poll every 5 minutes

- [x] 9a.1 Red: CLI tests for the poller healthcheck: unhealthy before the first sync, healthy 10 minutes after the last sync, unhealthy 20 minutes after it
- [x] 9a.2 Green: set `MAX_SYNC_AGE` to 15 minutes and the poller schedule in `crontab` to every 5 minutes
- [x] 9a.3 Update the 30-minute and 90-minute texts in the README, in the Purpose of the `poller-runtime` spec, and in `openspec/config.yaml`

## 9. Check in the real stack

- [x] 9.1 Rebuild and start the stack. Confirm that migration 004 ran, that the existing mails are unchanged, and that no message is sent for the existing archive
- [x] 9.2 Make Home Assistant unreachable (rename the webhook, or block it) and confirm that a pass fails with a log line and no mail is recorded. Confirm that the notifier turns `unhealthy` after the set time (set `last_ok_at` back instead of waiting) and recovers
- [ ] 9.3 Send a test mail that is not bulk and has an urgent topic. Confirm that exactly one message arrives on the phone with category, importance, sender, and summary
- [x] 9.4 Confirm the limit with test rows in a throwaway database: 12 ready mails give 10 single messages and one digest
- [x] 9.5 Run the full test suite with `TEST_DATABASE_URL` set and show the result
- [x] 9.6 Update the README: the new service, `HA_WEBHOOK_URL`, the example Home Assistant automation (for `kind` mail and digest), a `curl` test of the webhook, how to see what was reported (`notifications`), and the rollback steps
