-- Mails and sync points belong to an account. Existing data belongs to "gmail".
-- The default is dropped again so that new code must name the account.
ALTER TABLE messages ADD COLUMN account text NOT NULL DEFAULT 'gmail';
ALTER TABLE messages ALTER COLUMN account DROP DEFAULT;
CREATE INDEX messages_account_date_idx ON messages (account, internal_date);

-- gmail_id is the unique mail key of every account. For Gmail it is the Gmail ID.
-- For IMAP it is "<account>:<Message-ID>". The name is kept to avoid a large rename.
COMMENT ON COLUMN messages.gmail_id IS 'Unique mail key across all accounts';

-- One sync point per account. A NULL cursor means: not started yet.
ALTER TABLE sync_state ADD COLUMN account text;
UPDATE sync_state SET account = 'gmail';
ALTER TABLE sync_state ALTER COLUMN account SET NOT NULL;
ALTER TABLE sync_state RENAME COLUMN history_id TO cursor;
ALTER TABLE sync_state ALTER COLUMN cursor DROP NOT NULL;
-- Dropping id also drops its primary key and its check (id = 1).
ALTER TABLE sync_state DROP COLUMN id;
ALTER TABLE sync_state ADD PRIMARY KEY (account);
