-- Analysis results are kept apart from the archived mail.
-- One row per mail and prompt version, so a new prompt can add a second result.
CREATE TABLE analyses (
    id             bigserial PRIMARY KEY,
    gmail_id       text NOT NULL REFERENCES messages (gmail_id),
    prompt_version text NOT NULL,
    status         text NOT NULL CHECK (status IN ('pending', 'done', 'failed')),
    category       text,
    importance     text CHECK (importance IN ('ignore', 'normal', 'important', 'urgent')),
    summary        text NOT NULL DEFAULT '',
    reason         text NOT NULL DEFAULT '',
    model          text NOT NULL,
    attempts       integer NOT NULL DEFAULT 0,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (gmail_id, prompt_version),
    -- Only finished results carry a rating.
    CHECK (status <> 'done' OR (category IS NOT NULL AND importance IS NOT NULL)),
    CHECK (status = 'done' OR (category IS NULL AND importance IS NULL))
);

-- For the later notifier: finished results by importance.
CREATE INDEX analyses_done_importance_idx ON analyses (importance) WHERE status = 'done';

-- Single row. The healthcheck reads the time of the last successful pass.
CREATE TABLE analyzer_state (
    id         integer PRIMARY KEY CHECK (id = 1),
    last_ok_at timestamptz NOT NULL
);

-- The poller never changed this column, so every row still holds the default.
-- The state of an analysis now lives in analyses.
DROP INDEX IF EXISTS messages_analysis_status_idx;
ALTER TABLE messages DROP COLUMN analysis_status;
