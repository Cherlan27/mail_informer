## Context

See proposal.md for the motivation. Current state:

- The analyzer writes one row per mail and prompt version to `analyses` (`status`, `category`, `importance`, `summary`, `updated_at`). `important` and `urgent` mails have a German summary. Bulk and unknown-bulk mails can never be `urgent`.
- Compose runs `postgres`, `poller`, and `analyzer`. The analyzer pattern is the model for this change: same image, `RUN_COMMAND` and `CRONTAB` set per service, a 5-minute schedule with supercronic, an advisory lock per service, a state row with `last_ok_at`, and a health command.
- Home Assistant runs on the home network. The short name `homeassistant` resolves on the host and in a container on the default Docker network, but **not** inside the Compose network. `homeassistant.fritz.box` and `homeassistant.local` resolve there. The address in `.env` therefore uses a full name (or a fixed IP). This was found while checking the stack, see tasks 9.1 and 9.2.
- Migrations are numbered SQL files. The last one is `003_analyses.sql`.

Constraints: the webhook address is a secret. Model text is data (see the `mail-analysis` spec). The container runs as a non-root user.

## Goals / Non-Goals

**Goals:**
- A reportable mail reaches the phone within about 5 minutes after it is analyzed.
- A mail is reported at most once, even after crashes, restarts, or a new prompt version.
- A broken notifier or a down Home Assistant never affects the poller or the analyzer.

**Non-Goals:**
- No guarantee of exactly-once delivery. See decision 4.
- No queue service, no push service of our own, no mobile app.
- No second channel such as mail or Telegram.

## Decisions

### 1. Separate container, same image
The notifier is a fourth Compose service. It starts `python -m mail_informer notify` through `RUN_COMMAND`, with its own crontab `crontab.notifier` (every 5 minutes). It needs only `DATABASE_URL` and `HA_WEBHOOK_URL`. It has no `secrets/` volume and no model server address.

- Why: the analyzer must not carry a network path to Home Assistant, and the notifier must not carry one to the model. Each container can fail or be restarted alone.
- Alternative: send from the analyzer right after saving a result. Rejected: it couples model speed and Home Assistant availability, and it puts the send action next to the model call.
- Alternative: a Postgres trigger or `LISTEN/NOTIFY`. Rejected: more moving parts for no gain at this volume.

### 2. Webhook, not the REST API
The notifier does `POST` with a JSON body to `HA_WEBHOOK_URL`, for example `http://homeassistant:8123/api/webhook/<id>`. The HTTP client is a small class on `urllib`, like `OllamaClient`, behind a `Notifier` protocol so tests use a fake.

- Why: the webhook id is the only secret and it opens only one automation. A REST token allows almost everything in Home Assistant.
- Home Assistant answers a webhook with 200 even for an unknown id, so a wrong address is not detected by the notifier. The README tells how to test the automation by hand.
- Alternative: `notify.mobile_app_<phone>` through the REST API. Rejected: needs a long-lived token.

### 3. Message format
Two kinds, both JSON with a `kind` field:

```
{"kind": "mail",   "category": "...", "importance": "urgent|important",
                   "sender": "...",   "summary": "..."}
{"kind": "digest", "count": 15}
```

- `sender` is the `From` header text, `summary` is the stored summary. Both lose control characters and are cut (sender 200, summary 500 characters). No ID, subject, or body.
- The automation in Home Assistant branches on `kind` and sets the title from `importance`. The README has an example.
- Why no subject: it is free text from the mail and could carry anything. The summary is already a short German text. This also keeps mail content out of the Home Assistant history.

### 4. Selection, ordering, and "once"
A reportable mail is the newest `done` analysis of a mail with importance `urgent` or `important`, where the first `done` analysis of the mail is at or after `notifier_state.start_at` and the newest one is not older than 6 hours, and where the mail has no row in `notifications`.

- Order: `urgent` first, then newest first. Under the limit the most important mails go out as single messages.
- `notifications(gmail_id PRIMARY KEY → messages, status, importance, created_at)` has one row per mail, not per prompt version. This is what makes a re-analysis harmless. `status` is `sent` (single message) or `suppressed` (covered by a collective message).
- Order of steps per mail: **send first, then record**, one transaction per mail. A crash between the two sends the message again in the next pass. This is a duplicate, not a loss. A lost "urgent" mail is worse than a repeated one, so at-least-once was chosen. The window is a few milliseconds.
- A dedicated advisory lock (own key) stops two passes from running together. This also removes most duplicates.
- Alternative: record first, then send. Rejected: a crash would lose the message for good.
- Alternative: a `status` column on `analyses`. Rejected: rows exist per prompt version, which would allow a second message, and the analyzer would own state it does not use.

