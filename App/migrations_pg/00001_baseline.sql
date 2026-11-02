-- +goose Up
-- Schema version 33 as rendered by db.apply_postgresql_schema on 2026-10-31; generated, never edited.
--
-- PostgreSQL database dump
--


-- Dumped from database version 16.15 (Ubuntu 16.15-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.15 (Ubuntu 16.15-0ubuntu0.24.04.1)


--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

-- *not* creating schema, since initdb creates it


--
-- Name: ubyhost_invoice_delete_guard(); Type: FUNCTION; Schema: public; Owner: -
--

-- +goose StatementBegin
CREATE FUNCTION public.ubyhost_invoice_delete_guard() RETURNS trigger
    LANGUAGE plpgsql
    AS $$ BEGIN
  IF OLD.issued_at IS NOT NULL AND COALESCE((SELECT value FROM settings WHERE key = 'invoice_purge_unlock'), '') <> '1' THEN
    RAISE EXCEPTION USING ERRCODE = 'integrity_constraint_violation', MESSAGE = 'invoice is issued and immutable';
  END IF;
  RETURN OLD;
END $$;
-- +goose StatementEnd


--
-- Name: ubyhost_invoice_issued_guard(); Type: FUNCTION; Schema: public; Owner: -
--

-- +goose StatementBegin
CREATE FUNCTION public.ubyhost_invoice_issued_guard() RETURNS trigger
    LANGUAGE plpgsql
    AS $$ BEGIN
  IF OLD.issued_at IS NOT NULL THEN
    RAISE EXCEPTION USING ERRCODE = 'integrity_constraint_violation', MESSAGE = 'invoice is issued and immutable';
  END IF;
  RETURN NEW;
END $$;
-- +goose StatementEnd


--
-- Name: ubyhost_invoice_item_delete_guard(); Type: FUNCTION; Schema: public; Owner: -
--

-- +goose StatementBegin
CREATE FUNCTION public.ubyhost_invoice_item_delete_guard() RETURNS trigger
    LANGUAGE plpgsql
    AS $$ BEGIN
  IF (SELECT issued_at FROM invoice WHERE id = OLD.invoice_id) IS NOT NULL
     AND COALESCE((SELECT value FROM settings WHERE key = 'invoice_purge_unlock'), '') <> '1' THEN
    RAISE EXCEPTION USING ERRCODE = 'integrity_constraint_violation', MESSAGE = 'invoice is issued and immutable';
  END IF;
  RETURN OLD;
END $$;
-- +goose StatementEnd


--
-- Name: ubyhost_invoice_item_insert_guard(); Type: FUNCTION; Schema: public; Owner: -
--

-- +goose StatementBegin
CREATE FUNCTION public.ubyhost_invoice_item_insert_guard() RETURNS trigger
    LANGUAGE plpgsql
    AS $$ BEGIN
  IF (SELECT issued_at FROM invoice WHERE id = NEW.invoice_id) IS NOT NULL THEN
    RAISE EXCEPTION USING ERRCODE = 'integrity_constraint_violation', MESSAGE = 'invoice is issued and immutable';
  END IF;
  RETURN NEW;
END $$;
-- +goose StatementEnd


--
-- Name: ubyhost_invoice_item_update_guard(); Type: FUNCTION; Schema: public; Owner: -
--

-- +goose StatementBegin
CREATE FUNCTION public.ubyhost_invoice_item_update_guard() RETURNS trigger
    LANGUAGE plpgsql
    AS $$ BEGIN
  IF (SELECT issued_at FROM invoice WHERE id = OLD.invoice_id) IS NOT NULL THEN
    RAISE EXCEPTION USING ERRCODE = 'integrity_constraint_violation', MESSAGE = 'invoice is issued and immutable';
  END IF;
  RETURN NEW;
END $$;
-- +goose StatementEnd


--
-- Name: ubyhost_invoice_note_guard(); Type: FUNCTION; Schema: public; Owner: -
--

-- +goose StatementBegin
CREATE FUNCTION public.ubyhost_invoice_note_guard() RETURNS trigger
    LANGUAGE plpgsql
    AS $$ BEGIN
  IF OLD.issued_at IS NOT NULL THEN
    RAISE EXCEPTION USING ERRCODE = 'integrity_constraint_violation', MESSAGE = 'invoice is issued and immutable';
  END IF;
  RETURN NEW;
END $$;
-- +goose StatementEnd


--
-- Name: ubyhost_sqlite_date(text); Type: FUNCTION; Schema: public; Owner: -
--

-- +goose StatementBegin
CREATE FUNCTION public.ubyhost_sqlite_date(value text) RETURNS text
    LANGUAGE plpgsql STABLE STRICT
    AS $_$
DECLARE parsed timestamptz;
        parsed_local timestamp without time zone;
BEGIN
  IF value !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}([ T][0-9]{2}:[0-9]{2}(:[0-9]{2}(\.[0-9]{1,6})?)?(Z|[+-][0-9]{2}:[0-9]{2})?)?$' THEN
    RETURN NULL;
  END IF;
  IF value ~ '(Z|[+-][0-9]{2}:[0-9]{2})$' THEN
    parsed := value::timestamptz;
    RETURN to_char(parsed AT TIME ZONE 'UTC', 'YYYY-MM-DD');
  END IF;
  parsed_local := value::timestamp without time zone;
  RETURN to_char(parsed_local, 'YYYY-MM-DD');
EXCEPTION WHEN OTHERS THEN
  RETURN NULL;
END $_$;
-- +goose StatementEnd




--
-- Name: ad_click; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ad_click (
    id bigint NOT NULL,
    user_account_id bigint NOT NULL,
    platform text NOT NULL COLLATE pg_catalog."C",
    gclid text COLLATE pg_catalog."C",
    gbraid text COLLATE pg_catalog."C",
    wbraid text COLLATE pg_catalog."C",
    clicked_at text NOT NULL COLLATE pg_catalog."C",
    consent_text_id bigint NOT NULL,
    consented_at text NOT NULL COLLATE pg_catalog."C",
    withdrawn_at text COLLATE pg_catalog."C",
    uploaded_at text COLLATE pg_catalog."C",
    ids_deleted_at text COLLATE pg_catalog."C",
    created_at text NOT NULL COLLATE pg_catalog."C",
    fbc text COLLATE pg_catalog."C",
    event_id text COLLATE pg_catalog."C",
    send_state text COLLATE pg_catalog."C",
    attempts bigint DEFAULT 0 NOT NULL,
    next_attempt_at text COLLATE pg_catalog."C",
    last_error text COLLATE pg_catalog."C",
    client_user_agent text COLLATE pg_catalog."C"
);


--
-- Name: ad_click_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.ad_click ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.ad_click_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: ai_usage; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_usage (
    day text NOT NULL COLLATE pg_catalog."C",
    feature text NOT NULL COLLATE pg_catalog."C",
    key text DEFAULT ''::text NOT NULL COLLATE pg_catalog."C",
    requests bigint DEFAULT 0 NOT NULL,
    input_tokens bigint DEFAULT 0 NOT NULL,
    cache_write_tokens bigint DEFAULT 0 NOT NULL,
    cache_read_tokens bigint DEFAULT 0 NOT NULL,
    output_tokens bigint DEFAULT 0 NOT NULL
);


--
-- Name: alert; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alert (
    id bigint NOT NULL,
    level text NOT NULL COLLATE pg_catalog."C",
    kind text NOT NULL COLLATE pg_catalog."C",
    apartment_id bigint,
    reservation_id bigint,
    owner_user_id bigint,
    dedupe_key text COLLATE pg_catalog."C",
    message text NOT NULL COLLATE pg_catalog."C",
    detail text COLLATE pg_catalog."C",
    created_at text NOT NULL COLLATE pg_catalog."C",
    resolved_at text COLLATE pg_catalog."C",
    params text COLLATE pg_catalog."C",
    user_dismissed bigint DEFAULT 0 NOT NULL
);


--
-- Name: alert_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.alert ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.alert_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: apartment; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.apartment (
    id bigint NOT NULL,
    legal_entity_id bigint,
    data_controller_entity_id bigint,
    owner_user_id bigint,
    internal_name text NOT NULL COLLATE pg_catalog."C",
    city_en text COLLATE pg_catalog."C",
    addr_okres text COLLATE pg_catalog."C",
    addr_obec text COLLATE pg_catalog."C",
    addr_obec_cast text COLLATE pg_catalog."C",
    addr_street text COLLATE pg_catalog."C",
    addr_house_no text COLLATE pg_catalog."C",
    addr_orient_no text COLLATE pg_catalog."C",
    addr_zip text COLLATE pg_catalog."C",
    uby_idub text COLLATE pg_catalog."C",
    uby_mark text COLLATE pg_catalog."C",
    uby_name text COLLATE pg_catalog."C",
    uby_contact text COLLATE pg_catalog."C",
    uby_ws_user text COLLATE pg_catalog."C",
    uby_ws_password_enc text COLLATE pg_catalog."C",
    automation_mode text DEFAULT 'scheduled'::text NOT NULL COLLATE pg_catalog."C",
    submit_after_hours bigint DEFAULT 24 NOT NULL,
    permalink_token text COLLATE pg_catalog."C",
    permalink_window_days bigint DEFAULT 2 NOT NULL,
    permalink_reachback_days bigint DEFAULT 365 NOT NULL,
    default_purpose text DEFAULT '10'::text NOT NULL COLLATE pg_catalog."C",
    checkin_info text COLLATE pg_catalog."C",
    checkout_info text COLLATE pg_catalog."C",
    guest_message text COLLATE pg_catalog."C",
    notes text COLLATE pg_catalog."C",
    passport_photo_policy text DEFAULT 'off'::text NOT NULL COLLATE pg_catalog."C",
    stay_fee_rate_czk bigint DEFAULT 0 NOT NULL,
    stay_fee_cadence text DEFAULT 'monthly'::text NOT NULL COLLATE pg_catalog."C",
    stay_fee_council_account text COLLATE pg_catalog."C",
    stay_fee_council_iban text COLLATE pg_catalog."C",
    stay_fee_vs text COLLATE pg_catalog."C",
    stay_fee_authority_name text COLLATE pg_catalog."C",
    stay_fee_authority_address text COLLATE pg_catalog."C",
    stay_fee_authority_contact text COLLATE pg_catalog."C",
    stay_fee_payee text COLLATE pg_catalog."C",
    stay_fee_instruction text COLLATE pg_catalog."C",
    active bigint DEFAULT 1 NOT NULL,
    created_at text NOT NULL COLLATE pg_catalog."C",
    permalink_pin text COLLATE pg_catalog."C",
    archived_at text COLLATE pg_catalog."C",
    stay_fee_scope_rule text COLLATE pg_catalog."C",
    stay_fee_scope_reference text COLLATE pg_catalog."C",
    lock_provider text COLLATE pg_catalog."C",
    lock_id text COLLATE pg_catalog."C",
    checkin_hour bigint,
    checkout_hour bigint,
    stay_fee_authority_databox text COLLATE pg_catalog."C",
    guide_token text COLLATE pg_catalog."C",
    leon_enabled bigint DEFAULT 0 NOT NULL,
    leon_terms_version text COLLATE pg_catalog."C",
    leon_terms_accepted_at text COLLATE pg_catalog."C",
    leon_terms_accepted_by bigint,
    ubyport_verified_at text COLLATE pg_catalog."C"
);


--
-- Name: apartment_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.apartment ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.apartment_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: apartment_slug; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.apartment_slug (
    slug text NOT NULL COLLATE pg_catalog."C",
    apartment_id bigint NOT NULL,
    is_current bigint DEFAULT 1 NOT NULL,
    created_at text NOT NULL COLLATE pg_catalog."C"
);


--
-- Name: audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit (
    id bigint NOT NULL,
    at text NOT NULL COLLATE pg_catalog."C",
    actor text COLLATE pg_catalog."C",
    action text NOT NULL COLLATE pg_catalog."C",
    detail text COLLATE pg_catalog."C",
    owner_user_id bigint,
    actor_user_id bigint,
    impersonator_user_id bigint
);


--
-- Name: audit_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.audit ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.audit_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: bank_payment; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bank_payment (
    bank_tx_id text NOT NULL COLLATE pg_catalog."C",
    received_on text NOT NULL COLLATE pg_catalog."C",
    amount_haler bigint NOT NULL,
    vs text COLLATE pg_catalog."C",
    counter_account text COLLATE pg_catalog."C",
    message text COLLATE pg_catalog."C",
    matched_invoice_id bigint,
    status text NOT NULL COLLATE pg_catalog."C",
    CONSTRAINT bank_payment_status_check CHECK ((status = ANY (ARRAY['matched'::text, 'unmatched'::text, 'partial'::text, 'overpaid'::text])))
);


--
-- Name: billing_account; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.billing_account (
    owner_user_id bigint NOT NULL,
    status text DEFAULT 'trial_pending'::text NOT NULL COLLATE pg_catalog."C",
    plan text COLLATE pg_catalog."C",
    billing_interval text COLLATE pg_catalog."C",
    payment_method text DEFAULT 'invoice'::text NOT NULL COLLATE pg_catalog."C",
    founder bigint DEFAULT 0 NOT NULL,
    addon_ttlock bigint DEFAULT 0 NOT NULL,
    addon_whitelabel bigint DEFAULT 0 NOT NULL,
    apartments_billed bigint DEFAULT 0 NOT NULL,
    trial_started_at text COLLATE pg_catalog."C",
    trial_ends_at text COLLATE pg_catalog."C",
    period_start text COLLATE pg_catalog."C",
    period_end text COLLATE pg_catalog."C",
    cancel_at_period_end bigint DEFAULT 0 NOT NULL,
    pending_change_json text COLLATE pg_catalog."C",
    carry_czk bigint DEFAULT 0 NOT NULL,
    buyer_name text COLLATE pg_catalog."C",
    buyer_street text COLLATE pg_catalog."C",
    buyer_city text COLLATE pg_catalog."C",
    buyer_zip text COLLATE pg_catalog."C",
    buyer_ico text COLLATE pg_catalog."C",
    buyer_dic text COLLATE pg_catalog."C",
    buyer_email text COLLATE pg_catalog."C",
    updated_at text NOT NULL COLLATE pg_catalog."C",
    discount_percent bigint DEFAULT 0 NOT NULL,
    discount_reason text COLLATE pg_catalog."C",
    CONSTRAINT billing_account_billing_interval_check CHECK ((billing_interval = ANY (ARRAY['month'::text, 'year'::text]))),
    CONSTRAINT billing_account_discount_percent_check CHECK (((discount_percent >= 0) AND (discount_percent <= 100))),
    CONSTRAINT billing_account_plan_check CHECK ((plan = ANY (ARRAY['standard'::text, 'max'::text]))),
    CONSTRAINT billing_account_status_check CHECK ((status = ANY (ARRAY['trial_pending'::text, 'trialing'::text, 'active'::text, 'overdue'::text, 'canceling'::text, 'paused'::text])))
);


