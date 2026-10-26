-- Brief 0413: the PDF of each UbyHost invoice, stored once at issue and never re-rendered.
ALTER TABLE platform_invoice ADD COLUMN pdf_blob BLOB;
ALTER TABLE platform_invoice ADD COLUMN pdf_sha256 TEXT;
