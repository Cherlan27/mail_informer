-- One row per reported mail, kept apart from the analysis results. A new prompt
-- version adds analysis rows but never a second notification.
CREATE TABLE notifications (
    gmail_id   text PRIMARY KEY REFERENCES messages (gmail_id),
    -- sent: reported with its own message. suppressed: only counted in a collective message.
    status     text NOT NULL CHECK (status IN ('sent', 'suppressed')),
    importance text NOT NULL CHECK (importance IN ('important', 'urgent')),
    created_at timestamptz NOT NULL DEFAULT now()
);

-- For the hourly limit: count the single messages of the last hour.
CREATE INDEX notifications_sent_idx ON notifications (created_at) WHERE status = 'sent';

-- Single row. start_at is set by the first pass: older analyses are never reported.
-- The healthcheck reads the time of the last successful pass.
CREATE TABLE notifier_state (
    id         integer PRIMARY KEY CHECK (id = 1),
    start_at   timestamptz NOT NULL,
    last_ok_at timestamptz
);
