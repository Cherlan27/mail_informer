CREATE TABLE messages (
    gmail_id        text PRIMARY KEY,
    thread_id       text NOT NULL,
    internal_date   timestamptz NOT NULL,
    from_addr       text,
    to_addrs        text,
    subject         text,
    labels          text[] NOT NULL DEFAULT '{}',
    snippet         text,
    body_text       text NOT NULL DEFAULT '',
    fetched_at      timestamptz NOT NULL DEFAULT now(),
    analysis_status text NOT NULL DEFAULT 'pending'
);

CREATE INDEX messages_internal_date_idx ON messages (internal_date);
CREATE INDEX messages_analysis_status_idx ON messages (analysis_status);

CREATE TABLE sync_state (
    id         integer PRIMARY KEY CHECK (id = 1),
    history_id text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);