--
-- Name: billing_month_snapshot; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.billing_month_snapshot (
    owner_user_id bigint NOT NULL,
    month text NOT NULL COLLATE pg_catalog."C",
    status text NOT NULL COLLATE pg_catalog."C",
    plan text COLLATE pg_catalog."C",
    billing_interval text COLLATE pg_catalog."C",
    apartments bigint DEFAULT 0 NOT NULL,
    addon_ttlock bigint DEFAULT 0 NOT NULL,
    addon_whitelabel bigint DEFAULT 0 NOT NULL,
    founder bigint DEFAULT 0 NOT NULL,
    discount_percent bigint DEFAULT 0 NOT NULL,
    list_czk bigint DEFAULT 0 NOT NULL,
    net_czk bigint DEFAULT 0 NOT NULL,
    monthly_czk bigint DEFAULT 0 NOT NULL,
    created_at text NOT NULL COLLATE pg_catalog."C"
);


--
-- Name: booking_hold; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.booking_hold (
    id bigint NOT NULL,
    apartment_id bigint NOT NULL,
    date_from text NOT NULL COLLATE pg_catalog."C",
    date_to text NOT NULL COLLATE pg_catalog."C",
    expires_at text NOT NULL COLLATE pg_catalog."C",
    created_at text NOT NULL COLLATE pg_catalog."C"
);


--
-- Name: booking_hold_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.booking_hold ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.booking_hold_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: cleaning_code; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cleaning_code (
    id bigint NOT NULL,
    apartment_id bigint NOT NULL,
    source text NOT NULL COLLATE pg_catalog."C",
    pin_enc text COLLATE pg_catalog."C",
    lock_account_id bigint,
    lock_id text COLLATE pg_catalog."C",
    provider_code_id text COLLATE pg_catalog."C",
    operation_ref text NOT NULL COLLATE pg_catalog."C",
    state text NOT NULL COLLATE pg_catalog."C",
    attempts bigint DEFAULT 0 NOT NULL,
    next_attempt_at text COLLATE pg_catalog."C",
    claimed_at text COLLATE pg_catalog."C",
    last_error text COLLATE pg_catalog."C",
    created_at text NOT NULL COLLATE pg_catalog."C",
    updated_at text NOT NULL COLLATE pg_catalog."C",
    CONSTRAINT cleaning_code_source_check CHECK ((source = ANY (ARRAY['manual'::text, 'ttlock'::text])))
);


--
-- Name: cleaning_code_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.cleaning_code ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.cleaning_code_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: cleaning_event; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cleaning_event (
    id bigint NOT NULL,
    apartment_id bigint NOT NULL,
    source_reservation_id bigint,
    source_date text COLLATE pg_catalog."C",
    scheduled_date text NOT NULL COLLATE pg_catalog."C",
    start_time text COLLATE pg_catalog."C",
    end_time text COLLATE pg_catalog."C",
    notes_enc text COLLATE pg_catalog."C",
    overridden bigint DEFAULT 0 NOT NULL,
    state text DEFAULT 'scheduled'::text NOT NULL COLLATE pg_catalog."C",
    revision bigint DEFAULT 1 NOT NULL,
    created_at text NOT NULL COLLATE pg_catalog."C",
    updated_at text NOT NULL COLLATE pg_catalog."C",
    CONSTRAINT cleaning_event_state_check CHECK ((state = ANY (ARRAY['scheduled'::text, 'dismissed'::text, 'source_cancelled'::text])))
);


--
-- Name: cleaning_event_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.cleaning_event ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.cleaning_event_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: cleaning_property; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cleaning_property (
    id bigint NOT NULL,
    apartment_id bigint NOT NULL,
    instructions text DEFAULT ''::text NOT NULL COLLATE pg_catalog."C",
    checkout_time text COLLATE pg_catalog."C",
    checkin_time text COLLATE pg_catalog."C",
    code_id bigint,
    pending_code_id bigint,
    updated_at text NOT NULL COLLATE pg_catalog."C"
);


--
-- Name: cleaning_property_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.cleaning_property ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.cleaning_property_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: cleaning_share; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cleaning_share (
    id bigint NOT NULL,
    owner_user_id bigint,
    token_hash text NOT NULL COLLATE pg_catalog."C",
    expires_at text NOT NULL COLLATE pg_catalog."C",
    revoked_at text COLLATE pg_catalog."C",
    created_at text NOT NULL COLLATE pg_catalog."C"
);


--
-- Name: cleaning_share_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.cleaning_share ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.cleaning_share_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: cleaning_share_property; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cleaning_share_property (
    id bigint NOT NULL,
    share_id bigint NOT NULL,
    apartment_id bigint NOT NULL
);


--
-- Name: cleaning_share_property_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.cleaning_share_property ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.cleaning_share_property_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: codelist; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.codelist (
    kind text NOT NULL COLLATE pg_catalog."C",
    code text NOT NULL COLLATE pg_catalog."C",
    text_cs text COLLATE pg_catalog."C",
    text_en text COLLATE pg_catalog."C",
    extra text COLLATE pg_catalog."C",
    fetched_at text COLLATE pg_catalog."C"
);


--
-- Name: consent_texts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.consent_texts (
    id bigint NOT NULL,
    version text NOT NULL COLLATE pg_catalog."C",
    purpose text NOT NULL COLLATE pg_catalog."C",
    lang text NOT NULL COLLATE pg_catalog."C",
    text text NOT NULL COLLATE pg_catalog."C",
    text_sha256 text NOT NULL COLLATE pg_catalog."C",
    created_at text NOT NULL COLLATE pg_catalog."C"
);


--
-- Name: consent_texts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.consent_texts ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.consent_texts_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: console_mail_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.console_mail_log (
    id bigint NOT NULL,
    outbox_id bigint,
    to_email text COLLATE pg_catalog."C",
    cc_email text COLLATE pg_catalog."C",
    subject text COLLATE pg_catalog."C",
    body_text text COLLATE pg_catalog."C",
    body_html text COLLATE pg_catalog."C",
    created_at text NOT NULL COLLATE pg_catalog."C"
);


--
-- Name: console_mail_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.console_mail_log ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.console_mail_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: data_subject_request; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.data_subject_request (
    id bigint NOT NULL,
    owner_user_id bigint,
    received_at text NOT NULL COLLATE pg_catalog."C",
    due_at text NOT NULL COLLATE pg_catalog."C",
    channel text NOT NULL COLLATE pg_catalog."C",
    request_type text NOT NULL COLLATE pg_catalog."C",
    subject_kind text NOT NULL COLLATE pg_catalog."C",
    guest_id bigint,
    reservation_id bigint,
    identity_checked_at text COLLATE pg_catalog."C",
    status text DEFAULT 'open'::text NOT NULL COLLATE pg_catalog."C",
    extended_until text COLLATE pg_catalog."C",
    closed_at text COLLATE pg_catalog."C",
    outcome_note text COLLATE pg_catalog."C",
    handled_by bigint,
    created_at text NOT NULL COLLATE pg_catalog."C",
    updated_at text NOT NULL COLLATE pg_catalog."C",
    CONSTRAINT data_subject_request_channel_check CHECK ((channel = ANY (ARRAY['email'::text, 'post'::text, 'in_person'::text, 'support'::text, 'other'::text]))),
    CONSTRAINT data_subject_request_request_type_check CHECK ((request_type = ANY (ARRAY['access'::text, 'rectification'::text, 'erasure'::text, 'restriction'::text, 'portability'::text, 'objection'::text, 'other'::text]))),
    CONSTRAINT data_subject_request_status_check CHECK ((status = ANY (ARRAY['open'::text, 'extended'::text, 'fulfilled'::text, 'refused'::text, 'withdrawn'::text]))),
    CONSTRAINT data_subject_request_subject_kind_check CHECK ((subject_kind = ANY (ARRAY['guest'::text, 'host_user'::text, 'other'::text])))
);


--
-- Name: data_subject_request_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.data_subject_request ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.data_subject_request_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: door_code; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.door_code (
    id bigint NOT NULL,
    reservation_id bigint NOT NULL,
    apartment_id bigint NOT NULL,
    lock_id text NOT NULL COLLATE pg_catalog."C",
    code_kind text DEFAULT 'random'::text NOT NULL COLLATE pg_catalog."C",
    state text DEFAULT 'pending'::text NOT NULL COLLATE pg_catalog."C",
    pin_enc text COLLATE pg_catalog."C",
    provider_code_id text COLLATE pg_catalog."C",
    valid_from text COLLATE pg_catalog."C",
    valid_to text COLLATE pg_catalog."C",
    attempts bigint DEFAULT 0 NOT NULL,
    next_attempt_at text COLLATE pg_catalog."C",
    claimed_at text COLLATE pg_catalog."C",
    last_error text COLLATE pg_catalog."C",
    notified_at text COLLATE pg_catalog."C",
    issued_at text COLLATE pg_catalog."C",
    revoked_at text COLLATE pg_catalog."C",
    created_at text NOT NULL COLLATE pg_catalog."C",
    updated_at text NOT NULL COLLATE pg_catalog."C"
);


--
-- Name: door_code_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.door_code ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.door_code_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: email_outbox; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.email_outbox (
    id bigint NOT NULL,
    idempotency_key text NOT NULL COLLATE pg_catalog."C",
    kind text NOT NULL COLLATE pg_catalog."C",
    reservation_id bigint,
    apartment_id bigint,
    owner_user_id bigint,
    to_email text COLLATE pg_catalog."C",
    cc_email text COLLATE pg_catalog."C",
    subject text COLLATE pg_catalog."C",
    payload text COLLATE pg_catalog."C",
    state text DEFAULT 'queued'::text NOT NULL COLLATE pg_catalog."C",
    attempts bigint DEFAULT 0 NOT NULL,
    next_attempt_at text COLLATE pg_catalog."C",
    provider_id text COLLATE pg_catalog."C",
    last_error text COLLATE pg_catalog."C",
    created_at text NOT NULL COLLATE pg_catalog."C",
    updated_at text NOT NULL COLLATE pg_catalog."C",
    sent_at text COLLATE pg_catalog."C"
);


--
-- Name: email_outbox_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.email_outbox ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.email_outbox_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: founder_slot; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.founder_slot (
    slot bigint NOT NULL,
    owner_user_id bigint,
    claimed_at text NOT NULL COLLATE pg_catalog."C",
    CONSTRAINT founder_slot_slot_check CHECK ((slot >= 1))
);


--
-- Name: guest; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.guest (
    id bigint NOT NULL,
    reservation_id bigint NOT NULL,
    surname text COLLATE pg_catalog."C",
    first_name text COLLATE pg_catalog."C",
    birth_date text COLLATE pg_catalog."C",
    nationality text COLLATE pg_catalog."C",
    doc_number text COLLATE pg_catalog."C",
    visa_number text COLLATE pg_catalog."C",
    doc_number_enc text COLLATE pg_catalog."C",
    visa_number_enc text COLLATE pg_catalog."C",
    res_street text COLLATE pg_catalog."C",
    res_city text COLLATE pg_catalog."C",
    res_country text COLLATE pg_catalog."C",
    purpose text COLLATE pg_catalog."C",
    note text COLLATE pg_catalog."C",
    stay_from text COLLATE pg_catalog."C",
    stay_to text COLLATE pg_catalog."C",
    is_lead bigint DEFAULT 0 NOT NULL,
    signature_png text COLLATE pg_catalog."C",
    signature_png_enc text COLLATE pg_catalog."C",
    restricted_at text COLLATE pg_catalog."C",
    restricted_reason text COLLATE pg_catalog."C",
    doc_type text COLLATE pg_catalog."C",
    fee_host_decision text COLLATE pg_catalog."C",
    fee_host_reason text COLLATE pg_catalog."C",
    signed_at text COLLATE pg_catalog."C",
    notice_version text COLLATE pg_catalog."C",
    notice_lang text COLLATE pg_catalog."C",
    notice_ack_at text COLLATE pg_catalog."C",
    filled_at text COLLATE pg_catalog."C",
    filled_ip text COLLATE pg_catalog."C",
    entered_by text DEFAULT 'guest'::text NOT NULL COLLATE pg_catalog."C",
    submit_state text DEFAULT 'pending'::text NOT NULL COLLATE pg_catalog."C",
    submitted_at text COLLATE pg_catalog."C",
    submission_id bigint,
    last_errors text COLLATE pg_catalog."C",
    submit_attempts bigint DEFAULT 0 NOT NULL,
    created_at text NOT NULL COLLATE pg_catalog."C",
    updated_at text NOT NULL COLLATE pg_catalog."C",
    receipt_submission_id bigint,
    archived_at text COLLATE pg_catalog."C",
    passport_photo_at text COLLATE pg_catalog."C",
    identity_verified_at text COLLATE pg_catalog."C",
    identity_verified_by bigint,
    fee_host_reason_enc text COLLATE pg_catalog."C",
    fee_host_reason_reference text COLLATE pg_catalog."C",
    manual_filed_at text COLLATE pg_catalog."C",
    manual_reference text COLLATE pg_catalog."C",
    manual_marked_at text COLLATE pg_catalog."C",
    manual_prev_state text COLLATE pg_catalog."C",
    birth_date_enc text COLLATE pg_catalog."C",
    res_street_enc text COLLATE pg_catalog."C",
    res_city_enc text COLLATE pg_catalog."C"
);


