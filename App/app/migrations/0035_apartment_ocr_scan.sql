-- Brief 0834: per-property host switch for the passport scan (default off).
--
-- apartment.ocr_scan is 1 only when the host turned the scan on. It has effect
-- only while passport_photo_policy is 'required_foreign' (see doc_ocr.available).
ALTER TABLE apartment ADD COLUMN ocr_scan INTEGER NOT NULL DEFAULT 0;