### 5. Start point
`notifier_state(id=1, start_at, last_ok_at)`. On the first pass `start_at` is set to the current time (insert, do nothing if it exists). Mails analyzed before are never reported.

- Why: the archive already holds `important` mails. Without a start point the first pass would send all of them within the age limit.
- Alternative: mark all existing mails as `suppressed` in the migration. Rejected: the notifier would then depend on the migration time, and mails analyzed in between would be lost.

### 6. Limit and collective message
Per pass, `room = 10 - (rows with status 'sent' and created_at in the last hour)`. The first `room` mails go out as single messages. If more mails are ready, one `digest` message with the remaining count is sent, and then those mails are recorded as `suppressed` in one transaction.

- If the digest cannot be sent, nothing is recorded for those mails and the next pass tries again.
- Worst case during a long flood: 10 single messages plus at most one digest per pass (12 per hour). This is acceptable. It is still far less than the flood.
- Why a limit: a tricked model can rate a personal-looking spam mail as `important` or `urgent` (see the `llm-analysis` risks). The limit bounds what such a mail can do to the phone.
- Alternative: no limit. Rejected: a flood would fill the phone and hide real mails.
- Alternative: hold the extra mails for the next hour. Rejected: during a flood they would drop out at the age limit without notice.

### 7. Age limit and errors
- Mails with `updated_at` older than 6 hours are not selected. They also do not count as work for the healthcheck.
- A connection error, a timeout, or a non-2xx answer raises `NotifierUnavailable`. Nothing is recorded for that message, the pass ends with exit code 1, and the log has one line without the address and without mail text. The next pass starts the same selection again.
- There is no per-mail attempt count. The age limit is the end of retrying.

### 8. Healthcheck
`notifier-health` fails when reportable mails exist and `notifier_state.last_ok_at` is older than 30 minutes. `last_ok_at` is set after every pass that ends without error, also when there was no work. With no work it passes.

### 9. Module layout
- `notify/rules.py`: pure functions. Clean and cut text, build the message, compute `room`. No I/O.
- `notify/client.py`: `Notifier` protocol, `HaWebhookClient`, `NotifierUnavailable`.
- `notify/notifier.py`: one pass. Depends only on the protocol and on `db`.
- `db.py`: all SQL (select reportable mails, count sent in the last hour, record, state).
- `cli.py`: `notify` and `notifier-health`. `config.py`: `HA_WEBHOOK_URL`, required only for `notify`.

## Risks / Trade-offs

- [Crash after sending but before recording] → One duplicate message in the next pass. Accepted (decision 4).
- [Wrong webhook address] → Home Assistant answers 200, so the notifier sees no error. The README describes a manual test with `curl`.
- [The webhook address leaks] → Anyone on the network could send fake messages to the automation. They can do nothing else. Keep it in `.env` (git-ignored), never log it, and change the id in Home Assistant if it leaks.
- [Tricked model rates spam as important] → The limit bounds the damage. The bulk guard already blocks newsletters. The summary is shown as plain text only.
- [Summary text shown on the phone is wrong or misleading] → It is a model summary. The category and the sender are shown next to it. Acceptable for a first version.
- [Home Assistant is down for more than 6 hours] → Mails from that time are not reported. They stay in `analyses` and can be read there.
- [The notifier starts before any analyzer pass] → No reportable mails, healthy, nothing sent.
- [Two passes at once] → The advisory lock prevents it. `notifications.gmail_id` is a primary key, so a second record would fail instead of duplicating.
- [Collective message hides which mails arrived] → The mails are in `analyses` and the archive. The count tells that something happened.

## Migration Plan

1. Add `004_notifications.sql` with `notifications` and `notifier_state`. It only adds tables and changes no existing data.
2. Set `HA_WEBHOOK_URL` in `.env` and create the webhook automation in Home Assistant (README example).
3. `docker compose up -d`. The first notifier pass sets `start_at`. Only mails analyzed after that are reported.
4. Check by hand: send a test message with `curl` to the webhook, and send a real test mail that is not bulk and about an urgent topic.

Rollback: `docker compose stop notifier`. The poller and the analyzer do not depend on it. To undo the migration by hand: drop `notifications` and `notifier_state`.

## Open Questions

- The exact wording and sound of the phone notification. It is set in the Home Assistant automation and does not change the code.
- Whether 10 per hour and 6 hours are the right limits. They are constants and can be tuned after real use.