--
-- Name: guest_chat; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.guest_chat (
    id bigint NOT NULL,
    apartment_id bigint NOT NULL,
    door text NOT NULL COLLATE pg_catalog."C",
    reservation_id bigint,
    cookie_id text COLLATE pg_catalog."C",
    lang text DEFAULT 'en'::text NOT NULL COLLATE pg_catalog."C",
    refusals bigint DEFAULT 0 NOT NULL,
    paused_until text COLLATE pg_catalog."C",
    busy_until text COLLATE pg_catalog."C",
    model_messages bigint DEFAULT 0 NOT NULL,
    created_at text NOT NULL COLLATE pg_catalog."C",
    last_message_at text NOT NULL COLLATE pg_catalog."C",
    CONSTRAINT guest_chat_door_check CHECK ((door = ANY (ARRAY['stay'::text, 'qr'::text])))
);


--
-- Name: guest_chat_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.guest_chat ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.guest_chat_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: guest_chat_message; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.guest_chat_message (
    id bigint NOT NULL,
    chat_id bigint NOT NULL,
    role text NOT NULL COLLATE pg_catalog."C",
    kind text DEFAULT ''::text NOT NULL COLLATE pg_catalog."C",
    text text NOT NULL COLLATE pg_catalog."C",
    sources text DEFAULT ''::text NOT NULL COLLATE pg_catalog."C",
    client_id text COLLATE pg_catalog."C",
    created_at text NOT NULL COLLATE pg_catalog."C",
    CONSTRAINT guest_chat_message_role_check CHECK ((role = ANY (ARRAY['guest'::text, 'leon'::text, 'host'::text])))
);


--
-- Name: guest_chat_message_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.guest_chat_message ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.guest_chat_message_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: guest_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.guest ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.guest_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: guest_question; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.guest_question (
    id bigint NOT NULL,
    chat_id bigint NOT NULL,
    apartment_id bigint NOT NULL,
    message_id bigint NOT NULL,
    summary text NOT NULL COLLATE pg_catalog."C",
    status text DEFAULT 'open'::text NOT NULL COLLATE pg_catalog."C",
    answer text DEFAULT ''::text NOT NULL COLLATE pg_catalog."C",
    urgent bigint DEFAULT 0 NOT NULL,
    triaged bigint DEFAULT 1 NOT NULL,
    created_at text NOT NULL COLLATE pg_catalog."C",
    answered_at text COLLATE pg_catalog."C",
    CONSTRAINT guest_question_status_check CHECK ((status = ANY (ARRAY['open'::text, 'answered'::text, 'dismissed'::text])))
);


--
-- Name: guest_question_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.guest_question ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.guest_question_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: guide_fact; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.guide_fact (
    apartment_id bigint NOT NULL,
    fact text NOT NULL COLLATE pg_catalog."C",
    value text NOT NULL COLLATE pg_catalog."C",
    updated_at text NOT NULL COLLATE pg_catalog."C"
);


--
-- Name: guide_import; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.guide_import (
    id bigint NOT NULL,
    apartment_id bigint NOT NULL,
    source text NOT NULL COLLATE pg_catalog."C",
    url text NOT NULL COLLATE pg_catalog."C",
    status text DEFAULT 'queued'::text NOT NULL COLLATE pg_catalog."C",
    error text COLLATE pg_catalog."C",
    raw_json text COLLATE pg_catalog."C",
    created_at text NOT NULL COLLATE pg_catalog."C",
    started_at text COLLATE pg_catalog."C",
    finished_at text COLLATE pg_catalog."C",
    used_at text COLLATE pg_catalog."C",
    CONSTRAINT guide_import_source_check CHECK ((source = ANY (ARRAY['booking'::text, 'airbnb'::text]))),
    CONSTRAINT guide_import_status_check CHECK ((status = ANY (ARRAY['queued'::text, 'running'::text, 'done'::text, 'failed'::text, 'used'::text, 'expired'::text])))
);


--
-- Name: guide_import_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.guide_import ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.guide_import_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: guide_item; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.guide_item (
    id bigint NOT NULL,
    apartment_id bigint NOT NULL,
    topic text NOT NULL COLLATE pg_catalog."C",
    kind text DEFAULT 'custom'::text NOT NULL COLLATE pg_catalog."C",
    title text DEFAULT ''::text NOT NULL COLLATE pg_catalog."C",
    location text DEFAULT ''::text NOT NULL COLLATE pg_catalog."C",
    steps text DEFAULT ''::text NOT NULL COLLATE pg_catalog."C",
    watch_out text DEFAULT ''::text NOT NULL COLLATE pg_catalog."C",
    video_url text DEFAULT ''::text NOT NULL COLLATE pg_catalog."C",
    visibility text DEFAULT 'everyone'::text NOT NULL COLLATE pg_catalog."C",
    state text DEFAULT 'missing'::text NOT NULL COLLATE pg_catalog."C",
    source text DEFAULT 'host'::text NOT NULL COLLATE pg_catalog."C",
    sort_order bigint DEFAULT 0 NOT NULL,
    created_at text NOT NULL COLLATE pg_catalog."C",
    updated_at text NOT NULL COLLATE pg_catalog."C",
    CONSTRAINT guide_item_source_check CHECK ((source = ANY (ARRAY['host'::text, 'legacy'::text, 'booking'::text, 'airbnb'::text, 'paste'::text, 'ai'::text, 'guest_question'::text]))),
    CONSTRAINT guide_item_state_check CHECK ((state = ANY (ARRAY['missing'::text, 'check'::text, 'done'::text, 'skipped'::text]))),
    CONSTRAINT guide_item_visibility_check CHECK ((visibility = ANY (ARRAY['everyone'::text, 'booked'::text, 'host'::text])))
);


--
-- Name: guide_item_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.guide_item ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.guide_item_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: guide_photo; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.guide_photo (
    id bigint NOT NULL,
    item_id bigint NOT NULL,
    file_name text NOT NULL COLLATE pg_catalog."C",
    sort_order bigint DEFAULT 0 NOT NULL,
    created_at text NOT NULL COLLATE pg_catalog."C"
);


--
-- Name: guide_photo_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.guide_photo ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.guide_photo_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: guide_translation; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.guide_translation (
    id bigint NOT NULL,
    item_id bigint NOT NULL,
    lang text NOT NULL COLLATE pg_catalog."C",
    source_hash text NOT NULL COLLATE pg_catalog."C",
    title text DEFAULT ''::text NOT NULL COLLATE pg_catalog."C",
    location text DEFAULT ''::text NOT NULL COLLATE pg_catalog."C",
    steps text DEFAULT ''::text NOT NULL COLLATE pg_catalog."C",
    watch_out text DEFAULT ''::text NOT NULL COLLATE pg_catalog."C",
    same bigint DEFAULT 0 NOT NULL,
    created_at text NOT NULL COLLATE pg_catalog."C"
);


--
-- Name: guide_translation_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.guide_translation ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.guide_translation_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: havel_gap; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.havel_gap (
    id bigint NOT NULL,
    created_at text NOT NULL COLLATE pg_catalog."C",
    lang text NOT NULL COLLATE pg_catalog."C",
    page text COLLATE pg_catalog."C",
    kind text NOT NULL COLLATE pg_catalog."C",
    question text NOT NULL COLLATE pg_catalog."C"
);


--
-- Name: havel_gap_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.havel_gap ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.havel_gap_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: havel_stats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.havel_stats (
    day text NOT NULL COLLATE pg_catalog."C",
    kind text NOT NULL COLLATE pg_catalog."C",
    count bigint DEFAULT 0 NOT NULL
);


--
-- Name: ical_feed; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ical_feed (
    id bigint NOT NULL,
    apartment_id bigint NOT NULL,
    url text NOT NULL COLLATE pg_catalog."C",
    label text COLLATE pg_catalog."C",
    own_name text COLLATE pg_catalog."C",
    last_sync_at text COLLATE pg_catalog."C",
    last_status text COLLATE pg_catalog."C",
    last_error text COLLATE pg_catalog."C",
    active bigint DEFAULT 1 NOT NULL,
    created_at text NOT NULL COLLATE pg_catalog."C",
    etag text COLLATE pg_catalog."C",
    last_modified text COLLATE pg_catalog."C",
    body_sha256 text COLLATE pg_catalog."C",
    last_checked_at text COLLATE pg_catalog."C"
);


--
-- Name: ical_feed_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.ical_feed ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.ical_feed_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: invoice; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.invoice (
    id bigint NOT NULL,
    legal_entity_id bigint NOT NULL,
    apartment_id bigint,
    reservation_id bigint,
    kind text NOT NULL COLLATE pg_catalog."C",
    corrects_invoice_id bigint,
    correction_reason text COLLATE pg_catalog."C",
    correction_date text COLLATE pg_catalog."C",
    seq_year bigint NOT NULL,
    seq_no bigint NOT NULL,
    number text NOT NULL COLLATE pg_catalog."C",
    vs text NOT NULL COLLATE pg_catalog."C",
    lang text NOT NULL COLLATE pg_catalog."C",
    currency text DEFAULT 'CZK'::text NOT NULL COLLATE pg_catalog."C",
    vat_status text NOT NULL COLLATE pg_catalog."C",
    issue_date text NOT NULL COLLATE pg_catalog."C",
    duzp text COLLATE pg_catalog."C",
    due_date text COLLATE pg_catalog."C",
    paid_on text COLLATE pg_catalog."C",
    paid_via text COLLATE pg_catalog."C",
    note text COLLATE pg_catalog."C",
    seller_name text NOT NULL COLLATE pg_catalog."C",
    seller_seat text NOT NULL COLLATE pg_catalog."C",
    seller_ico text COLLATE pg_catalog."C",
    seller_dic text COLLATE pg_catalog."C",
    seller_registry text COLLATE pg_catalog."C",
    seller_bank_account text COLLATE pg_catalog."C",
    seller_iban text COLLATE pg_catalog."C",
    seller_bic text COLLATE pg_catalog."C",
    seller_email text COLLATE pg_catalog."C",
    seller_phone text COLLATE pg_catalog."C",
    buyer_name text NOT NULL COLLATE pg_catalog."C",
    buyer_street text COLLATE pg_catalog."C",
    buyer_city text COLLATE pg_catalog."C",
    buyer_zip text COLLATE pg_catalog."C",
    buyer_country text COLLATE pg_catalog."C",
    buyer_ico text COLLATE pg_catalog."C",
    buyer_dic text COLLATE pg_catalog."C",
    buyer_email text COLLATE pg_catalog."C",
    stay_from text COLLATE pg_catalog."C",
    stay_to text COLLATE pg_catalog."C",
    stay_label text COLLATE pg_catalog."C",
    total_base_haler bigint,
    total_vat_haler bigint,
    total_haler bigint NOT NULL,
    pdf_blob bytea,
    pdf_sha256 text COLLATE pg_catalog."C",
    issued_at text COLLATE pg_catalog."C",
    issued_by bigint,
    marked_paid_at text COLLATE pg_catalog."C",
    emailed_at text COLLATE pg_catalog."C",
    owner_user_id bigint,
    created_at text NOT NULL COLLATE pg_catalog."C",
    CONSTRAINT invoice_currency_check CHECK ((currency = 'CZK'::text)),
    CONSTRAINT invoice_kind_check CHECK ((kind = ANY (ARRAY['invoice'::text, 'storno'::text, 'corrective'::text]))),
    CONSTRAINT invoice_lang_check CHECK ((lang = ANY (ARRAY['cs'::text, 'en'::text])))
);


--
-- Name: invoice_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.invoice ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.invoice_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: invoice_item; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.invoice_item (
    id bigint NOT NULL,
    invoice_id bigint NOT NULL,
    "position" bigint NOT NULL,
    kind text NOT NULL COLLATE pg_catalog."C",
    description text NOT NULL COLLATE pg_catalog."C",
    quantity bigint DEFAULT 1 NOT NULL,
    unit text DEFAULT ''::text NOT NULL COLLATE pg_catalog."C",
    vat_rate bigint,
    base_haler bigint,
    vat_haler bigint,
    gross_haler bigint NOT NULL,
    CONSTRAINT invoice_item_kind_check CHECK ((kind = ANY (ARRAY['accommodation'::text, 'stay_fee'::text, 'other'::text])))
);


--
-- Name: invoice_item_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.invoice_item ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.invoice_item_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: invoice_sequence; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.invoice_sequence (
    legal_entity_id bigint NOT NULL,
    year bigint NOT NULL,
    last_no bigint NOT NULL
);


--
-- Name: legal_acceptance; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.legal_acceptance (
    id bigint NOT NULL,
    user_account_id bigint NOT NULL,
    document text NOT NULL COLLATE pg_catalog."C",
    version text NOT NULL COLLATE pg_catalog."C",
    accepted_at text NOT NULL COLLATE pg_catalog."C",
    method text NOT NULL COLLATE pg_catalog."C",
    ip text COLLATE pg_catalog."C",
    user_agent text COLLATE pg_catalog."C",
    CONSTRAINT legal_acceptance_document_check CHECK ((document = ANY (ARRAY['terms'::text, 'privacy'::text, 'dpa'::text]))),
    CONSTRAINT legal_acceptance_method_check CHECK ((method = ANY (ARRAY['clickwrap'::text, 'login_notice'::text, 'backfill'::text])))
);


--
-- Name: legal_acceptance_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.legal_acceptance ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.legal_acceptance_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: legal_entity; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.legal_entity (
    id bigint NOT NULL,
    name text NOT NULL COLLATE pg_catalog."C",
    seat text COLLATE pg_catalog."C",
    ico text COLLATE pg_catalog."C",
    dic text COLLATE pg_catalog."C",
    contact_email text COLLATE pg_catalog."C",
    contact_phone text COLLATE pg_catalog."C",
    bank_account text COLLATE pg_catalog."C",
    iban text COLLATE pg_catalog."C",
    bic text COLLATE pg_catalog."C",
    signature_png_enc text COLLATE pg_catalog."C",
    signature_name text COLLATE pg_catalog."C",
    vat_status text DEFAULT 'non_payer'::text NOT NULL COLLATE pg_catalog."C",
    registry_entry text COLLATE pg_catalog."C",
    invoice_prefix text COLLATE pg_catalog."C",
    invoice_next_number bigint,
    invoice_next_number_year bigint,
    invoice_due_days bigint DEFAULT 14 NOT NULL,
    owner_user_id bigint,
    created_at text NOT NULL COLLATE pg_catalog."C",
    archived_at text COLLATE pg_catalog."C",
    business_type text DEFAULT 'individual'::text NOT NULL COLLATE pg_catalog."C",
    CONSTRAINT legal_entity_business_type_check CHECK ((business_type = ANY (ARRAY['individual'::text, 'company'::text])))
);


