ALTER TABLE apartment ADD COLUMN stay_fee_authority_databox TEXT;
ALTER TABLE stay_fee_filing ADD COLUMN sent_at TEXT;
ALTER TABLE stay_fee_filing ADD COLUMN sent_message_id TEXT;
ALTER TABLE stay_fee_filing ADD COLUMN paid_at TEXT;
