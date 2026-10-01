"""SQLite access layer plus at-rest encryption for UbyPort passwords."""
from __future__ import annotations

import base64
import hashlib
import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from cryptography.fernet import Fernet, InvalidToken

from . import config

_current_owner_id: ContextVar[Optional[int]] = ContextVar("ubyhost_owner_id", default=None)
# (user_id, username, impersonator_id) of whoever is acting in this request.
_current_actor: ContextVar[Optional[tuple]] = ContextVar("ubyhost_actor", default=None)

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS user_account (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    username             TEXT NOT NULL COLLATE NOCASE UNIQUE,
    display_name         TEXT,
    password_hash        TEXT NOT NULL,
    role                 TEXT NOT NULL DEFAULT 'host' CHECK (role IN ('admin', 'host')),
    active               INTEGER NOT NULL DEFAULT 1,
    must_change_password INTEGER NOT NULL DEFAULT 1,
    session_version      INTEGER NOT NULL DEFAULT 1,
    created_at           TEXT NOT NULL,
    last_login_at        TEXT,
    deletion_due_at      TEXT,
    totp_secret_enc      TEXT,
    totp_enabled         INTEGER NOT NULL DEFAULT 0,
    recovery_codes_hash  TEXT
);

CREATE TABLE IF NOT EXISTS legal_entity (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    seat          TEXT,
    ico           TEXT,
    dic           TEXT,
    contact_email TEXT,
    contact_phone TEXT,
    bank_account  TEXT,
    iban          TEXT,
    bic           TEXT,
    signature_png_enc TEXT,
    signature_name TEXT,
    vat_status               TEXT NOT NULL DEFAULT 'non_payer',
    registry_entry           TEXT,
    invoice_prefix           TEXT,
    invoice_next_number      INTEGER,
    invoice_next_number_year INTEGER,
    invoice_due_days         INTEGER NOT NULL DEFAULT 14,
    owner_user_id INTEGER REFERENCES user_account(id),
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS apartment (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    legal_entity_id       INTEGER REFERENCES legal_entity(id),
    data_controller_entity_id INTEGER REFERENCES legal_entity(id),
    owner_user_id         INTEGER REFERENCES user_account(id),
    internal_name         TEXT NOT NULL,
    city_en               TEXT,
    addr_okres            TEXT,
    addr_obec             TEXT,
    addr_obec_cast        TEXT,
    addr_street           TEXT,
    addr_house_no         TEXT,
    addr_orient_no        TEXT,
    addr_zip              TEXT,
    uby_idub              TEXT,
    uby_mark              TEXT,
    uby_name              TEXT,
    uby_contact           TEXT,
    uby_ws_user           TEXT,
    uby_ws_password_enc   TEXT,
    automation_mode       TEXT NOT NULL DEFAULT 'scheduled',
    submit_after_hours    INTEGER NOT NULL DEFAULT 24,
    permalink_token       TEXT UNIQUE,
    permalink_window_days INTEGER NOT NULL DEFAULT 2,
    permalink_reachback_days INTEGER NOT NULL DEFAULT 365,
    default_purpose       TEXT NOT NULL DEFAULT '10',
    checkin_info          TEXT,
    checkout_info         TEXT,
    guest_message         TEXT,
    notes                 TEXT,
    passport_photo_policy TEXT NOT NULL DEFAULT 'off',
    stay_fee_rate_czk     INTEGER NOT NULL DEFAULT 0,
    stay_fee_cadence      TEXT NOT NULL DEFAULT 'monthly',
    stay_fee_council_account TEXT,
    stay_fee_council_iban TEXT,
    stay_fee_vs           TEXT,
    stay_fee_authority_name TEXT,
    stay_fee_authority_address TEXT,
    stay_fee_authority_contact TEXT,
    stay_fee_payee        TEXT,
    stay_fee_instruction  TEXT,
    active                INTEGER NOT NULL DEFAULT 1,
    created_at            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ical_feed (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    apartment_id  INTEGER NOT NULL REFERENCES apartment(id) ON DELETE CASCADE,
    url           TEXT NOT NULL,
    label         TEXT,
    own_name      TEXT,
    last_sync_at  TEXT,
    last_status   TEXT,
    last_error    TEXT,
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reservation (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    apartment_id            INTEGER NOT NULL REFERENCES apartment(id) ON DELETE CASCADE,
    ical_feed_id            INTEGER REFERENCES ical_feed(id) ON DELETE SET NULL,
    source                  TEXT NOT NULL DEFAULT 'ical',
    uid                     TEXT NOT NULL,
    date_from               TEXT NOT NULL,
    date_to                 TEXT NOT NULL,
    summary                 TEXT,
    reservation_url         TEXT,
    phone_last4             TEXT,
    declared_guests         INTEGER,
    expected_guests_override INTEGER,
    registration_completed_at TEXT,
    guest_email             TEXT,
    host_note               TEXT,
    status                  TEXT NOT NULL DEFAULT 'active',
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL,
    UNIQUE (apartment_id, uid)
);

CREATE TABLE IF NOT EXISTS guest (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    reservation_id INTEGER NOT NULL REFERENCES reservation(id) ON DELETE CASCADE,
    surname        TEXT,
    first_name     TEXT,
    birth_date     TEXT,
    nationality    TEXT,
    doc_number     TEXT,
    visa_number    TEXT,
    doc_number_enc TEXT,
    visa_number_enc TEXT,
    res_street     TEXT,
    res_city       TEXT,
    res_country    TEXT,
    purpose        TEXT,
    note           TEXT,
    stay_from      TEXT,
    stay_to        TEXT,
    is_lead        INTEGER NOT NULL DEFAULT 0,
    signature_png  TEXT,
    signature_png_enc TEXT,
    restricted_at  TEXT,
    restricted_reason TEXT,
    doc_type       TEXT,
    fee_host_decision TEXT,
    fee_host_reason TEXT,
    signed_at      TEXT,
    notice_version TEXT,
    notice_lang    TEXT,
    notice_ack_at  TEXT,
    filled_at      TEXT,
    filled_ip      TEXT,
    entered_by     TEXT NOT NULL DEFAULT 'guest',
    submit_state   TEXT NOT NULL DEFAULT 'pending',
    submitted_at   TEXT,
    -- The latest submission that carried this guest: the current pointer, and
    -- the authority for "which submission filed this guest". Overwritten on
    -- every send, so it cannot say who was in an older batch; that is what
    -- submission.guest_ids is for.
    submission_id  INTEGER REFERENCES submission(id) ON DELETE SET NULL,
    last_errors    TEXT,
    -- Consecutive failed submissions for this guest, counted only on the
    -- unattended sweep. It is the brake that stops a record the register keeps
    -- refusing from being re-offered every sweep forever. Reset to 0 on any
    -- accept or duplicate, and by the host saving the form, so correcting the
    -- data restarts the count. Never consulted for a host-initiated send.
    submit_attempts INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    -- The submission whose response holds this guest's Dorucenka, which is not
    -- always the one above: a duplicate answer proves the register already held
    -- the record, so the receipt sits on the submission that first filed it.
    -- NULL when no confirmation was ever stored for this guest.
    receipt_submission_id INTEGER REFERENCES submission(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS submission (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    apartment_id  INTEGER NOT NULL REFERENCES apartment(id) ON DELETE CASCADE,
    created_at    TEXT NOT NULL,
    finished_at   TEXT,
    mode          TEXT,
    state         TEXT NOT NULL DEFAULT 'running',
    -- The guests that were in the batch when it went out, frozen at send time.
    -- Not derivable from guest.submission_id: a later resend overwrites that
    -- pointer, so deriving would empty an older submission's guest list. The
    -- two answer different questions - this one "who was in this batch", that
    -- one "what filed this guest" - and both are written by submit_batch.
    guest_ids     TEXT,
    header_errors TEXT,
    record_errors TEXT,
    pseudo_stamp  TEXT,
    receipt_pdf   TEXT,
    error_pdf     TEXT,
    endpoint      TEXT,
    request_xml   TEXT,
    response_xml  TEXT,
    error_text    TEXT
);

CREATE TABLE IF NOT EXISTS alert (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    level          TEXT NOT NULL,
    kind           TEXT NOT NULL,
    apartment_id   INTEGER,
    reservation_id INTEGER,
    owner_user_id  INTEGER REFERENCES user_account(id),
    dedupe_key     TEXT,
    message        TEXT NOT NULL,
    detail         TEXT,
    created_at     TEXT NOT NULL,
    resolved_at    TEXT,
    params         TEXT
);

CREATE TABLE IF NOT EXISTS codelist (
    kind       TEXT NOT NULL,
    code       TEXT NOT NULL,
    text_cs    TEXT,
    text_en    TEXT,
    extra      TEXT,
    fetched_at TEXT,
    PRIMARY KEY (kind, code)
);

CREATE TABLE IF NOT EXISTS audit (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    at     TEXT NOT NULL,
    actor  TEXT,
    action TEXT NOT NULL,
    detail TEXT,
    owner_user_id INTEGER REFERENCES user_account(id),
    actor_user_id INTEGER REFERENCES user_account(id) ON DELETE SET NULL,
    impersonator_user_id INTEGER REFERENCES user_account(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_res_apartment_dates ON reservation (apartment_id, date_from);
CREATE INDEX IF NOT EXISTS idx_guest_reservation   ON guest (reservation_id);
-- idx_guest_state is dropped, not created: nothing filters on submit_state in
-- SQL - the send gate reads it in Python - so the index was maintained on every
-- guest write and never read.
DROP INDEX IF EXISTS idx_guest_state;
CREATE INDEX IF NOT EXISTS idx_apartment_owner     ON apartment (owner_user_id);
CREATE INDEX IF NOT EXISTS idx_entity_owner        ON legal_entity (owner_user_id);
CREATE INDEX IF NOT EXISTS idx_alert_owner         ON alert (owner_user_id, resolved_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_alert_dedupe ON alert (dedupe_key) WHERE resolved_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_submission_apartment ON submission (apartment_id);
CREATE INDEX IF NOT EXISTS idx_guest_submission         ON guest (submission_id);
CREATE INDEX IF NOT EXISTS idx_guest_receipt_submission ON guest (receipt_submission_id);
CREATE INDEX IF NOT EXISTS idx_reservation_feed         ON reservation (ical_feed_id);
CREATE INDEX IF NOT EXISTS idx_audit_owner         ON audit (owner_user_id, id);

CREATE TABLE IF NOT EXISTS rate_limit_event (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,
    key   TEXT NOT NULL,
    at    REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rate_limit_scope_key ON rate_limit_event (scope, key, at);

-- A short-lived cross-process lease prevents a scheduler sweep and a host
-- request from putting the same guest on the wire at the same time.
CREATE TABLE IF NOT EXISTS submission_claim (
    guest_id    INTEGER PRIMARY KEY REFERENCES guest(id) ON DELETE CASCADE,
    claim_token TEXT NOT NULL,
    claimed_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS reservation_claim (
    reservation_id          INTEGER PRIMARY KEY REFERENCES reservation(id) ON DELETE CASCADE,
    state                   TEXT NOT NULL DEFAULT 'unclaimed'
        CHECK (state IN ('unclaimed', 'provisional', 'claimed')),
    email                   TEXT,
    email_masked            TEXT,
    lang                    TEXT,
    token_hash              TEXT,
    token_version           INTEGER NOT NULL DEFAULT 0,
    provisional_until       TEXT,
    claimed_at              TEXT,
    guest_access_locked_at  TEXT,
    guest_access_reopened_at TEXT,
    declared_guests         INTEGER,
    completion_notified_at  TEXT,
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS email_outbox (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    idempotency_key  TEXT NOT NULL UNIQUE,
    kind             TEXT NOT NULL,
    reservation_id   INTEGER REFERENCES reservation(id) ON DELETE SET NULL,
    apartment_id     INTEGER,
    owner_user_id    INTEGER,
    to_email         TEXT,
    cc_email         TEXT,
    subject          TEXT,
    payload          TEXT,
    state            TEXT NOT NULL DEFAULT 'queued',
    attempts         INTEGER NOT NULL DEFAULT 0,
    next_attempt_at  TEXT,
    provider_id      TEXT,
    last_error       TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL,
    sent_at          TEXT
);
CREATE INDEX IF NOT EXISTS idx_outbox_state_attempt ON email_outbox (state, next_attempt_at);

CREATE TABLE IF NOT EXISTS console_mail_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    outbox_id  INTEGER,
    to_email   TEXT,
    cc_email   TEXT,
    subject    TEXT,
    body_text  TEXT,
    body_html  TEXT,
    created_at TEXT NOT NULL
);

-- --- invoices (docs/plans/PLAN_GUEST_INVOICE_FEATURE.md; host-only Phase 1) ---

CREATE TABLE IF NOT EXISTS invoice_sequence (
    legal_entity_id INTEGER NOT NULL REFERENCES legal_entity(id),
    year            INTEGER NOT NULL,
    last_no         INTEGER NOT NULL,
    PRIMARY KEY (legal_entity_id, year)
);

CREATE TABLE IF NOT EXISTS invoice (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    legal_entity_id      INTEGER NOT NULL REFERENCES legal_entity(id),
    apartment_id         INTEGER REFERENCES apartment(id),
    reservation_id       INTEGER REFERENCES reservation(id) ON DELETE SET NULL,
    kind                 TEXT NOT NULL CHECK (kind IN ('invoice','storno','corrective')),
    corrects_invoice_id  INTEGER REFERENCES invoice(id),
    correction_reason    TEXT,
    correction_date      TEXT,
    seq_year             INTEGER NOT NULL,
    seq_no               INTEGER NOT NULL,
    number               TEXT NOT NULL,
    vs                   TEXT NOT NULL,
    lang                 TEXT NOT NULL CHECK (lang IN ('cs','en')),
    currency             TEXT NOT NULL DEFAULT 'CZK' CHECK (currency = 'CZK'),
    vat_status           TEXT NOT NULL,
    issue_date           TEXT NOT NULL,
    duzp                 TEXT,
    due_date             TEXT,
    paid_on              TEXT,
    paid_via             TEXT,
    seller_name TEXT NOT NULL, seller_seat TEXT NOT NULL, seller_ico TEXT, seller_dic TEXT,
    seller_registry TEXT, seller_bank_account TEXT, seller_iban TEXT, seller_bic TEXT,
    seller_email TEXT, seller_phone TEXT,
    buyer_name TEXT NOT NULL, buyer_street TEXT, buyer_city TEXT, buyer_zip TEXT,
    buyer_country TEXT, buyer_ico TEXT, buyer_dic TEXT, buyer_email TEXT,
    stay_from            TEXT, stay_to TEXT, stay_label TEXT,
    total_base_haler     INTEGER,
    total_vat_haler      INTEGER,
    total_haler          INTEGER NOT NULL,
    pdf_blob             BLOB,
    pdf_sha256           TEXT,
    issued_at            TEXT,
    issued_by            INTEGER REFERENCES user_account(id),
    marked_paid_at       TEXT,
    emailed_at           TEXT,
    owner_user_id        INTEGER REFERENCES user_account(id),
    created_at           TEXT NOT NULL,
    UNIQUE (legal_entity_id, number),
    UNIQUE (legal_entity_id, seq_year, seq_no)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_invoice_one_correction
    ON invoice (corrects_invoice_id) WHERE corrects_invoice_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_invoice_reservation ON invoice (reservation_id);
CREATE INDEX IF NOT EXISTS idx_invoice_owner ON invoice (owner_user_id, issue_date);

CREATE TABLE IF NOT EXISTS invoice_item (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id   INTEGER NOT NULL REFERENCES invoice(id),
    position     INTEGER NOT NULL,
    kind         TEXT NOT NULL CHECK (kind IN ('accommodation','stay_fee','other')),
    -- 'stay_fee' stays in the CHECK only so the schema never needs a table
    -- rebuild; the feature was reverted and nothing writes the value.
    description  TEXT NOT NULL,
    quantity     INTEGER NOT NULL DEFAULT 1,
    unit         TEXT NOT NULL DEFAULT '',
    vat_rate     INTEGER,
    base_haler   INTEGER,
    vat_haler    INTEGER,
    gross_haler  INTEGER NOT NULL,
    UNIQUE (invoice_id, position)
);

CREATE TRIGGER IF NOT EXISTS invoice_issued_guard
BEFORE UPDATE OF legal_entity_id, apartment_id, kind, corrects_invoice_id, correction_reason,
    correction_date, seq_year, seq_no, number, vs, lang, currency, vat_status, issue_date, duzp,
    due_date, paid_on, paid_via, seller_name, seller_seat, seller_ico, seller_dic, seller_registry,
    seller_bank_account, seller_iban, seller_bic, seller_email, seller_phone, buyer_name,
    buyer_street, buyer_city, buyer_zip, buyer_country, buyer_ico, buyer_dic, buyer_email,
    stay_from, stay_to, stay_label, total_base_haler, total_vat_haler, total_haler,
    pdf_blob, pdf_sha256, issued_at, issued_by
ON invoice
WHEN OLD.issued_at IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'invoice is issued and immutable');
END;

CREATE TRIGGER IF NOT EXISTS invoice_delete_guard
BEFORE DELETE ON invoice
WHEN OLD.issued_at IS NOT NULL
 AND COALESCE((SELECT value FROM settings WHERE key = 'invoice_purge_unlock'), '') <> '1'
BEGIN
    SELECT RAISE(ABORT, 'invoice is issued and immutable');
END;

CREATE TRIGGER IF NOT EXISTS invoice_item_insert_guard
BEFORE INSERT ON invoice_item
WHEN (SELECT issued_at FROM invoice WHERE id = NEW.invoice_id) IS NOT NULL
BEGIN SELECT RAISE(ABORT, 'invoice is issued and immutable'); END;

CREATE TRIGGER IF NOT EXISTS invoice_item_update_guard
BEFORE UPDATE ON invoice_item
WHEN (SELECT issued_at FROM invoice WHERE id = OLD.invoice_id) IS NOT NULL
BEGIN SELECT RAISE(ABORT, 'invoice is issued and immutable'); END;

CREATE TRIGGER IF NOT EXISTS invoice_item_delete_guard
BEFORE DELETE ON invoice_item
WHEN (SELECT issued_at FROM invoice WHERE id = OLD.invoice_id) IS NOT NULL
 AND COALESCE((SELECT value FROM settings WHERE key = 'invoice_purge_unlock'), '') <> '1'
BEGIN SELECT RAISE(ABORT, 'invoice is issued and immutable'); END;

-- Sealed stay-fee period: encrypted PDF/CSV snapshots after host finalization.
CREATE TABLE IF NOT EXISTS stay_fee_filing (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    apartment_id         INTEGER NOT NULL REFERENCES apartment(id),
    period_key           TEXT NOT NULL,
    version              INTEGER NOT NULL DEFAULT 1,
    cadence              TEXT NOT NULL,
    rate_czk             INTEGER NOT NULL,
    liable_days          INTEGER NOT NULL,
    exempt_days          INTEGER NOT NULL,
    total_due_czk        INTEGER NOT NULL,
    total_collected_czk  INTEGER NOT NULL,
    pdf_enc              BLOB,
    csv_enc              BLOB,
    payload_enc          TEXT,
    created_at           TEXT NOT NULL,
    superseded_at        TEXT,
    UNIQUE (apartment_id, period_key, version)
);
CREATE INDEX IF NOT EXISTS idx_stay_fee_filing_lookup
    ON stay_fee_filing (apartment_id, period_key);

-- Evidence that a host accepted the Terms of Service, DPA and Privacy Policy,
-- per document version (BE-1). One row per account and document version; a
-- version bump makes that document pending again without touching old rows.
-- Append-only: rows are never updated or deleted while the account lives.
CREATE TABLE IF NOT EXISTS legal_acceptance (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_account_id INTEGER NOT NULL REFERENCES user_account(id),
    document        TEXT NOT NULL CHECK (document IN ('terms','privacy','dpa')),
    version         TEXT NOT NULL,
    accepted_at     TEXT NOT NULL,
    method          TEXT NOT NULL CHECK (method IN ('clickwrap','login_notice','backfill')),
    ip              TEXT,
    user_agent      TEXT,
    UNIQUE (user_account_id, document, version)
);
CREATE INDEX IF NOT EXISTS idx_acceptance_user ON legal_acceptance (user_account_id, document);

-- Security incident register (BE-13 / LD-5). Platform-admin only; the row is the
-- evidence Art 33(5) asks for. `affected_owner_ids` is a JSON array of ids.
CREATE TABLE IF NOT EXISTS security_incident (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    detected_at             TEXT NOT NULL,
    reported_by             TEXT,
    summary                 TEXT NOT NULL,
    data_categories         TEXT,
    affected_owner_ids      TEXT,
    approx_subjects         INTEGER,
    risk_level              TEXT CHECK (risk_level IN ('none','low','high')),
    contained_at            TEXT,
    controllers_notified_at TEXT,
    authority_notified_at   TEXT,
    subjects_notified_at    TEXT,
    closed_at               TEXT,
    notes                   TEXT,
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL
);

-- Data-subject request register (BE-8): one row per access/erasure/etc. request
-- a host records, with the one-month deadline Art 12(3) sets.
CREATE TABLE IF NOT EXISTS data_subject_request (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_user_id       INTEGER REFERENCES user_account(id),
    received_at         TEXT NOT NULL,
    due_at              TEXT NOT NULL,
    channel             TEXT NOT NULL CHECK (channel IN ('email','post','in_person','support','other')),
    request_type        TEXT NOT NULL CHECK (request_type IN
                          ('access','rectification','erasure','restriction','portability','objection','other')),
    subject_kind        TEXT NOT NULL CHECK (subject_kind IN ('guest','host_user','other')),
    guest_id            INTEGER REFERENCES guest(id) ON DELETE SET NULL,
    reservation_id      INTEGER REFERENCES reservation(id) ON DELETE SET NULL,
    identity_checked_at TEXT,
    status              TEXT NOT NULL DEFAULT 'open'
                          CHECK (status IN ('open','extended','fulfilled','refused','withdrawn')),
    extended_until      TEXT,
    closed_at           TEXT,
    outcome_note        TEXT,
    handled_by          INTEGER REFERENCES user_account(id),
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dsr_owner_status ON data_subject_request (owner_user_id, status, due_at);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(config.DB_PATH), timeout=30, isolation_level=None)
    try:
        config.DB_PATH.chmod(0o600)
    except OSError:
        pass
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    # Overwrite freed pages instead of leaving the old bytes behind. Without
    # this, blanking a plaintext document number left it readable in the file
    # until something happened to reuse the page.
    conn.execute("PRAGMA secure_delete = ON")
    return conn


@contextmanager
def cursor():
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute("BEGIN")
        try:
            yield cur
            cur.execute("COMMIT")
        except Exception:
            cur.execute("ROLLBACK")
            raise
    finally:
        conn.close()


@contextmanager
def immediate():
    """Like cursor(), but takes the write lock before the first read."""
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        try:
            yield cur
            cur.execute("COMMIT")
        except Exception:
            cur.execute("ROLLBACK")
            raise
    finally:
        conn.close()


# Columns added after the first release. CREATE TABLE IF NOT EXISTS leaves an
# existing database untouched, so every later column has to be added by hand.
ADDED_COLUMNS = (
    ("user_account", "totp_secret_enc", "TEXT"),
    ("user_account", "totp_enabled", "INTEGER NOT NULL DEFAULT 0"),
    ("user_account", "recovery_codes_hash", "TEXT"),
    ("user_account", "totp_last_step", "INTEGER"),
    ("legal_entity", "contact_email", "TEXT"),
    ("legal_entity", "contact_phone", "TEXT"),
    ("legal_entity", "owner_user_id", "INTEGER REFERENCES user_account(id)"),
    ("legal_entity", "archived_at", "TEXT"),
    ("apartment", "owner_user_id", "INTEGER REFERENCES user_account(id)"),
    ("apartment", "data_controller_entity_id", "INTEGER REFERENCES legal_entity(id)"),
    ("apartment", "permalink_pin", "TEXT"),
    ("apartment", "archived_at", "TEXT"),
    ("reservation", "archived_at", "TEXT"),
    ("guest", "archived_at", "TEXT"),
    ("guest", "passport_photo_at", "TEXT"),
    ("guest", "identity_verified_at", "TEXT"),
    ("guest", "identity_verified_by", "INTEGER"),
    ("alert", "user_dismissed", "INTEGER NOT NULL DEFAULT 0"),
    ("alert", "owner_user_id", "INTEGER REFERENCES user_account(id)"),
    ("audit", "owner_user_id", "INTEGER REFERENCES user_account(id)"),
    ("apartment", "passport_photo_policy", "TEXT NOT NULL DEFAULT 'off'"),
    ("apartment", "guest_message", "TEXT"),
    ("reservation_claim", "guest_access_reopened_at", "TEXT"),
    ("reservation", "registration_completed_at", "TEXT"),
    ("guest", "doc_number_enc", "TEXT"),
    ("guest", "visa_number_enc", "TEXT"),
    ("apartment", "permalink_reachback_days", "INTEGER NOT NULL DEFAULT 365"),
    ("guest", "receipt_submission_id", "INTEGER REFERENCES submission(id) ON DELETE SET NULL"),
    ("console_mail_log", "body_html", "TEXT"),
    ("guest", "submit_attempts", "INTEGER NOT NULL DEFAULT 0"),
    # The values an alert's card interpolates, as JSON, so the card can be
    # rebuilt in the host's language at render time instead of storing prose.
    ("alert", "params", "TEXT"),
    ("legal_entity", "bank_account", "TEXT"),
    ("legal_entity", "iban", "TEXT"),
    ("legal_entity", "bic", "TEXT"),
    # Invoices (docs/plans/PLAN_GUEST_INVOICE_FEATURE.md)
    ("legal_entity", "vat_status", "TEXT NOT NULL DEFAULT 'non_payer'"),
    ("legal_entity", "registry_entry", "TEXT"),
    ("legal_entity", "invoice_prefix", "TEXT"),
    ("legal_entity", "invoice_next_number", "INTEGER"),
    ("legal_entity", "invoice_next_number_year", "INTEGER"),
    ("legal_entity", "invoice_due_days", "INTEGER NOT NULL DEFAULT 14"),
    # BE-5: proof that the guest saw and acknowledged the privacy notice.
    ("guest", "notice_version", "TEXT"),
    ("guest", "notice_lang", "TEXT"),
    ("guest", "notice_ack_at", "TEXT"),
    # BE-6: who actually acted, and whether they were previewing a workspace.
    # SET NULL keeps the audit row (and its actor name) if the account is ever
    # deleted; the id is history, not a live reference.
    ("audit", "actor_user_id", "INTEGER REFERENCES user_account(id) ON DELETE SET NULL"),
    ("audit", "impersonator_user_id", "INTEGER REFERENCES user_account(id) ON DELETE SET NULL"),
    # BE-12: drawn signatures encrypted at rest, like the document numbers.
    ("guest", "signature_png_enc", "TEXT"),
    # BE-9: processing restriction (Art 18).
    ("guest", "restricted_at", "TEXT"),
    ("guest", "restricted_reason", "TEXT"),
    # BE-10: workspace termination.
    ("user_account", "deletion_due_at", "TEXT"),
    # Stay-fee remittance, host only
    # (docs/plans/stay-fee-remittance/PLAN_STAY_FEE_REMITTANCE.md).
    ("apartment", "stay_fee_rate_czk", "INTEGER NOT NULL DEFAULT 0"),
    ("apartment", "stay_fee_cadence", "TEXT NOT NULL DEFAULT 'monthly'"),
    ("apartment", "stay_fee_council_account", "TEXT"),
    ("apartment", "stay_fee_council_iban", "TEXT"),
    ("apartment", "stay_fee_vs", "TEXT"),
    ("apartment", "stay_fee_authority_name", "TEXT"),
    ("apartment", "stay_fee_authority_address", "TEXT"),
    ("apartment", "stay_fee_authority_contact", "TEXT"),
    ("apartment", "stay_fee_payee", "TEXT"),
    ("apartment", "stay_fee_instruction", "TEXT"),
    ("legal_entity", "signature_png_enc", "TEXT"),
    ("legal_entity", "signature_name", "TEXT"),
    ("guest", "doc_type", "TEXT"),
    ("guest", "fee_host_decision", "TEXT"),
    ("guest", "fee_host_reason", "TEXT"),
    ("apartment", "stay_fee_scope_rule", "TEXT"),
    ("apartment", "stay_fee_scope_reference", "TEXT"),
    ("guest", "fee_host_reason_enc", "TEXT"),
    ("guest", "fee_host_reason_reference", "TEXT"),
)

# The reverted 26 Sep 2026 stay-fee build (AR-55) used some of the same column
# names. A database that ran it may still hold guest-typed claims (possibly
# disability data) and a non-zero rate that would switch the calculator on.
# Everything is cleared once, the first time this release starts.
_REVERTED_STAY_FEE_COLUMNS = (
    ("guest", "fee_claim"),
    ("reservation", "stay_fee_rate_czk"),
    ("reservation", "stay_fee_paid_at"),
    ("reservation", "stay_fee_paid_amount_czk"),
    ("apartment", "stay_fee_payment_link"),
)
_STAY_FEE_RESET_KEY = "stay_fee_remittance_reset_done"


def _reset_reverted_stay_fee(conn: sqlite3.Connection) -> None:
    if conn.execute(
        "SELECT 1 FROM settings WHERE key = ?", (_STAY_FEE_RESET_KEY,)
    ).fetchone():
        return
    conn.execute("UPDATE apartment SET stay_fee_rate_czk = 0")
    conn.execute(
        "UPDATE guest SET doc_type = NULL, fee_host_decision = NULL, fee_host_reason = NULL"
    )
    for table, column in _REVERTED_STAY_FEE_COLUMNS:
        present = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column in present:
            conn.execute(f"UPDATE {table} SET {column} = NULL")
    conn.execute("INSERT INTO settings (key, value) VALUES (?, '1')", (_STAY_FEE_RESET_KEY,))


def _add_missing_columns(conn: sqlite3.Connection) -> None:
    """Bring a database created by an older release up to the current columns.

    One ``PRAGMA table_info`` per table, not one per column: this used to run on
    every connection and every query opens one, so the schema check was most of
    the statements the process executed. It runs at startup now, from
    ``init_db``.
    """
    columns: Dict[str, set] = {}
    for table, column, decl in ADDED_COLUMNS:
        if table not in columns:
            columns[table] = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if columns[table] and column not in columns[table]:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
            columns[table].add(column)


def init_db() -> None:
    # The data directory has to exist before sqlite opens the database inside
    # it, and creating it is no longer an import-time side effect of config.
    config.ensure_data_dir()
    conn = connect()
    try:
        # Migrate before the schema, because SCHEMA also creates indexes over
        # columns a legacy database is missing and CREATE TABLE IF NOT EXISTS
        # will not add them. Migrate again after it, because SCHEMA's own table
        # definitions do not carry every later column - a fresh database gets
        # those from ADDED_COLUMNS. Both passes are one PRAGMA per table, once.
        _add_missing_columns(conn)
        conn.executescript(SCHEMA)
        _add_missing_columns(conn)
        _reset_reverted_stay_fee(conn)
    finally:
        conn.close()


# --- small query helpers -------------------------------------------------

class _HydratedRow(dict):
    """A row that still answers to both a column name and a position.

    Decrypted values are merged into the row so templates, exports and the
    police payload keep reading ``row["doc_number"]`` unchanged. Indexing and
    iteration follow ``sqlite3.Row`` rather than ``dict``: an integer or slice
    yields values, and iterating the row yields values in column order, because
    that is what a caller holding a plain row would have got.
    """

    __slots__ = ("_order",)

    def __init__(self, mapping: Dict[str, Any], order: Iterable[str]) -> None:
        super().__init__(mapping)
        self._order = tuple(order)

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, (int, slice)):
            return tuple(dict.__getitem__(self, name) for name in self._order)[key]
        return dict.__getitem__(self, key)

    def __iter__(self):
        return iter(dict.__getitem__(self, name) for name in self._order)


def _hydrate(row: sqlite3.Row) -> Any:
    """Merge decrypted guest fields into a row, leaving other rows untouched.

    A row only qualifies when it actually selected one of the encrypted
    columns, so the cost is paid by guest reads and nothing else.
    """
    keys = row.keys()
    present = [name for name, enc in ENCRYPTED_GUEST_COLUMNS.items() if enc in keys]
    if not present:
        return row
    values: Dict[str, Any] = dict(row)
    for name in present:
        values[name] = decrypt_field(
            row[ENCRYPTED_GUEST_COLUMNS[name]], row[name] if name in keys else None
        )
    return _HydratedRow(values, keys)


def _guest_write_values(values: Dict[str, Any]) -> Dict[str, Any]:
    """Redirect a guest field to its encrypted column and blank the plaintext.

    Blanking on write means an existing row loses the copy the backfill has not
    reached yet the first time anything saves it again.
    """
    out: Dict[str, Any] = {}
    for key, value in values.items():
        enc = ENCRYPTED_GUEST_COLUMNS.get(key)
        if enc is None:
            out[key] = value
        else:
            out[enc] = encrypt_field(value)
            out[key] = None
    return out


def query(sql: str, params: Iterable[Any] = ()) -> List[sqlite3.Row]:
    conn = connect()
    try:
        return [_hydrate(row) for row in conn.execute(sql, tuple(params)).fetchall()]
    finally:
        conn.close()


def query_one(sql: str, params: Iterable[Any] = ()) -> Optional[sqlite3.Row]:
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params: Iterable[Any] = ()) -> int:
    conn = connect()
    try:
        cur = conn.execute(sql, tuple(params))
        return cur.lastrowid
    finally:
        conn.close()


def insert(table: str, values: Dict[str, Any]) -> int:
    if table == "guest":
        values = _guest_write_values(values)
    cols = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    return execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", list(values.values()))


def update(table: str, row_id: int, values: Dict[str, Any]) -> None:
    if not values:
        return
    if table == "guest":
        values = _guest_write_values(values)
    sets = ", ".join(f"{k} = ?" for k in values)
    execute(f"UPDATE {table} SET {sets} WHERE id = ?", list(values.values()) + [row_id])


def update_if(
    table: str,
    row_id: int,
    values: Dict[str, Any],
    expected: Dict[str, Any],
    extra_where: str = "",
    extra_params: Iterable[Any] = (),
) -> bool:
    """UPDATE the row only if it still holds ``expected``; True when it did.

    Compare-and-set for rows a background job may change between a request's
    read and its write. ``expected`` values compare with IS, so None matches
    NULL. ``extra_where`` is a trusted SQL fragment (never user input).
    Guest values are encrypted exactly as in update().
    """
    if not values:
        return False
    if table == "guest":
        values = _guest_write_values(values)
    sets = ", ".join(f"{k} = ?" for k in values)
    clauses = ["id = ?"] + [f"{k} IS ?" for k in expected]
    if extra_where:
        clauses.append(extra_where)
    sql = f"UPDATE {table} SET {sets} WHERE " + " AND ".join(clauses)
    params = list(values.values()) + [row_id] + list(expected.values()) + list(extra_params)
    conn = connect()
    try:
        return conn.execute(sql, params).rowcount == 1
    finally:
        conn.close()


def update_in(cur, table: str, row_id: int, values: Dict[str, Any]) -> None:
    """update(), but on a cursor from cursor()/immediate(), inside its transaction."""
    if not values:
        return
    if table == "guest":
        values = _guest_write_values(values)
    sets = ", ".join(f"{k} = ?" for k in values)
    cur.execute(f"UPDATE {table} SET {sets} WHERE id = ?", list(values.values()) + [row_id])


def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    row = query_one("SELECT value FROM settings WHERE key = ?", (key,))
    return row["value"] if row else default


def set_setting(key: str, value: Optional[str]) -> None:
    execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def set_current_owner(owner_user_id: Optional[int]) -> None:
    _current_owner_id.set(owner_user_id)


def set_current_actor(
    user_id: Optional[int], username: str = "host", impersonating: bool = False
) -> None:
    """Remember who is acting, for audit rows written later in the request.

    ``impersonator_user_id`` is the acting user's own id only while they are
    inside another workspace, so an ordinary action records ``NULL`` there.
    """
    if user_id is None:
        _current_actor.set(None)
        return
    _current_actor.set(
        (int(user_id), username, int(user_id) if impersonating else None)
    )


def audit(
    action: str, detail: str = "", actor: str = "host", owner_user_id: Optional[int] = None
) -> None:
    if owner_user_id is None:
        owner_user_id = _current_owner_id.get()
    actor_user_id = None
    impersonator_user_id = None
    current = _current_actor.get()
    if current:
        actor_user_id, username, impersonator_user_id = current
        # A caller that named no actor gets the signed-in username instead of
        # the bare "host" placeholder.
        if actor == "host":
            actor = username
    insert(
        "audit",
        {
            "at": utcnow(),
            "actor": actor,
            "action": action,
            "detail": detail,
            "owner_user_id": owner_user_id,
            "actor_user_id": actor_user_id,
            "impersonator_user_id": impersonator_user_id,
        },
    )


# --- secret handling -----------------------------------------------------

def _fernet() -> Fernet:
    digest = hashlib.sha256(config.secret_key().encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plain: str) -> str:
    if not plain:
        return ""
    return _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_secret(token: Optional[str]) -> str:
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        # Wrong or rotated SECRET_KEY: treat as missing so the UI prompts again.
        return ""


# --- guest travel-document fields ----------------------------------------
#
# A guest's passport and visa numbers are the two fields the police register
# actually turns on, and the audit found them sitting in the clear in every
# copy of the database file. They are now stored Fernet-encrypted in the *_enc
# columns. The plaintext columns are kept only as a read fallback for rows a
# backfill has not reached yet; nothing writes them any more.

ENCRYPTED_GUEST_COLUMNS = {
    "doc_number": "doc_number_enc",
    "visa_number": "visa_number_enc",
    # BE-12: the drawn signature is as sensitive as the document number.
    "signature_png": "signature_png_enc",
}


def encrypt_blob(data: bytes) -> bytes:
    """Encrypt a file body (used for passport images/PDFs)."""
    return _fernet().encrypt(data)


def decrypt_blob(token: bytes) -> bytes:
    """Decrypt a file body. Raises like ``decrypt_field`` when the key is wrong."""
    try:
        return _fernet().decrypt(token)
    except (InvalidToken, ValueError) as exc:
        raise DecryptionError("stored attachment could not be decrypted") from exc


class DecryptionError(RuntimeError):
    """A stored guest field could not be decrypted with the current key."""


def encrypt_field(plain: Optional[str]) -> Optional[str]:
    """Encrypt one guest field for storage. An absent value stays absent."""
    if not plain:
        return None
    return encrypt_secret(plain)


def decrypt_field(token: Optional[str], fallback: Optional[str] = None) -> Optional[str]:
    """Decrypt one guest field, falling back to its plaintext column.

    Deliberately stricter than decrypt_secret: a value that will not decrypt
    raises instead of becoming empty. An empty cDocN filed with the police is
    worse than an error the host can see and act on.

    With no ciphertext the fallback is returned verbatim, ``None`` included, so
    a column that was never filled in still reads the way it always did.
    """
    if not token:
        return fallback
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise DecryptionError("stored guest document field could not be decrypted") from exc