--
-- Name: legal_entity_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.legal_entity ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.legal_entity_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: lifecycle_mail_sent; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lifecycle_mail_sent (
    user_account_id bigint NOT NULL,
    kind text NOT NULL COLLATE pg_catalog."C",
    sent_at text NOT NULL COLLATE pg_catalog."C"
);


--
-- Name: lock_account; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lock_account (
    id bigint NOT NULL,
    owner_user_id bigint NOT NULL,
    provider text DEFAULT 'ttlock'::text NOT NULL COLLATE pg_catalog."C",
    username text NOT NULL COLLATE pg_catalog."C",
    password_enc text COLLATE pg_catalog."C",
    access_token_enc text COLLATE pg_catalog."C",
    refresh_token_enc text COLLATE pg_catalog."C",
    token_expires_at text COLLATE pg_catalog."C",
    token_version bigint DEFAULT 0 NOT NULL,
    status text DEFAULT 'ok'::text NOT NULL COLLATE pg_catalog."C",
    locks_json text COLLATE pg_catalog."C",
    locks_fetched_at text COLLATE pg_catalog."C",
    created_at text NOT NULL COLLATE pg_catalog."C",
    updated_at text NOT NULL COLLATE pg_catalog."C"
);


--
-- Name: lock_account_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.lock_account ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.lock_account_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: lock_api_usage; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lock_api_usage (
    month text NOT NULL COLLATE pg_catalog."C",
    provider text NOT NULL COLLATE pg_catalog."C",
    calls bigint DEFAULT 0 NOT NULL
);


--
-- Name: login_token; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.login_token (
    id bigint NOT NULL,
    token_hash text NOT NULL COLLATE pg_catalog."C",
    user_account_id bigint NOT NULL,
    purpose text NOT NULL COLLATE pg_catalog."C",
    email text NOT NULL COLLATE pg_catalog."C",
    remember bigint DEFAULT 0 NOT NULL,
    next_path text COLLATE pg_catalog."C",
    created_at text NOT NULL COLLATE pg_catalog."C",
    expires_at text NOT NULL COLLATE pg_catalog."C",
    used_at text COLLATE pg_catalog."C"
);


--
-- Name: login_token_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.login_token ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.login_token_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: mail_suppression; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mail_suppression (
    email_hash text NOT NULL COLLATE pg_catalog."C",
    scope text NOT NULL COLLATE pg_catalog."C",
    created_at text NOT NULL COLLATE pg_catalog."C"
);


--
-- Name: passkey; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.passkey (
    id bigint NOT NULL,
    user_account_id bigint NOT NULL,
    credential_id text NOT NULL COLLATE pg_catalog."C",
    public_key text NOT NULL COLLATE pg_catalog."C",
    sign_count bigint DEFAULT 0 NOT NULL,
    transports text COLLATE pg_catalog."C",
    name text NOT NULL COLLATE pg_catalog."C",
    backed_up bigint DEFAULT 0 NOT NULL,
    created_at text NOT NULL COLLATE pg_catalog."C",
    last_used_at text COLLATE pg_catalog."C"
);


--
-- Name: passkey_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.passkey ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.passkey_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: payment_request; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payment_request (
    id bigint NOT NULL,
    owner_user_id bigint NOT NULL,
    apartment_id bigint,
    reservation_id bigint,
    reason text NOT NULL COLLATE pg_catalog."C",
    amount_czk bigint NOT NULL,
    currency text DEFAULT 'CZK'::text NOT NULL COLLATE pg_catalog."C",
    guest_email text COLLATE pg_catalog."C",
    guest_note text COLLATE pg_catalog."C",
    rail text NOT NULL COLLATE pg_catalog."C",
    status text DEFAULT 'draft'::text NOT NULL COLLATE pg_catalog."C",
    variable_symbol text COLLATE pg_catalog."C",
    stripe_payment_link_id text COLLATE pg_catalog."C",
    stripe_session_id text COLLATE pg_catalog."C",
    stripe_payment_intent_id text COLLATE pg_catalog."C",
    invoice_id bigint,
    paid_at text COLLATE pg_catalog."C",
    expires_at text NOT NULL COLLATE pg_catalog."C",
    created_at text NOT NULL COLLATE pg_catalog."C",
    updated_at text NOT NULL COLLATE pg_catalog."C",
    CONSTRAINT payment_request_amount_czk_check CHECK ((amount_czk >= 1)),
    CONSTRAINT payment_request_currency_check CHECK ((currency = 'CZK'::text)),
    CONSTRAINT payment_request_rail_check CHECK ((rail = ANY (ARRAY['card'::text, 'qr'::text]))),
    CONSTRAINT payment_request_reason_check CHECK ((reason = ANY (ARRAY['repair'::text, 'extra_guest'::text, 'late_checkout'::text, 'cleaning'::text, 'damage'::text, 'custom'::text]))),
    CONSTRAINT payment_request_status_check CHECK ((status = ANY (ARRAY['draft'::text, 'sent'::text, 'awaiting_payment'::text, 'paid'::text, 'expired'::text, 'cancelled'::text])))
);


--
-- Name: payment_request_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.payment_request ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.payment_request_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: platform_invoice; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.platform_invoice (
    id bigint NOT NULL,
    owner_user_id bigint,
    kind text NOT NULL COLLATE pg_catalog."C",
    corrects_id bigint,
    seq_year bigint NOT NULL,
    seq_no bigint NOT NULL,
    number text NOT NULL COLLATE pg_catalog."C",
    vs text NOT NULL COLLATE pg_catalog."C",
    issue_date text NOT NULL COLLATE pg_catalog."C",
    due_date text NOT NULL COLLATE pg_catalog."C",
    period_from text NOT NULL COLLATE pg_catalog."C",
    period_to text NOT NULL COLLATE pg_catalog."C",
    total_haler bigint NOT NULL,
    voided bigint DEFAULT 0 NOT NULL,
    paid_on text COLLATE pg_catalog."C",
    paid_via text COLLATE pg_catalog."C",
    snapshot_json text NOT NULL COLLATE pg_catalog."C",
    created_at text NOT NULL COLLATE pg_catalog."C",
    pdf_blob bytea,
    pdf_sha256 text COLLATE pg_catalog."C",
    CONSTRAINT platform_invoice_kind_check CHECK ((kind = ANY (ARRAY['invoice'::text, 'supplementary'::text, 'storno'::text]))),
    CONSTRAINT platform_invoice_paid_via_check CHECK ((paid_via = ANY (ARRAY['bank_auto'::text, 'bank_manual'::text])))
);


--
-- Name: platform_invoice_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.platform_invoice ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.platform_invoice_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: platform_invoice_sequence; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.platform_invoice_sequence (
    year bigint NOT NULL,
    last_no bigint NOT NULL
);


--
-- Name: property_page; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.property_page (
    id bigint NOT NULL,
    apartment_id bigint NOT NULL,
    description text COLLATE pg_catalog."C",
    photos_json text COLLATE pg_catalog."C",
    amenities_json text COLLATE pg_catalog."C",
    checkin_text text COLLATE pg_catalog."C",
    checkout_text text COLLATE pg_catalog."C",
    published bigint DEFAULT 0 NOT NULL,
    published_at text COLLATE pg_catalog."C",
    hide_from_search bigint DEFAULT 1 NOT NULL,
    created_at text NOT NULL COLLATE pg_catalog."C",
    updated_at text NOT NULL COLLATE pg_catalog."C",
    nightly_price_czk bigint
);


--
-- Name: property_page_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.property_page ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.property_page_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: property_slug; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.property_slug (
    id bigint NOT NULL,
    apartment_id bigint NOT NULL,
    slug text NOT NULL COLLATE pg_catalog."C",
    published bigint DEFAULT 0 NOT NULL,
    published_at text COLLATE pg_catalog."C",
    created_at text NOT NULL COLLATE pg_catalog."C",
    updated_at text NOT NULL COLLATE pg_catalog."C"
);


--
-- Name: property_slug_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.property_slug_history (
    old_slug text NOT NULL COLLATE pg_catalog."C",
    apartment_id bigint NOT NULL,
    created_at text NOT NULL COLLATE pg_catalog."C"
);


--
-- Name: property_slug_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.property_slug ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.property_slug_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: push_outbox; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.push_outbox (
    id bigint NOT NULL,
    idempotency_key text NOT NULL COLLATE pg_catalog."C",
    subscription_id bigint NOT NULL,
    user_account_id bigint NOT NULL,
    kind text NOT NULL COLLATE pg_catalog."C",
    params text DEFAULT '{}'::text NOT NULL COLLATE pg_catalog."C",
    url text DEFAULT '/'::text NOT NULL COLLATE pg_catalog."C",
    state text DEFAULT 'queued'::text NOT NULL COLLATE pg_catalog."C",
    attempts bigint DEFAULT 0 NOT NULL,
    next_attempt_at text NOT NULL COLLATE pg_catalog."C",
    last_status bigint,
    created_at text NOT NULL COLLATE pg_catalog."C",
    sent_at text COLLATE pg_catalog."C",
    CONSTRAINT push_outbox_state_check CHECK ((state = ANY (ARRAY['queued'::text, 'sent'::text, 'failed'::text])))
);


--
-- Name: push_outbox_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.push_outbox ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.push_outbox_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: push_subscription; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.push_subscription (
    id bigint NOT NULL,
    user_account_id bigint NOT NULL,
    endpoint_hash text NOT NULL COLLATE pg_catalog."C",
    endpoint_enc text NOT NULL COLLATE pg_catalog."C",
    p256dh_enc text NOT NULL COLLATE pg_catalog."C",
    auth_enc text NOT NULL COLLATE pg_catalog."C",
    lang text DEFAULT 'en'::text NOT NULL COLLATE pg_catalog."C",
    device text DEFAULT ''::text NOT NULL COLLATE pg_catalog."C",
    failures bigint DEFAULT 0 NOT NULL,
    created_at text NOT NULL COLLATE pg_catalog."C",
    last_seen_at text NOT NULL COLLATE pg_catalog."C",
    last_sent_at text COLLATE pg_catalog."C"
);


--
-- Name: push_subscription_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.push_subscription ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.push_subscription_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: rate_limit_event; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rate_limit_event (
    id bigint NOT NULL,
    scope text NOT NULL COLLATE pg_catalog."C",
    key text NOT NULL COLLATE pg_catalog."C",
    at double precision NOT NULL
);


--
-- Name: rate_limit_event_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.rate_limit_event ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.rate_limit_event_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: reservation; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reservation (
    id bigint NOT NULL,
    apartment_id bigint NOT NULL,
    ical_feed_id bigint,
    source text DEFAULT 'ical'::text NOT NULL COLLATE pg_catalog."C",
    uid text NOT NULL COLLATE pg_catalog."C",
    date_from text NOT NULL COLLATE pg_catalog."C",
    date_to text NOT NULL COLLATE pg_catalog."C",
    summary text COLLATE pg_catalog."C",
    reservation_url text COLLATE pg_catalog."C",
    phone_last4 text COLLATE pg_catalog."C",
    declared_guests bigint,
    expected_guests_override bigint,
    registration_completed_at text COLLATE pg_catalog."C",
    guest_email text COLLATE pg_catalog."C",
    host_note text COLLATE pg_catalog."C",
    status text DEFAULT 'active'::text NOT NULL COLLATE pg_catalog."C",
    created_at text NOT NULL COLLATE pg_catalog."C",
    updated_at text NOT NULL COLLATE pg_catalog."C",
    archived_at text COLLATE pg_catalog."C",
    at_risk_mailed_at text COLLATE pg_catalog."C"
);


--
-- Name: reservation_claim; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reservation_claim (
    reservation_id bigint NOT NULL,
    state text DEFAULT 'unclaimed'::text NOT NULL COLLATE pg_catalog."C",
    email text COLLATE pg_catalog."C",
    email_masked text COLLATE pg_catalog."C",
    lang text COLLATE pg_catalog."C",
    token_hash text COLLATE pg_catalog."C",
    token_version bigint DEFAULT 0 NOT NULL,
    provisional_until text COLLATE pg_catalog."C",
    claimed_at text COLLATE pg_catalog."C",
    guest_access_locked_at text COLLATE pg_catalog."C",
    guest_access_reopened_at text COLLATE pg_catalog."C",
    declared_guests bigint,
    completion_notified_at text COLLATE pg_catalog."C",
    created_at text NOT NULL COLLATE pg_catalog."C",
    updated_at text NOT NULL COLLATE pg_catalog."C",
    CONSTRAINT reservation_claim_state_check CHECK ((state = ANY (ARRAY['unclaimed'::text, 'provisional'::text, 'claimed'::text])))
);


--
-- Name: reservation_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.reservation ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.reservation_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: schema_migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.schema_migrations (
    version bigint NOT NULL,
    name text NOT NULL COLLATE pg_catalog."C",
    applied_at text NOT NULL COLLATE pg_catalog."C"
);


--
-- Name: security_incident; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.security_incident (
    id bigint NOT NULL,
    detected_at text NOT NULL COLLATE pg_catalog."C",
    reported_by text COLLATE pg_catalog."C",
    summary text NOT NULL COLLATE pg_catalog."C",
    data_categories text COLLATE pg_catalog."C",
    affected_owner_ids text COLLATE pg_catalog."C",
    approx_subjects bigint,
    risk_level text COLLATE pg_catalog."C",
    contained_at text COLLATE pg_catalog."C",
    controllers_notified_at text COLLATE pg_catalog."C",
    authority_notified_at text COLLATE pg_catalog."C",
    subjects_notified_at text COLLATE pg_catalog."C",
    closed_at text COLLATE pg_catalog."C",
    notes text COLLATE pg_catalog."C",
    created_at text NOT NULL COLLATE pg_catalog."C",
    updated_at text NOT NULL COLLATE pg_catalog."C",
    CONSTRAINT security_incident_risk_level_check CHECK ((risk_level = ANY (ARRAY['none'::text, 'low'::text, 'high'::text])))
);


