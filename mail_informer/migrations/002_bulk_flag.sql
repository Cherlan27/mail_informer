-- true: the mail has a List-Unsubscribe header (newsletter, ad, alert).
-- NULL: unknown. Mails stored before this column existed stay NULL,
-- because their headers were not kept. The analyzer treats NULL as bulk.
ALTER TABLE messages ADD COLUMN is_bulk boolean;
