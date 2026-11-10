-- Brief 1089: which adult guest signed for a guest under 15, in which role, when and under which wording.
-- Personal data about the adult and the child, kept with the guest row and deleted with it.
ALTER TABLE guest ADD COLUMN signed_for_guest_id INTEGER;
ALTER TABLE guest ADD COLUMN signed_for_role TEXT;
ALTER TABLE guest ADD COLUMN signed_for_at TEXT;
ALTER TABLE guest ADD COLUMN signed_for_wording TEXT;