--
-- Name: security_incident_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.security_incident ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.security_incident_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.settings (
    key text NOT NULL COLLATE pg_catalog."C",
    value text COLLATE pg_catalog."C"
);


--
-- Name: stay_fee_adjustment; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.stay_fee_adjustment (
    id bigint NOT NULL,
    apartment_id bigint NOT NULL,
    period_key text NOT NULL COLLATE pg_catalog."C",
    direction text NOT NULL COLLATE pg_catalog."C",
    mode text NOT NULL COLLATE pg_catalog."C",
    people_count bigint,
    nights bigint,
    bed_days bigint NOT NULL,
    reason_enc text NOT NULL COLLATE pg_catalog."C",
    created_by bigint,
    created_at text NOT NULL COLLATE pg_catalog."C",
    reversed_at text COLLATE pg_catalog."C",
    reversed_by bigint,
    filing_id bigint,
    CONSTRAINT stay_fee_adjustment_direction_check CHECK ((direction = ANY (ARRAY['add'::text, 'remove'::text]))),
    CONSTRAINT stay_fee_adjustment_mode_check CHECK ((mode = ANY (ARRAY['people'::text, 'bed_days'::text])))
);


--
-- Name: stay_fee_adjustment_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.stay_fee_adjustment ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.stay_fee_adjustment_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: stay_fee_filing; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.stay_fee_filing (
    id bigint NOT NULL,
    apartment_id bigint NOT NULL,
    period_key text NOT NULL COLLATE pg_catalog."C",
    version bigint DEFAULT 1 NOT NULL,
    cadence text NOT NULL COLLATE pg_catalog."C",
    rate_czk bigint NOT NULL,
    liable_days bigint NOT NULL,
    exempt_days bigint NOT NULL,
    total_due_czk bigint NOT NULL,
    total_collected_czk bigint NOT NULL,
    pdf_enc bytea,
    csv_enc bytea,
    payload_enc text COLLATE pg_catalog."C",
    created_at text NOT NULL COLLATE pg_catalog."C",
    superseded_at text COLLATE pg_catalog."C",
    sent_at text COLLATE pg_catalog."C",
    sent_message_id text COLLATE pg_catalog."C",
    paid_at text COLLATE pg_catalog."C"
);


--
-- Name: stay_fee_filing_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.stay_fee_filing ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.stay_fee_filing_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: stripe_account; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.stripe_account (
    id bigint NOT NULL,
    owner_user_id bigint NOT NULL,
    stripe_account_id text NOT NULL COLLATE pg_catalog."C",
    mode text NOT NULL COLLATE pg_catalog."C",
    onboarding_state text DEFAULT 'pending'::text NOT NULL COLLATE pg_catalog."C",
    charges_enabled bigint DEFAULT 0 NOT NULL,
    payouts_enabled bigint DEFAULT 0 NOT NULL,
    requirements_json text COLLATE pg_catalog."C",
    payout_delay_days bigint DEFAULT 7 NOT NULL,
    created_at text NOT NULL COLLATE pg_catalog."C",
    updated_at text NOT NULL COLLATE pg_catalog."C",
    CONSTRAINT stripe_account_mode_check CHECK ((mode = ANY (ARRAY['test'::text, 'live'::text]))),
    CONSTRAINT stripe_account_onboarding_state_check CHECK ((onboarding_state = ANY (ARRAY['pending'::text, 'action_required'::text, 'complete'::text, 'rejected'::text, 'disabled'::text]))),
    CONSTRAINT stripe_account_payout_delay_days_check CHECK (((payout_delay_days >= 0) AND (payout_delay_days <= 14)))
);


--
-- Name: stripe_account_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.stripe_account ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.stripe_account_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: stripe_webhook_event; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.stripe_webhook_event (
    id bigint NOT NULL,
    event_id text NOT NULL COLLATE pg_catalog."C",
    event_type text NOT NULL COLLATE pg_catalog."C",
    mode text NOT NULL COLLATE pg_catalog."C",
    created_at text NOT NULL COLLATE pg_catalog."C",
    CONSTRAINT stripe_webhook_event_mode_check CHECK ((mode = ANY (ARRAY['test'::text, 'live'::text])))
);


--
-- Name: stripe_webhook_event_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.stripe_webhook_event ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.stripe_webhook_event_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: submission; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.submission (
    id bigint NOT NULL,
    apartment_id bigint NOT NULL,
    created_at text NOT NULL COLLATE pg_catalog."C",
    finished_at text COLLATE pg_catalog."C",
    mode text COLLATE pg_catalog."C",
    state text DEFAULT 'running'::text NOT NULL COLLATE pg_catalog."C",
    guest_ids text COLLATE pg_catalog."C",
    header_errors text COLLATE pg_catalog."C",
    record_errors text COLLATE pg_catalog."C",
    pseudo_stamp text COLLATE pg_catalog."C",
    receipt_pdf text COLLATE pg_catalog."C",
    error_pdf text COLLATE pg_catalog."C",
    endpoint text COLLATE pg_catalog."C",
    request_xml text COLLATE pg_catalog."C",
    response_xml text COLLATE pg_catalog."C",
    error_text text COLLATE pg_catalog."C",
    retried_at text COLLATE pg_catalog."C",
    request_xml_enc text COLLATE pg_catalog."C"
);


--
-- Name: submission_claim; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.submission_claim (
    guest_id bigint NOT NULL,
    claim_token text NOT NULL COLLATE pg_catalog."C",
    claimed_at double precision NOT NULL
);


--
-- Name: submission_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.submission ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.submission_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: user_account; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_account (
    id bigint NOT NULL,
    username text NOT NULL COLLATE pg_catalog."C",
    display_name text COLLATE pg_catalog."C",
    password_hash text NOT NULL COLLATE pg_catalog."C",
    role text DEFAULT 'host'::text NOT NULL COLLATE pg_catalog."C",
    active bigint DEFAULT 1 NOT NULL,
    must_change_password bigint DEFAULT 1 NOT NULL,
    session_version bigint DEFAULT 1 NOT NULL,
    created_at text NOT NULL COLLATE pg_catalog."C",
    last_login_at text COLLATE pg_catalog."C",
    deletion_due_at text COLLATE pg_catalog."C",
    totp_secret_enc text COLLATE pg_catalog."C",
    totp_enabled bigint DEFAULT 0 NOT NULL,
    recovery_codes_hash text COLLATE pg_catalog."C",
    totp_last_step bigint,
    onboarding_emails_opt_out bigint DEFAULT 0 NOT NULL,
    onboarding_emails_opt_out_at text COLLATE pg_catalog."C",
    email text COLLATE pg_catalog."C",
    email_verified_at text COLLATE pg_catalog."C",
    signup_at text COLLATE pg_catalog."C",
    signup_verify_nonce text COLLATE pg_catalog."C",
    signup_utm_source text COLLATE pg_catalog."C",
    signup_utm_medium text COLLATE pg_catalog."C",
    signup_utm_campaign text COLLATE pg_catalog."C",
    signup_source text COLLATE pg_catalog."C",
    webauthn_user_handle text COLLATE pg_catalog."C",
    two_factor_prompted_at text COLLATE pg_catalog."C",
    posthog_stage text COLLATE pg_catalog."C",
    stay_fee_emails_opt_out bigint DEFAULT 0 NOT NULL,
    stay_fee_emails_opt_out_at text COLLATE pg_catalog."C",
    signup_selection_json text COLLATE pg_catalog."C",
    CONSTRAINT user_account_role_check CHECK ((role = ANY (ARRAY['admin'::text, 'host'::text])))
);


--
-- Name: user_account_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.user_account ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.user_account_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: webauthn_challenge; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.webauthn_challenge (
    id bigint NOT NULL,
    challenge_hash text NOT NULL COLLATE pg_catalog."C",
    purpose text NOT NULL COLLATE pg_catalog."C",
    user_account_id bigint,
    created_at text NOT NULL COLLATE pg_catalog."C",
    expires_at text NOT NULL COLLATE pg_catalog."C",
    used_at text COLLATE pg_catalog."C"
);


--
-- Name: webauthn_challenge_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.webauthn_challenge ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.webauthn_challenge_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: ad_click ad_click_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ad_click
    ADD CONSTRAINT ad_click_pkey PRIMARY KEY (id);


--
-- Name: ad_click ad_click_user_account_id_platform_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ad_click
    ADD CONSTRAINT ad_click_user_account_id_platform_key UNIQUE (user_account_id, platform);


--
-- Name: ai_usage ai_usage_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_usage
    ADD CONSTRAINT ai_usage_pkey PRIMARY KEY (day, feature, key);


--
-- Name: alert alert_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alert
    ADD CONSTRAINT alert_pkey PRIMARY KEY (id);


--
-- Name: apartment apartment_permalink_token_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.apartment
    ADD CONSTRAINT apartment_permalink_token_key UNIQUE (permalink_token);


--
-- Name: apartment apartment_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.apartment
    ADD CONSTRAINT apartment_pkey PRIMARY KEY (id);


--
-- Name: apartment_slug apartment_slug_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.apartment_slug
    ADD CONSTRAINT apartment_slug_pkey PRIMARY KEY (slug);


--
-- Name: audit audit_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit
    ADD CONSTRAINT audit_pkey PRIMARY KEY (id);


--
-- Name: bank_payment bank_payment_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bank_payment
    ADD CONSTRAINT bank_payment_pkey PRIMARY KEY (bank_tx_id);


--
-- Name: billing_account billing_account_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.billing_account
    ADD CONSTRAINT billing_account_pkey PRIMARY KEY (owner_user_id);


--
-- Name: billing_month_snapshot billing_month_snapshot_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.billing_month_snapshot
    ADD CONSTRAINT billing_month_snapshot_pkey PRIMARY KEY (owner_user_id, month);


--
-- Name: booking_hold booking_hold_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.booking_hold
    ADD CONSTRAINT booking_hold_pkey PRIMARY KEY (id);


--
-- Name: cleaning_code cleaning_code_operation_ref_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cleaning_code
    ADD CONSTRAINT cleaning_code_operation_ref_key UNIQUE (operation_ref);


--
-- Name: cleaning_code cleaning_code_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cleaning_code
    ADD CONSTRAINT cleaning_code_pkey PRIMARY KEY (id);


--
-- Name: cleaning_event cleaning_event_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cleaning_event
    ADD CONSTRAINT cleaning_event_pkey PRIMARY KEY (id);


--
-- Name: cleaning_event cleaning_event_source_reservation_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cleaning_event
    ADD CONSTRAINT cleaning_event_source_reservation_id_key UNIQUE (source_reservation_id);


--
-- Name: cleaning_property cleaning_property_apartment_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cleaning_property
    ADD CONSTRAINT cleaning_property_apartment_id_key UNIQUE (apartment_id);


--
-- Name: cleaning_property cleaning_property_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cleaning_property
    ADD CONSTRAINT cleaning_property_pkey PRIMARY KEY (id);


--
-- Name: cleaning_share cleaning_share_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cleaning_share
    ADD CONSTRAINT cleaning_share_pkey PRIMARY KEY (id);


--
-- Name: cleaning_share_property cleaning_share_property_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cleaning_share_property
    ADD CONSTRAINT cleaning_share_property_pkey PRIMARY KEY (id);


--
-- Name: cleaning_share_property cleaning_share_property_share_id_apartment_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cleaning_share_property
    ADD CONSTRAINT cleaning_share_property_share_id_apartment_id_key UNIQUE (share_id, apartment_id);


--
-- Name: cleaning_share cleaning_share_token_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cleaning_share
    ADD CONSTRAINT cleaning_share_token_hash_key UNIQUE (token_hash);


--
-- Name: codelist codelist_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.codelist
    ADD CONSTRAINT codelist_pkey PRIMARY KEY (kind, code);


--
-- Name: consent_texts consent_texts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.consent_texts
    ADD CONSTRAINT consent_texts_pkey PRIMARY KEY (id);


--
-- Name: consent_texts consent_texts_version_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.consent_texts
    ADD CONSTRAINT consent_texts_version_key UNIQUE (version);


--
-- Name: console_mail_log console_mail_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.console_mail_log
    ADD CONSTRAINT console_mail_log_pkey PRIMARY KEY (id);


--
-- Name: data_subject_request data_subject_request_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.data_subject_request
    ADD CONSTRAINT data_subject_request_pkey PRIMARY KEY (id);


--
-- Name: door_code door_code_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.door_code
    ADD CONSTRAINT door_code_pkey PRIMARY KEY (id);


--
-- Name: door_code door_code_reservation_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.door_code
    ADD CONSTRAINT door_code_reservation_id_key UNIQUE (reservation_id);


--
-- Name: email_outbox email_outbox_idempotency_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.email_outbox
    ADD CONSTRAINT email_outbox_idempotency_key_key UNIQUE (idempotency_key);


--
-- Name: email_outbox email_outbox_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.email_outbox
    ADD CONSTRAINT email_outbox_pkey PRIMARY KEY (id);


--
-- Name: founder_slot founder_slot_owner_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.founder_slot
    ADD CONSTRAINT founder_slot_owner_user_id_key UNIQUE (owner_user_id);


--
-- Name: founder_slot founder_slot_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.founder_slot
    ADD CONSTRAINT founder_slot_pkey PRIMARY KEY (slot);


--
-- Name: guest_chat_message guest_chat_message_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.guest_chat_message
    ADD CONSTRAINT guest_chat_message_pkey PRIMARY KEY (id);


--
-- Name: guest_chat guest_chat_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.guest_chat
    ADD CONSTRAINT guest_chat_pkey PRIMARY KEY (id);


--
-- Name: guest guest_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.guest
    ADD CONSTRAINT guest_pkey PRIMARY KEY (id);


--
-- Name: guest_question guest_question_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.guest_question
    ADD CONSTRAINT guest_question_pkey PRIMARY KEY (id);


--
-- Name: guide_fact guide_fact_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.guide_fact
    ADD CONSTRAINT guide_fact_pkey PRIMARY KEY (apartment_id, fact);


