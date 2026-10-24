-- Brief 0294: the public QR door of the guest guide (plan: docs/plans/guest-guide.md).
--
-- apartment.guide_token: the unguessable key in the QR code at the property
-- (/g/{token}). Separate from permalink_token, which opens the stay link and
-- the registration form: the QR token only ever shows "everyone" cards and
-- the host can rotate it (brief 0295) without breaking the stay links.
-- NULL until the host first opens the guide page.
ALTER TABLE apartment ADD COLUMN guide_token TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS uq_apartment_guide_token ON apartment (guide_token) WHERE guide_token IS NOT NULL;
