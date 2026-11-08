-- Brief 0999: the host's house rules for the public page, prefilled once from the Airbnb import.
-- Host content, no personal data; a re-import fills it only while empty.
ALTER TABLE property_page ADD COLUMN house_rules TEXT;
