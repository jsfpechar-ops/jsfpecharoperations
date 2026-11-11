-- Brief 1120: the host's switch for full guest details in the confirmation e-mail (1 = on, the default).
-- A boolean preference of the account, not personal data; it goes with the user_account row.
ALTER TABLE user_account ADD COLUMN guest_details_mail INTEGER NOT NULL DEFAULT 1;
