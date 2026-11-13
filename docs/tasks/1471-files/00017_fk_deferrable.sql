-- +goose Up
-- Brief 1471 (plan sqlite-retirement S2). Goose-only, no SQLite twin, no schema_migrations row.
-- Production was built by Python's translation of the SQLite migrations, which makes every
-- foreign key DEFERRABLE INITIALLY IMMEDIATE and every TEXT column COLLATE "C". Goose 00004,
-- 00011 and 00013 left DEFERRABLE out of 6 foreign keys, and goose 00006-00015 left COLLATE "C"
-- out of 19 text columns, so a database built from goose files alone differed from production.
-- On production this file changes nothing: ALTER CONSTRAINT with the attributes a constraint
-- already has writes no catalog row, and the DO block alters only a listed column whose
-- collation is not "C".
ALTER TABLE site_booking ALTER CONSTRAINT site_booking_apartment_id_fkey DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE site_booking ALTER CONSTRAINT site_booking_invoice_id_fkey DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE site_booking ALTER CONSTRAINT site_booking_owner_user_id_fkey DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE site_booking ALTER CONSTRAINT site_booking_reservation_id_fkey DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE stay_fee_rate ALTER CONSTRAINT stay_fee_rate_apartment_id_fkey DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE guest_form_draft ALTER CONSTRAINT guest_form_draft_reservation_id_fkey DEFERRABLE INITIALLY IMMEDIATE;
-- +goose StatementBegin
DO $$
DECLARE
    col record;
BEGIN
    FOR col IN
        SELECT c.table_name, c.column_name
        FROM information_schema.columns c
        JOIN (VALUES
            ('apartment', 'stay_fee_guest_rails'),
            ('apartment', 'stay_fee_guest_revolut_link'),
            ('apartment', 'stay_fee_guest_cash_note'),
            ('apartment', 'stay_fee_guest_default_rail'),
            ('guest', 'signed_for_role'),
            ('guest', 'signed_for_at'),
            ('guest', 'signed_for_wording'),
            ('guest_form_draft', 'device_key_hash'),
            ('guest_form_draft', 'fields_enc'),
            ('guest_form_draft', 'created_at'),
            ('guest_form_draft', 'updated_at'),
            ('property_page', 'house_rules'),
            ('reservation', 'lead_reduced_at'),
            ('reservation_claim', 'fee_mailed_at'),
            ('reservation_claim', 'fee_pending_since'),
            ('site_booking', 'pay_method'),
            ('site_booking', 'request_expires_at'),
            ('stay_fee_rate', 'effective_from'),
            ('stay_fee_rate', 'created_at')
        ) AS want (table_name, column_name)
            ON c.table_name = want.table_name AND c.column_name = want.column_name
        WHERE c.table_schema = current_schema()
          AND c.data_type = 'text'
          AND c.collation_name IS DISTINCT FROM 'C'
        ORDER BY c.table_name, c.column_name
    LOOP
        EXECUTE format('ALTER TABLE %I ALTER COLUMN %I TYPE text COLLATE "C"', col.table_name, col.column_name);
    END LOOP;
END $$;
-- +goose StatementEnd

-- +goose Down
-- Restores the goose-only form. Never run this on production: production had the Up form
-- before this file existed.
ALTER TABLE stay_fee_rate ALTER COLUMN created_at TYPE text COLLATE "default";
ALTER TABLE stay_fee_rate ALTER COLUMN effective_from TYPE text COLLATE "default";
ALTER TABLE site_booking ALTER COLUMN request_expires_at TYPE text COLLATE "default";
ALTER TABLE site_booking ALTER COLUMN pay_method TYPE text COLLATE "default";
ALTER TABLE reservation_claim ALTER COLUMN fee_pending_since TYPE text COLLATE "default";
ALTER TABLE reservation_claim ALTER COLUMN fee_mailed_at TYPE text COLLATE "default";
ALTER TABLE reservation ALTER COLUMN lead_reduced_at TYPE text COLLATE "default";
ALTER TABLE property_page ALTER COLUMN house_rules TYPE text COLLATE "default";
ALTER TABLE guest_form_draft ALTER COLUMN updated_at TYPE text COLLATE "default";
ALTER TABLE guest_form_draft ALTER COLUMN created_at TYPE text COLLATE "default";
ALTER TABLE guest_form_draft ALTER COLUMN fields_enc TYPE text COLLATE "default";
ALTER TABLE guest_form_draft ALTER COLUMN device_key_hash TYPE text COLLATE "default";
ALTER TABLE guest ALTER COLUMN signed_for_wording TYPE text COLLATE "default";
ALTER TABLE guest ALTER COLUMN signed_for_at TYPE text COLLATE "default";
ALTER TABLE guest ALTER COLUMN signed_for_role TYPE text COLLATE "default";
ALTER TABLE apartment ALTER COLUMN stay_fee_guest_default_rail TYPE text COLLATE "default";
ALTER TABLE apartment ALTER COLUMN stay_fee_guest_cash_note TYPE text COLLATE "default";
ALTER TABLE apartment ALTER COLUMN stay_fee_guest_revolut_link TYPE text COLLATE "default";
ALTER TABLE apartment ALTER COLUMN stay_fee_guest_rails TYPE text COLLATE "default";
ALTER TABLE guest_form_draft ALTER CONSTRAINT guest_form_draft_reservation_id_fkey NOT DEFERRABLE;
ALTER TABLE stay_fee_rate ALTER CONSTRAINT stay_fee_rate_apartment_id_fkey NOT DEFERRABLE;
ALTER TABLE site_booking ALTER CONSTRAINT site_booking_reservation_id_fkey NOT DEFERRABLE;
ALTER TABLE site_booking ALTER CONSTRAINT site_booking_owner_user_id_fkey NOT DEFERRABLE;
ALTER TABLE site_booking ALTER CONSTRAINT site_booking_invoice_id_fkey NOT DEFERRABLE;
ALTER TABLE site_booking ALTER CONSTRAINT site_booking_apartment_id_fkey NOT DEFERRABLE;
