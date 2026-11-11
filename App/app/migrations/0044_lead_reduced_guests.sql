-- Brief 1095: the lead guest's lower head count, kept apart from the host's number.
-- Numbers and one timestamp, no personal data; deleted with the reservation row.
ALTER TABLE reservation ADD COLUMN lead_reduced_guests INTEGER;
ALTER TABLE reservation ADD COLUMN lead_reduced_from INTEGER;
ALTER TABLE reservation ADD COLUMN lead_reduced_at TEXT;
ALTER TABLE reservation ADD COLUMN lead_reduced_changes INTEGER NOT NULL DEFAULT 0;
