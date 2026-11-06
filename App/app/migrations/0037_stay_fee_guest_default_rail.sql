-- Host configuration only: which guest payment method opens first on the stay summary.
-- One of 'qr','iban','revolut','cash', or empty for the standard order.
ALTER TABLE apartment ADD COLUMN stay_fee_guest_default_rail TEXT NOT NULL DEFAULT '';