--
-- Name: guide_import guide_import_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.guide_import
    ADD CONSTRAINT guide_import_pkey PRIMARY KEY (id);


--
-- Name: guide_item guide_item_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.guide_item
    ADD CONSTRAINT guide_item_pkey PRIMARY KEY (id);


--
-- Name: guide_photo guide_photo_file_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.guide_photo
    ADD CONSTRAINT guide_photo_file_name_key UNIQUE (file_name);


--
-- Name: guide_photo guide_photo_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.guide_photo
    ADD CONSTRAINT guide_photo_pkey PRIMARY KEY (id);


--
-- Name: guide_translation guide_translation_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.guide_translation
    ADD CONSTRAINT guide_translation_pkey PRIMARY KEY (id);


--
-- Name: havel_gap havel_gap_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.havel_gap
    ADD CONSTRAINT havel_gap_pkey PRIMARY KEY (id);


--
-- Name: havel_stats havel_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.havel_stats
    ADD CONSTRAINT havel_stats_pkey PRIMARY KEY (day, kind);


--
-- Name: ical_feed ical_feed_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ical_feed
    ADD CONSTRAINT ical_feed_pkey PRIMARY KEY (id);


--
-- Name: invoice_item invoice_item_invoice_id_position_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_item
    ADD CONSTRAINT invoice_item_invoice_id_position_key UNIQUE (invoice_id, "position");


--
-- Name: invoice_item invoice_item_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_item
    ADD CONSTRAINT invoice_item_pkey PRIMARY KEY (id);


--
-- Name: invoice invoice_legal_entity_id_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice
    ADD CONSTRAINT invoice_legal_entity_id_number_key UNIQUE (legal_entity_id, number);


--
-- Name: invoice invoice_legal_entity_id_seq_year_seq_no_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice
    ADD CONSTRAINT invoice_legal_entity_id_seq_year_seq_no_key UNIQUE (legal_entity_id, seq_year, seq_no);


--
-- Name: invoice invoice_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice
    ADD CONSTRAINT invoice_pkey PRIMARY KEY (id);


--
-- Name: invoice_sequence invoice_sequence_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_sequence
    ADD CONSTRAINT invoice_sequence_pkey PRIMARY KEY (legal_entity_id, year);


--
-- Name: legal_acceptance legal_acceptance_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_acceptance
    ADD CONSTRAINT legal_acceptance_pkey PRIMARY KEY (id);


--
-- Name: legal_acceptance legal_acceptance_user_account_id_document_version_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_acceptance
    ADD CONSTRAINT legal_acceptance_user_account_id_document_version_key UNIQUE (user_account_id, document, version);


--
-- Name: legal_entity legal_entity_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_entity
    ADD CONSTRAINT legal_entity_pkey PRIMARY KEY (id);


--
-- Name: lifecycle_mail_sent lifecycle_mail_sent_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lifecycle_mail_sent
    ADD CONSTRAINT lifecycle_mail_sent_pkey PRIMARY KEY (user_account_id, kind);


--
-- Name: lock_account lock_account_owner_user_id_provider_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lock_account
    ADD CONSTRAINT lock_account_owner_user_id_provider_key UNIQUE (owner_user_id, provider);


--
-- Name: lock_account lock_account_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lock_account
    ADD CONSTRAINT lock_account_pkey PRIMARY KEY (id);


--
-- Name: lock_api_usage lock_api_usage_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lock_api_usage
    ADD CONSTRAINT lock_api_usage_pkey PRIMARY KEY (month, provider);


--
-- Name: login_token login_token_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.login_token
    ADD CONSTRAINT login_token_pkey PRIMARY KEY (id);


--
-- Name: login_token login_token_token_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.login_token
    ADD CONSTRAINT login_token_token_hash_key UNIQUE (token_hash);


--
-- Name: mail_suppression mail_suppression_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mail_suppression
    ADD CONSTRAINT mail_suppression_pkey PRIMARY KEY (email_hash, scope);


--
-- Name: passkey passkey_credential_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.passkey
    ADD CONSTRAINT passkey_credential_id_key UNIQUE (credential_id);


--
-- Name: passkey passkey_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.passkey
    ADD CONSTRAINT passkey_pkey PRIMARY KEY (id);


--
-- Name: payment_request payment_request_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_request
    ADD CONSTRAINT payment_request_pkey PRIMARY KEY (id);


--
-- Name: payment_request payment_request_variable_symbol_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_request
    ADD CONSTRAINT payment_request_variable_symbol_key UNIQUE (variable_symbol);


--
-- Name: platform_invoice platform_invoice_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.platform_invoice
    ADD CONSTRAINT platform_invoice_number_key UNIQUE (number);


--
-- Name: platform_invoice platform_invoice_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.platform_invoice
    ADD CONSTRAINT platform_invoice_pkey PRIMARY KEY (id);


--
-- Name: platform_invoice platform_invoice_seq_year_seq_no_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.platform_invoice
    ADD CONSTRAINT platform_invoice_seq_year_seq_no_key UNIQUE (seq_year, seq_no);


--
-- Name: platform_invoice_sequence platform_invoice_sequence_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.platform_invoice_sequence
    ADD CONSTRAINT platform_invoice_sequence_pkey PRIMARY KEY (year);


--
-- Name: platform_invoice platform_invoice_vs_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.platform_invoice
    ADD CONSTRAINT platform_invoice_vs_key UNIQUE (vs);


--
-- Name: property_page property_page_apartment_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.property_page
    ADD CONSTRAINT property_page_apartment_id_key UNIQUE (apartment_id);


--
-- Name: property_page property_page_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.property_page
    ADD CONSTRAINT property_page_pkey PRIMARY KEY (id);


--
-- Name: property_slug property_slug_apartment_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.property_slug
    ADD CONSTRAINT property_slug_apartment_id_key UNIQUE (apartment_id);


--
-- Name: property_slug_history property_slug_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.property_slug_history
    ADD CONSTRAINT property_slug_history_pkey PRIMARY KEY (old_slug);


--
-- Name: property_slug property_slug_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.property_slug
    ADD CONSTRAINT property_slug_pkey PRIMARY KEY (id);


--
-- Name: property_slug property_slug_slug_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.property_slug
    ADD CONSTRAINT property_slug_slug_key UNIQUE (slug);


--
-- Name: push_outbox push_outbox_idempotency_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.push_outbox
    ADD CONSTRAINT push_outbox_idempotency_key_key UNIQUE (idempotency_key);


--
-- Name: push_outbox push_outbox_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.push_outbox
    ADD CONSTRAINT push_outbox_pkey PRIMARY KEY (id);


--
-- Name: push_subscription push_subscription_endpoint_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.push_subscription
    ADD CONSTRAINT push_subscription_endpoint_hash_key UNIQUE (endpoint_hash);


--
-- Name: push_subscription push_subscription_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.push_subscription
    ADD CONSTRAINT push_subscription_pkey PRIMARY KEY (id);


--
-- Name: rate_limit_event rate_limit_event_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rate_limit_event
    ADD CONSTRAINT rate_limit_event_pkey PRIMARY KEY (id);


--
-- Name: reservation reservation_apartment_id_uid_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reservation
    ADD CONSTRAINT reservation_apartment_id_uid_key UNIQUE (apartment_id, uid);


--
-- Name: reservation_claim reservation_claim_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reservation_claim
    ADD CONSTRAINT reservation_claim_pkey PRIMARY KEY (reservation_id);


--
-- Name: reservation reservation_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reservation
    ADD CONSTRAINT reservation_pkey PRIMARY KEY (id);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: security_incident security_incident_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_incident
    ADD CONSTRAINT security_incident_pkey PRIMARY KEY (id);


--
-- Name: settings settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.settings
    ADD CONSTRAINT settings_pkey PRIMARY KEY (key);


--
-- Name: stay_fee_adjustment stay_fee_adjustment_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stay_fee_adjustment
    ADD CONSTRAINT stay_fee_adjustment_pkey PRIMARY KEY (id);


--
-- Name: stay_fee_filing stay_fee_filing_apartment_id_period_key_version_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stay_fee_filing
    ADD CONSTRAINT stay_fee_filing_apartment_id_period_key_version_key UNIQUE (apartment_id, period_key, version);


--
-- Name: stay_fee_filing stay_fee_filing_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stay_fee_filing
    ADD CONSTRAINT stay_fee_filing_pkey PRIMARY KEY (id);


--
-- Name: stripe_account stripe_account_owner_user_id_mode_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stripe_account
    ADD CONSTRAINT stripe_account_owner_user_id_mode_key UNIQUE (owner_user_id, mode);


--
-- Name: stripe_account stripe_account_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stripe_account
    ADD CONSTRAINT stripe_account_pkey PRIMARY KEY (id);


--
-- Name: stripe_account stripe_account_stripe_account_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stripe_account
    ADD CONSTRAINT stripe_account_stripe_account_id_key UNIQUE (stripe_account_id);


--
-- Name: stripe_webhook_event stripe_webhook_event_event_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stripe_webhook_event
    ADD CONSTRAINT stripe_webhook_event_event_id_key UNIQUE (event_id);


--
-- Name: stripe_webhook_event stripe_webhook_event_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stripe_webhook_event
    ADD CONSTRAINT stripe_webhook_event_pkey PRIMARY KEY (id);


--
-- Name: submission_claim submission_claim_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.submission_claim
    ADD CONSTRAINT submission_claim_pkey PRIMARY KEY (guest_id);


--
-- Name: submission submission_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.submission
    ADD CONSTRAINT submission_pkey PRIMARY KEY (id);


--
-- Name: user_account user_account_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_account
    ADD CONSTRAINT user_account_pkey PRIMARY KEY (id);


--
-- Name: user_account user_account_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_account
    ADD CONSTRAINT user_account_username_key UNIQUE (username);


--
-- Name: webauthn_challenge webauthn_challenge_challenge_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.webauthn_challenge
    ADD CONSTRAINT webauthn_challenge_challenge_hash_key UNIQUE (challenge_hash);


--
-- Name: webauthn_challenge webauthn_challenge_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.webauthn_challenge
    ADD CONSTRAINT webauthn_challenge_pkey PRIMARY KEY (id);


--
-- Name: havel_gap_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX havel_gap_created ON public.havel_gap USING btree (created_at);


--
-- Name: idx_acceptance_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_acceptance_user ON public.legal_acceptance USING btree (user_account_id, document);


--
-- Name: idx_ad_click_platform; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ad_click_platform ON public.ad_click USING btree (platform, uploaded_at);


--
-- Name: idx_ad_click_send; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ad_click_send ON public.ad_click USING btree (send_state, next_attempt_at);


--
-- Name: idx_alert_dedupe; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_alert_dedupe ON public.alert USING btree (dedupe_key) WHERE (resolved_at IS NULL);


--
-- Name: idx_alert_owner; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_alert_owner ON public.alert USING btree (owner_user_id, resolved_at);


--
-- Name: idx_apartment_owner; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_apartment_owner ON public.apartment USING btree (owner_user_id);


--
-- Name: idx_audit_owner; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_owner ON public.audit USING btree (owner_user_id, id);


--
-- Name: idx_bank_payment_vs; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bank_payment_vs ON public.bank_payment USING btree (vs);


--
-- Name: idx_billing_snapshot_month; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_billing_snapshot_month ON public.billing_month_snapshot USING btree (month);


--
-- Name: idx_booking_hold_apartment; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_booking_hold_apartment ON public.booking_hold USING btree (apartment_id, date_from);


--
-- Name: idx_booking_hold_expires; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_booking_hold_expires ON public.booking_hold USING btree (expires_at);


--
-- Name: idx_cleaning_code_due; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cleaning_code_due ON public.cleaning_code USING btree (state, next_attempt_at);


--
-- Name: idx_cleaning_schedule; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cleaning_schedule ON public.cleaning_event USING btree (apartment_id, scheduled_date, state);


--
-- Name: idx_door_code_due; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_door_code_due ON public.door_code USING btree (state, next_attempt_at);


--
-- Name: idx_dsr_owner_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dsr_owner_status ON public.data_subject_request USING btree (owner_user_id, status, due_at);


--
-- Name: idx_entity_owner; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_entity_owner ON public.legal_entity USING btree (owner_user_id);


--
-- Name: idx_guest_chat_last; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_guest_chat_last ON public.guest_chat USING btree (door, last_message_at);


--
-- Name: idx_guest_chat_message_chat; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_guest_chat_message_chat ON public.guest_chat_message USING btree (chat_id, id);


--
-- Name: idx_guest_question_open; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_guest_question_open ON public.guest_question USING btree (apartment_id, status, created_at);


--
-- Name: idx_guest_receipt_submission; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_guest_receipt_submission ON public.guest USING btree (receipt_submission_id);


--
-- Name: idx_guest_reservation; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_guest_reservation ON public.guest USING btree (reservation_id);


--
-- Name: idx_guest_submission; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_guest_submission ON public.guest USING btree (submission_id);


--
-- Name: idx_guide_import_apartment; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_guide_import_apartment ON public.guide_import USING btree (apartment_id, status, created_at);


--
-- Name: idx_guide_import_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_guide_import_status ON public.guide_import USING btree (status, id);


--
-- Name: idx_guide_item_apartment; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_guide_item_apartment ON public.guide_item USING btree (apartment_id, topic, sort_order);


--
-- Name: idx_guide_photo_item; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_guide_photo_item ON public.guide_photo USING btree (item_id, sort_order);


--
-- Name: idx_invoice_one_correction; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_invoice_one_correction ON public.invoice USING btree (corrects_invoice_id) WHERE (corrects_invoice_id IS NOT NULL);


--
-- Name: idx_invoice_owner; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_invoice_owner ON public.invoice USING btree (owner_user_id, issue_date);


--
-- Name: idx_invoice_reservation; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_invoice_reservation ON public.invoice USING btree (reservation_id);


--
-- Name: idx_login_token_expires; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_login_token_expires ON public.login_token USING btree (expires_at);


--
-- Name: idx_login_token_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_login_token_user ON public.login_token USING btree (user_account_id, purpose);


--
-- Name: idx_outbox_state_attempt; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_outbox_state_attempt ON public.email_outbox USING btree (state, next_attempt_at);


--
-- Name: idx_passkey_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_passkey_user ON public.passkey USING btree (user_account_id);


