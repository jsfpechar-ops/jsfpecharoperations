-- Brief 1471, read-only: the 6 foreign keys and 19 text columns goose 00017 covers.
-- Expected on production, before and after 00017: 6|19
SELECT
    (SELECT count(*) FROM pg_constraint
     WHERE contype = 'f' AND condeferrable AND NOT condeferred
       AND connamespace = 'public'::regnamespace
       AND conname IN ('site_booking_apartment_id_fkey', 'site_booking_invoice_id_fkey',
                       'site_booking_owner_user_id_fkey', 'site_booking_reservation_id_fkey',
                       'stay_fee_rate_apartment_id_fkey', 'guest_form_draft_reservation_id_fkey')) AS deferrable_fks,
    (SELECT count(*) FROM information_schema.columns
     WHERE table_schema = 'public' AND collation_name = 'C'
       AND table_name || '.' || column_name IN (
           'apartment.stay_fee_guest_rails', 'apartment.stay_fee_guest_revolut_link',
           'apartment.stay_fee_guest_cash_note', 'apartment.stay_fee_guest_default_rail',
           'guest.signed_for_role', 'guest.signed_for_at', 'guest.signed_for_wording',
           'guest_form_draft.device_key_hash', 'guest_form_draft.fields_enc',
           'guest_form_draft.created_at', 'guest_form_draft.updated_at',
           'property_page.house_rules', 'reservation.lead_reduced_at',
           'reservation_claim.fee_mailed_at', 'reservation_claim.fee_pending_since',
           'site_booking.pay_method', 'site_booking.request_expires_at',
           'stay_fee_rate.effective_from', 'stay_fee_rate.created_at')) AS c_collated_columns;
