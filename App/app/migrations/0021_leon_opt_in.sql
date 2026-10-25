-- Brief 0376: Leon (AI) answers a property's guests only after its host switches it on.
ALTER TABLE apartment ADD COLUMN leon_enabled INTEGER NOT NULL DEFAULT 0;
