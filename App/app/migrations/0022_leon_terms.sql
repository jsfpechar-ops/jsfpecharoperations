-- Brief 0394: which Leon (AI) terms the host accepted for this property, when and who.
ALTER TABLE apartment ADD COLUMN leon_terms_version TEXT;
ALTER TABLE apartment ADD COLUMN leon_terms_accepted_at TEXT;
ALTER TABLE apartment ADD COLUMN leon_terms_accepted_by INTEGER;
