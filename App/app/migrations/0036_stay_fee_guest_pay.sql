-- Brief 0897: host configuration for stay-fee guest payment (phase 0).
--
-- Host configuration only. No guest or payment data is stored here.
-- stay_fee_guest_rails is a csv subset of 'qr','iban','revolut','cash'.
-- stay_fee_guest_revolut_link is a validated https link on revolut.me or
-- revolut.com (or a subdomain of either).
ALTER TABLE apartment ADD COLUMN stay_fee_collect INTEGER NOT NULL DEFAULT 0;
ALTER TABLE apartment ADD COLUMN stay_fee_guest_rails TEXT NOT NULL DEFAULT '';
ALTER TABLE apartment ADD COLUMN stay_fee_guest_revolut_link TEXT;
ALTER TABLE apartment ADD COLUMN stay_fee_guest_cash_note TEXT;
