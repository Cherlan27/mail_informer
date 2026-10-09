## Why

The analyzer now rates every mail, but the result sits in the database and nobody sees it. The few mails that matter (`urgent` and `important`) should reach the phone soon after they arrive, through Home Assistant, which is already on the home network.

## What Changes

- New `notifier` container (same image, like the analyzer). Every 5 minutes it finds analyzed mails rated `urgent` or `important` that were not reported yet, and sends each one as its own message to a Home Assistant webhook.
- The message holds only: the category, the importance, the sender, and the German summary. It holds no mail ID, no subject, and no body.
- Each mail is reported at most once. A new table `notifications` records it, apart from `analyses`, so a new prompt version does not report the same mail again.
- Only the rating decides. The notifier reads the importance enum and sends the summary as plain text for display. The summary never decides anything (see `mail-analysis`: model output triggers no action).
- Start point: only mails analyzed after the notifier first ran are reported. The existing archive is not sent.
- Limit: at most 10 single messages per hour. Mails over the limit are not sent one by one. One collective message tells how many more arrived.
- Old mails are dropped: a mail analyzed more than 6 hours ago is no longer reported. This ends endless retries when Home Assistant is down for a long time.
- If Home Assistant cannot be reached, nothing is recorded and the next pass tries again.
- The webhook address is a secret. It comes from `HA_WEBHOOK_URL` in `.env` and is never logged or committed.
- New command `notify` and a healthcheck `notifier-health` (unhealthy when reportable mails wait and the last successful pass is older than 30 minutes).
- The poller runs every 5 minutes instead of every 30, so a new mail reaches the phone within about 10 minutes. Its healthcheck limit goes from 90 to 15 minutes (three missed runs).
- The README gets an example Home Assistant automation that turns the message into a phone notification.

## Non-goals

- No bundling of `important` mails into a digest. Only the over-limit case uses one collective message.
- No reply, archive, or other action on a mail from the phone.
- No link to the mail or to Gmail in the message.
- No Home Assistant token and no use of the Home Assistant REST API.
- No changes to the poller, the analyzer, or Gmail access.
- No setup of Home Assistant itself. Only an example automation is documented.

## Capabilities

### New Capabilities
- `mail-notification`: Which analyzed mails are reported, what the message contains, the once-only rule, the start point, the hourly limit, the age limit, error behavior, and the safety rule for model text.

### Modified Capabilities
- `poller-runtime`: The Compose stack also starts the notifier, which needs the Home Assistant webhook address. The notifier has its own health reporting.

## Impact

- New migration `004_notifications.sql`: tables `notifications` and `notifier_state`.
- New module `mail_informer/notify/` (selection and message rules without I/O, plus a small HTTP client built on the standard library), new `notify` and `notifier-health` commands in `cli.py`, new functions in `db.py`.
- New service `notifier` in `docker-compose.yml`, new `crontab.notifier`. No `secrets/` volume and no model server access.
- New setting `HA_WEBHOOK_URL` in `.env.example` and `config.py` (required for the notifier only).
- No new dependency.
- Home Assistant needs one webhook automation (example in the README).