--
-- Name: idx_payment_request_owner; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_payment_request_owner ON public.payment_request USING btree (owner_user_id);


--
-- Name: idx_payment_request_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_payment_request_status ON public.payment_request USING btree (status);


--
-- Name: idx_platform_invoice_owner; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_platform_invoice_owner ON public.platform_invoice USING btree (owner_user_id);


--
-- Name: idx_platform_invoice_period; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_platform_invoice_period ON public.platform_invoice USING btree (owner_user_id, period_from, period_to) WHERE ((kind = 'invoice'::text) AND (voided = 0));


--
-- Name: idx_platform_invoice_unpaid_due; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_platform_invoice_unpaid_due ON public.platform_invoice USING btree (due_date, paid_on);


--
-- Name: idx_property_slug_history_apartment; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_property_slug_history_apartment ON public.property_slug_history USING btree (apartment_id);


--
-- Name: idx_push_outbox_device; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_push_outbox_device ON public.push_outbox USING btree (subscription_id, state, sent_at);


--
-- Name: idx_push_outbox_due; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_push_outbox_due ON public.push_outbox USING btree (state, next_attempt_at);


--
-- Name: idx_push_subscription_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_push_subscription_user ON public.push_subscription USING btree (user_account_id);


--
-- Name: idx_rate_limit_scope_key; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rate_limit_scope_key ON public.rate_limit_event USING btree (scope, key, at);


--
-- Name: idx_res_apartment_dates; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_res_apartment_dates ON public.reservation USING btree (apartment_id, date_from);


--
-- Name: idx_reservation_feed; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reservation_feed ON public.reservation USING btree (ical_feed_id);


--
-- Name: idx_slug_current; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_slug_current ON public.apartment_slug USING btree (apartment_id) WHERE (is_current = 1);


--
-- Name: idx_stay_fee_adjustment_period; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_stay_fee_adjustment_period ON public.stay_fee_adjustment USING btree (apartment_id, period_key);


--
-- Name: idx_stay_fee_filing_lookup; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_stay_fee_filing_lookup ON public.stay_fee_filing USING btree (apartment_id, period_key);


--
-- Name: idx_submission_apartment; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_submission_apartment ON public.submission USING btree (apartment_id);


--
-- Name: idx_user_account_email; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_user_account_email ON public.user_account USING btree (email);


--
-- Name: idx_webauthn_challenge_expires; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_webauthn_challenge_expires ON public.webauthn_challenge USING btree (expires_at);


--
-- Name: ubyhost_user_account_username_sqlite_nocase; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ubyhost_user_account_username_sqlite_nocase ON public.user_account USING btree (translate(username, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'::text, 'abcdefghijklmnopqrstuvwxyz'::text));


--
-- Name: uq_apartment_guide_token; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_apartment_guide_token ON public.apartment USING btree (guide_token) WHERE (guide_token IS NOT NULL);


--
-- Name: uq_guest_chat_message_client; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_guest_chat_message_client ON public.guest_chat_message USING btree (chat_id, client_id) WHERE (client_id IS NOT NULL);


--
-- Name: uq_guest_chat_qr; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_guest_chat_qr ON public.guest_chat USING btree (apartment_id, cookie_id) WHERE (door = 'qr'::text);


--
-- Name: uq_guest_chat_stay; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_guest_chat_stay ON public.guest_chat USING btree (reservation_id) WHERE (door = 'stay'::text);


--
-- Name: uq_guide_item_kind; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_guide_item_kind ON public.guide_item USING btree (apartment_id, kind) WHERE (kind <> 'custom'::text);


--
-- Name: uq_guide_translation; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_guide_translation ON public.guide_translation USING btree (item_id, lang);


--
-- Name: invoice invoice_delete_guard; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER invoice_delete_guard BEFORE DELETE ON public.invoice FOR EACH ROW EXECUTE FUNCTION public.ubyhost_invoice_delete_guard();


--
-- Name: invoice invoice_issued_guard; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER invoice_issued_guard BEFORE UPDATE OF legal_entity_id, apartment_id, kind, corrects_invoice_id, correction_reason, correction_date, seq_year, seq_no, number, vs, lang, currency, vat_status, issue_date, duzp, due_date, paid_on, paid_via, seller_name, seller_seat, seller_ico, seller_dic, seller_registry, seller_bank_account, seller_iban, seller_bic, seller_email, seller_phone, buyer_name, buyer_street, buyer_city, buyer_zip, buyer_country, buyer_ico, buyer_dic, buyer_email, stay_from, stay_to, stay_label, total_base_haler, total_vat_haler, total_haler, pdf_blob, pdf_sha256, issued_at, issued_by ON public.invoice FOR EACH ROW EXECUTE FUNCTION public.ubyhost_invoice_issued_guard();


--
-- Name: invoice_item invoice_item_delete_guard; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER invoice_item_delete_guard BEFORE DELETE ON public.invoice_item FOR EACH ROW EXECUTE FUNCTION public.ubyhost_invoice_item_delete_guard();


--
-- Name: invoice_item invoice_item_insert_guard; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER invoice_item_insert_guard BEFORE INSERT ON public.invoice_item FOR EACH ROW EXECUTE FUNCTION public.ubyhost_invoice_item_insert_guard();


--
-- Name: invoice_item invoice_item_update_guard; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER invoice_item_update_guard BEFORE UPDATE ON public.invoice_item FOR EACH ROW EXECUTE FUNCTION public.ubyhost_invoice_item_update_guard();


--
-- Name: invoice invoice_note_guard; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER invoice_note_guard BEFORE UPDATE OF note ON public.invoice FOR EACH ROW EXECUTE FUNCTION public.ubyhost_invoice_note_guard();


--
-- Name: ad_click ad_click_consent_text_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ad_click
    ADD CONSTRAINT ad_click_consent_text_id_fkey FOREIGN KEY (consent_text_id) REFERENCES public.consent_texts(id) DEFERRABLE;


--
-- Name: ad_click ad_click_user_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ad_click
    ADD CONSTRAINT ad_click_user_account_id_fkey FOREIGN KEY (user_account_id) REFERENCES public.user_account(id) DEFERRABLE;


--
-- Name: alert alert_owner_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alert
    ADD CONSTRAINT alert_owner_user_id_fkey FOREIGN KEY (owner_user_id) REFERENCES public.user_account(id) DEFERRABLE;


--
-- Name: apartment apartment_data_controller_entity_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.apartment
    ADD CONSTRAINT apartment_data_controller_entity_id_fkey FOREIGN KEY (data_controller_entity_id) REFERENCES public.legal_entity(id) DEFERRABLE;


--
-- Name: apartment apartment_legal_entity_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.apartment
    ADD CONSTRAINT apartment_legal_entity_id_fkey FOREIGN KEY (legal_entity_id) REFERENCES public.legal_entity(id) DEFERRABLE;


--
-- Name: apartment apartment_owner_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.apartment
    ADD CONSTRAINT apartment_owner_user_id_fkey FOREIGN KEY (owner_user_id) REFERENCES public.user_account(id) DEFERRABLE;


--
-- Name: apartment_slug apartment_slug_apartment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.apartment_slug
    ADD CONSTRAINT apartment_slug_apartment_id_fkey FOREIGN KEY (apartment_id) REFERENCES public.apartment(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: audit audit_actor_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit
    ADD CONSTRAINT audit_actor_user_id_fkey FOREIGN KEY (actor_user_id) REFERENCES public.user_account(id) ON DELETE SET NULL DEFERRABLE;


--
-- Name: audit audit_impersonator_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit
    ADD CONSTRAINT audit_impersonator_user_id_fkey FOREIGN KEY (impersonator_user_id) REFERENCES public.user_account(id) ON DELETE SET NULL DEFERRABLE;


--
-- Name: audit audit_owner_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit
    ADD CONSTRAINT audit_owner_user_id_fkey FOREIGN KEY (owner_user_id) REFERENCES public.user_account(id) DEFERRABLE;


--
-- Name: bank_payment bank_payment_matched_invoice_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bank_payment
    ADD CONSTRAINT bank_payment_matched_invoice_id_fkey FOREIGN KEY (matched_invoice_id) REFERENCES public.platform_invoice(id) DEFERRABLE;


--
-- Name: billing_account billing_account_owner_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.billing_account
    ADD CONSTRAINT billing_account_owner_user_id_fkey FOREIGN KEY (owner_user_id) REFERENCES public.user_account(id) DEFERRABLE;


--
-- Name: booking_hold booking_hold_apartment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.booking_hold
    ADD CONSTRAINT booking_hold_apartment_id_fkey FOREIGN KEY (apartment_id) REFERENCES public.apartment(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: cleaning_code cleaning_code_apartment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cleaning_code
    ADD CONSTRAINT cleaning_code_apartment_id_fkey FOREIGN KEY (apartment_id) REFERENCES public.apartment(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: cleaning_code cleaning_code_lock_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cleaning_code
    ADD CONSTRAINT cleaning_code_lock_account_id_fkey FOREIGN KEY (lock_account_id) REFERENCES public.lock_account(id) ON DELETE SET NULL DEFERRABLE;


--
-- Name: cleaning_event cleaning_event_apartment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cleaning_event
    ADD CONSTRAINT cleaning_event_apartment_id_fkey FOREIGN KEY (apartment_id) REFERENCES public.apartment(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: cleaning_event cleaning_event_source_reservation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cleaning_event
    ADD CONSTRAINT cleaning_event_source_reservation_id_fkey FOREIGN KEY (source_reservation_id) REFERENCES public.reservation(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: cleaning_property cleaning_property_apartment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cleaning_property
    ADD CONSTRAINT cleaning_property_apartment_id_fkey FOREIGN KEY (apartment_id) REFERENCES public.apartment(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: cleaning_property cleaning_property_code_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cleaning_property
    ADD CONSTRAINT cleaning_property_code_id_fkey FOREIGN KEY (code_id) REFERENCES public.cleaning_code(id) ON DELETE SET NULL DEFERRABLE;


--
-- Name: cleaning_property cleaning_property_pending_code_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cleaning_property
    ADD CONSTRAINT cleaning_property_pending_code_id_fkey FOREIGN KEY (pending_code_id) REFERENCES public.cleaning_code(id) ON DELETE SET NULL DEFERRABLE;


--
-- Name: cleaning_share cleaning_share_owner_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cleaning_share
    ADD CONSTRAINT cleaning_share_owner_user_id_fkey FOREIGN KEY (owner_user_id) REFERENCES public.user_account(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: cleaning_share_property cleaning_share_property_apartment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cleaning_share_property
    ADD CONSTRAINT cleaning_share_property_apartment_id_fkey FOREIGN KEY (apartment_id) REFERENCES public.apartment(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: cleaning_share_property cleaning_share_property_share_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cleaning_share_property
    ADD CONSTRAINT cleaning_share_property_share_id_fkey FOREIGN KEY (share_id) REFERENCES public.cleaning_share(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: data_subject_request data_subject_request_guest_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.data_subject_request
    ADD CONSTRAINT data_subject_request_guest_id_fkey FOREIGN KEY (guest_id) REFERENCES public.guest(id) ON DELETE SET NULL DEFERRABLE;


--
-- Name: data_subject_request data_subject_request_handled_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.data_subject_request
    ADD CONSTRAINT data_subject_request_handled_by_fkey FOREIGN KEY (handled_by) REFERENCES public.user_account(id) DEFERRABLE;


--
-- Name: data_subject_request data_subject_request_owner_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.data_subject_request
    ADD CONSTRAINT data_subject_request_owner_user_id_fkey FOREIGN KEY (owner_user_id) REFERENCES public.user_account(id) DEFERRABLE;


--
-- Name: data_subject_request data_subject_request_reservation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.data_subject_request
    ADD CONSTRAINT data_subject_request_reservation_id_fkey FOREIGN KEY (reservation_id) REFERENCES public.reservation(id) ON DELETE SET NULL DEFERRABLE;


--
-- Name: door_code door_code_apartment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.door_code
    ADD CONSTRAINT door_code_apartment_id_fkey FOREIGN KEY (apartment_id) REFERENCES public.apartment(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: door_code door_code_reservation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.door_code
    ADD CONSTRAINT door_code_reservation_id_fkey FOREIGN KEY (reservation_id) REFERENCES public.reservation(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: email_outbox email_outbox_reservation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.email_outbox
    ADD CONSTRAINT email_outbox_reservation_id_fkey FOREIGN KEY (reservation_id) REFERENCES public.reservation(id) ON DELETE SET NULL DEFERRABLE;


--
-- Name: founder_slot founder_slot_owner_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.founder_slot
    ADD CONSTRAINT founder_slot_owner_user_id_fkey FOREIGN KEY (owner_user_id) REFERENCES public.user_account(id) DEFERRABLE;


--
-- Name: guest_chat guest_chat_apartment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.guest_chat
    ADD CONSTRAINT guest_chat_apartment_id_fkey FOREIGN KEY (apartment_id) REFERENCES public.apartment(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: guest_chat_message guest_chat_message_chat_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.guest_chat_message
    ADD CONSTRAINT guest_chat_message_chat_id_fkey FOREIGN KEY (chat_id) REFERENCES public.guest_chat(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: guest_chat guest_chat_reservation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.guest_chat
    ADD CONSTRAINT guest_chat_reservation_id_fkey FOREIGN KEY (reservation_id) REFERENCES public.reservation(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: guest_question guest_question_apartment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.guest_question
    ADD CONSTRAINT guest_question_apartment_id_fkey FOREIGN KEY (apartment_id) REFERENCES public.apartment(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: guest_question guest_question_chat_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.guest_question
    ADD CONSTRAINT guest_question_chat_id_fkey FOREIGN KEY (chat_id) REFERENCES public.guest_chat(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: guest_question guest_question_message_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.guest_question
    ADD CONSTRAINT guest_question_message_id_fkey FOREIGN KEY (message_id) REFERENCES public.guest_chat_message(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: guest guest_receipt_submission_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.guest
    ADD CONSTRAINT guest_receipt_submission_id_fkey FOREIGN KEY (receipt_submission_id) REFERENCES public.submission(id) ON DELETE SET NULL DEFERRABLE;


--
-- Name: guest guest_reservation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.guest
    ADD CONSTRAINT guest_reservation_id_fkey FOREIGN KEY (reservation_id) REFERENCES public.reservation(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: guest guest_submission_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.guest
    ADD CONSTRAINT guest_submission_id_fkey FOREIGN KEY (submission_id) REFERENCES public.submission(id) ON DELETE SET NULL DEFERRABLE;


--
-- Name: guide_fact guide_fact_apartment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.guide_fact
    ADD CONSTRAINT guide_fact_apartment_id_fkey FOREIGN KEY (apartment_id) REFERENCES public.apartment(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: guide_import guide_import_apartment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.guide_import
    ADD CONSTRAINT guide_import_apartment_id_fkey FOREIGN KEY (apartment_id) REFERENCES public.apartment(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: guide_item guide_item_apartment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.guide_item
    ADD CONSTRAINT guide_item_apartment_id_fkey FOREIGN KEY (apartment_id) REFERENCES public.apartment(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: guide_photo guide_photo_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.guide_photo
    ADD CONSTRAINT guide_photo_item_id_fkey FOREIGN KEY (item_id) REFERENCES public.guide_item(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: guide_translation guide_translation_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.guide_translation
    ADD CONSTRAINT guide_translation_item_id_fkey FOREIGN KEY (item_id) REFERENCES public.guide_item(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: ical_feed ical_feed_apartment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ical_feed
    ADD CONSTRAINT ical_feed_apartment_id_fkey FOREIGN KEY (apartment_id) REFERENCES public.apartment(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: invoice invoice_apartment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice
    ADD CONSTRAINT invoice_apartment_id_fkey FOREIGN KEY (apartment_id) REFERENCES public.apartment(id) DEFERRABLE;


--
-- Name: invoice invoice_corrects_invoice_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice
    ADD CONSTRAINT invoice_corrects_invoice_id_fkey FOREIGN KEY (corrects_invoice_id) REFERENCES public.invoice(id) DEFERRABLE;


--
-- Name: invoice invoice_issued_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice
    ADD CONSTRAINT invoice_issued_by_fkey FOREIGN KEY (issued_by) REFERENCES public.user_account(id) DEFERRABLE;


--
-- Name: invoice_item invoice_item_invoice_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_item
    ADD CONSTRAINT invoice_item_invoice_id_fkey FOREIGN KEY (invoice_id) REFERENCES public.invoice(id) DEFERRABLE;


--
-- Name: invoice invoice_legal_entity_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice
    ADD CONSTRAINT invoice_legal_entity_id_fkey FOREIGN KEY (legal_entity_id) REFERENCES public.legal_entity(id) DEFERRABLE;


--
-- Name: invoice invoice_owner_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice
    ADD CONSTRAINT invoice_owner_user_id_fkey FOREIGN KEY (owner_user_id) REFERENCES public.user_account(id) DEFERRABLE;


--
-- Name: invoice invoice_reservation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice
    ADD CONSTRAINT invoice_reservation_id_fkey FOREIGN KEY (reservation_id) REFERENCES public.reservation(id) ON DELETE SET NULL DEFERRABLE;


--
-- Name: invoice_sequence invoice_sequence_legal_entity_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_sequence
    ADD CONSTRAINT invoice_sequence_legal_entity_id_fkey FOREIGN KEY (legal_entity_id) REFERENCES public.legal_entity(id) DEFERRABLE;


--
-- Name: legal_acceptance legal_acceptance_user_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_acceptance
    ADD CONSTRAINT legal_acceptance_user_account_id_fkey FOREIGN KEY (user_account_id) REFERENCES public.user_account(id) DEFERRABLE;


--
-- Name: legal_entity legal_entity_owner_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_entity
    ADD CONSTRAINT legal_entity_owner_user_id_fkey FOREIGN KEY (owner_user_id) REFERENCES public.user_account(id) DEFERRABLE;


--
-- Name: lifecycle_mail_sent lifecycle_mail_sent_user_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lifecycle_mail_sent
    ADD CONSTRAINT lifecycle_mail_sent_user_account_id_fkey FOREIGN KEY (user_account_id) REFERENCES public.user_account(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: lock_account lock_account_owner_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lock_account
    ADD CONSTRAINT lock_account_owner_user_id_fkey FOREIGN KEY (owner_user_id) REFERENCES public.user_account(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: login_token login_token_user_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.login_token
    ADD CONSTRAINT login_token_user_account_id_fkey FOREIGN KEY (user_account_id) REFERENCES public.user_account(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: passkey passkey_user_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.passkey
    ADD CONSTRAINT passkey_user_account_id_fkey FOREIGN KEY (user_account_id) REFERENCES public.user_account(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: payment_request payment_request_apartment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_request
    ADD CONSTRAINT payment_request_apartment_id_fkey FOREIGN KEY (apartment_id) REFERENCES public.apartment(id) ON DELETE SET NULL DEFERRABLE;


--
-- Name: payment_request payment_request_invoice_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_request
    ADD CONSTRAINT payment_request_invoice_id_fkey FOREIGN KEY (invoice_id) REFERENCES public.invoice(id) ON DELETE SET NULL DEFERRABLE;


--
-- Name: payment_request payment_request_owner_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_request
    ADD CONSTRAINT payment_request_owner_user_id_fkey FOREIGN KEY (owner_user_id) REFERENCES public.user_account(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: payment_request payment_request_reservation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_request
    ADD CONSTRAINT payment_request_reservation_id_fkey FOREIGN KEY (reservation_id) REFERENCES public.reservation(id) ON DELETE SET NULL DEFERRABLE;


--
-- Name: platform_invoice platform_invoice_corrects_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.platform_invoice
    ADD CONSTRAINT platform_invoice_corrects_id_fkey FOREIGN KEY (corrects_id) REFERENCES public.platform_invoice(id) DEFERRABLE;


--
-- Name: platform_invoice platform_invoice_owner_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.platform_invoice
    ADD CONSTRAINT platform_invoice_owner_user_id_fkey FOREIGN KEY (owner_user_id) REFERENCES public.user_account(id) DEFERRABLE;


--
-- Name: property_page property_page_apartment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.property_page
    ADD CONSTRAINT property_page_apartment_id_fkey FOREIGN KEY (apartment_id) REFERENCES public.apartment(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: property_slug property_slug_apartment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.property_slug
    ADD CONSTRAINT property_slug_apartment_id_fkey FOREIGN KEY (apartment_id) REFERENCES public.apartment(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: property_slug_history property_slug_history_apartment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.property_slug_history
    ADD CONSTRAINT property_slug_history_apartment_id_fkey FOREIGN KEY (apartment_id) REFERENCES public.apartment(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: push_outbox push_outbox_subscription_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.push_outbox
    ADD CONSTRAINT push_outbox_subscription_id_fkey FOREIGN KEY (subscription_id) REFERENCES public.push_subscription(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: push_outbox push_outbox_user_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.push_outbox
    ADD CONSTRAINT push_outbox_user_account_id_fkey FOREIGN KEY (user_account_id) REFERENCES public.user_account(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: push_subscription push_subscription_user_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.push_subscription
    ADD CONSTRAINT push_subscription_user_account_id_fkey FOREIGN KEY (user_account_id) REFERENCES public.user_account(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: reservation reservation_apartment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reservation
    ADD CONSTRAINT reservation_apartment_id_fkey FOREIGN KEY (apartment_id) REFERENCES public.apartment(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: reservation_claim reservation_claim_reservation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reservation_claim
    ADD CONSTRAINT reservation_claim_reservation_id_fkey FOREIGN KEY (reservation_id) REFERENCES public.reservation(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: reservation reservation_ical_feed_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reservation
    ADD CONSTRAINT reservation_ical_feed_id_fkey FOREIGN KEY (ical_feed_id) REFERENCES public.ical_feed(id) ON DELETE SET NULL DEFERRABLE;


--
-- Name: stay_fee_adjustment stay_fee_adjustment_apartment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stay_fee_adjustment
    ADD CONSTRAINT stay_fee_adjustment_apartment_id_fkey FOREIGN KEY (apartment_id) REFERENCES public.apartment(id) DEFERRABLE;


--
-- Name: stay_fee_adjustment stay_fee_adjustment_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stay_fee_adjustment
    ADD CONSTRAINT stay_fee_adjustment_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.user_account(id) DEFERRABLE;


--
-- Name: stay_fee_adjustment stay_fee_adjustment_filing_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stay_fee_adjustment
    ADD CONSTRAINT stay_fee_adjustment_filing_id_fkey FOREIGN KEY (filing_id) REFERENCES public.stay_fee_filing(id) DEFERRABLE;


--
-- Name: stay_fee_adjustment stay_fee_adjustment_reversed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stay_fee_adjustment
    ADD CONSTRAINT stay_fee_adjustment_reversed_by_fkey FOREIGN KEY (reversed_by) REFERENCES public.user_account(id) DEFERRABLE;


--
-- Name: stay_fee_filing stay_fee_filing_apartment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stay_fee_filing
    ADD CONSTRAINT stay_fee_filing_apartment_id_fkey FOREIGN KEY (apartment_id) REFERENCES public.apartment(id) DEFERRABLE;


--
-- Name: stripe_account stripe_account_owner_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stripe_account
    ADD CONSTRAINT stripe_account_owner_user_id_fkey FOREIGN KEY (owner_user_id) REFERENCES public.user_account(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: submission submission_apartment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.submission
    ADD CONSTRAINT submission_apartment_id_fkey FOREIGN KEY (apartment_id) REFERENCES public.apartment(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: submission_claim submission_claim_guest_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.submission_claim
    ADD CONSTRAINT submission_claim_guest_id_fkey FOREIGN KEY (guest_id) REFERENCES public.guest(id) ON DELETE CASCADE DEFERRABLE;


--
-- Name: webauthn_challenge webauthn_challenge_user_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.webauthn_challenge
    ADD CONSTRAINT webauthn_challenge_user_account_id_fkey FOREIGN KEY (user_account_id) REFERENCES public.user_account(id) ON DELETE CASCADE DEFERRABLE;


--
-- PostgreSQL database dump complete
--


INSERT INTO public.schema_migrations VALUES (1, 'baseline', '2026-10-31T19:15:08+00:00');
INSERT INTO public.schema_migrations VALUES (2, 'apartment_slug', '2026-10-31T19:15:08+00:00');
INSERT INTO public.schema_migrations VALUES (3, 'signup', '2026-10-31T19:15:08+00:00');
INSERT INTO public.schema_migrations VALUES (4, 'meta_capi', '2026-10-31T19:15:08+00:00');
INSERT INTO public.schema_migrations VALUES (5, 'email_login', '2026-10-31T19:15:08+00:00');
INSERT INTO public.schema_migrations VALUES (6, 'passkeys', '2026-10-31T19:15:08+00:00');
INSERT INTO public.schema_migrations VALUES (7, 'door_codes', '2026-10-31T19:15:08+00:00');
INSERT INTO public.schema_migrations VALUES (8, 'posthog_stage', '2026-10-31T19:15:08+00:00');
INSERT INTO public.schema_migrations VALUES (9, 'stay_fee_send', '2026-10-31T19:15:08+00:00');
INSERT INTO public.schema_migrations VALUES (10, 'cleaning', '2026-10-31T19:15:08+00:00');
INSERT INTO public.schema_migrations VALUES (11, 'stay_fee_emails', '2026-10-31T19:15:08+00:00');
INSERT INTO public.schema_migrations VALUES (12, 'web_push', '2026-10-31T19:15:09+00:00');
INSERT INTO public.schema_migrations VALUES (13, 'guest_guide', '2026-10-31T19:15:09+00:00');
INSERT INTO public.schema_migrations VALUES (14, 'guide_token', '2026-10-31T19:15:09+00:00');
INSERT INTO public.schema_migrations VALUES (15, 'ai_usage', '2026-10-31T19:15:09+00:00');
INSERT INTO public.schema_migrations VALUES (16, 'guide_import', '2026-10-31T19:15:09+00:00');
INSERT INTO public.schema_migrations VALUES (17, 'guest_chat', '2026-10-31T19:15:09+00:00');
INSERT INTO public.schema_migrations VALUES (18, 'guide_translation', '2026-10-31T19:15:09+00:00');
INSERT INTO public.schema_migrations VALUES (19, 'guide_fact', '2026-10-31T19:15:09+00:00');
INSERT INTO public.schema_migrations VALUES (20, 'havel_gap', '2026-10-31T19:15:09+00:00');
INSERT INTO public.schema_migrations VALUES (21, 'leon_opt_in', '2026-10-31T19:15:09+00:00');
INSERT INTO public.schema_migrations VALUES (22, 'leon_terms', '2026-10-31T19:15:09+00:00');
INSERT INTO public.schema_migrations VALUES (23, 'billing', '2026-10-31T19:15:09+00:00');
INSERT INTO public.schema_migrations VALUES (24, 'platform_invoice_pdf', '2026-10-31T19:15:09+00:00');
INSERT INTO public.schema_migrations VALUES (25, 'signup_selection', '2026-10-31T19:15:09+00:00');
INSERT INTO public.schema_migrations VALUES (26, 'payment_requests', '2026-10-31T19:15:09+00:00');
INSERT INTO public.schema_migrations VALUES (27, 'stripe_webhook_events', '2026-10-31T19:15:09+00:00');
INSERT INTO public.schema_migrations VALUES (28, 'property_slug', '2026-10-31T19:15:09+00:00');
INSERT INTO public.schema_migrations VALUES (29, 'property_page', '2026-10-31T19:15:09+00:00');
INSERT INTO public.schema_migrations VALUES (30, 'booking_hold', '2026-10-31T19:15:09+00:00');
INSERT INTO public.schema_migrations VALUES (31, 'billing_discount_snapshot', '2026-10-31T19:15:09+00:00');
INSERT INTO public.schema_migrations VALUES (32, 'legal_entity_business_type', '2026-10-31T19:15:09+00:00');
INSERT INTO public.schema_migrations VALUES (33, 'admin_queue_index', '2026-10-31T19:15:09+00:00');
-- +goose Down
-- +goose StatementBegin
DO $$ BEGIN RAISE EXCEPTION 'the baseline is never rolled back'; END $$;
-- +goose StatementEnd
