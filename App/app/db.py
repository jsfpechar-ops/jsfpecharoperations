"""SQLite access layer plus at-rest encryption for UbyPort passwords."""
from __future__ import annotations

import base64
import hashlib
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from cryptography.fernet import Fernet, InvalidToken

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS legal_entity (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    seat          TEXT,
    ico           TEXT,
    dic           TEXT,
    contact_email TEXT,
    contact_phone TEXT,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS apartment (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    legal_entity_id       INTEGER REFERENCES legal_entity(id),
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
    permalink_window_days INTEGER NOT NULL DEFAULT 3,
    default_purpose       TEXT NOT NULL DEFAULT '10',
    checkin_info          TEXT,
    checkout_info         TEXT,
    notes                 TEXT,
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
    res_street     TEXT,
    res_city       TEXT,
    res_country    TEXT,
    purpose        TEXT,
    note           TEXT,
    stay_from      TEXT,
    stay_to        TEXT,
    is_lead        INTEGER NOT NULL DEFAULT 0,
    signature_png  TEXT,
    signed_at      TEXT,
    filled_at      TEXT,
    filled_ip      TEXT,
    entered_by     TEXT NOT NULL DEFAULT 'guest',
    submit_state   TEXT NOT NULL DEFAULT 'pending',
    submitted_at   TEXT,
    submission_id  INTEGER REFERENCES submission(id) ON DELETE SET NULL,
    last_errors    TEXT,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS submission (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    apartment_id  INTEGER NOT NULL REFERENCES apartment(id) ON DELETE CASCADE,
    created_at    TEXT NOT NULL,
    finished_at   TEXT,
    mode          TEXT,
    state         TEXT NOT NULL DEFAULT 'running',
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
    dedupe_key     TEXT,
    message        TEXT NOT NULL,
    detail         TEXT,
    created_at     TEXT NOT NULL,
    resolved_at    TEXT
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
    detail TEXT
);

CREATE INDEX IF NOT EXISTS idx_res_apartment_dates ON reservation (apartment_id, date_from);
CREATE INDEX IF NOT EXISTS idx_guest_reservation   ON guest (reservation_id);
CREATE INDEX IF NOT EXISTS idx_guest_state         ON guest (submit_state);
CREATE UNIQUE INDEX IF NOT EXISTS idx_alert_dedupe ON alert (dedupe_key) WHERE resolved_at IS NULL;
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(config.DB_PATH), timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
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


# Columns added after the first release. CREATE TABLE IF NOT EXISTS leaves an
# existing database untouched, so every later column has to be added by hand.
ADDED_COLUMNS = (
    ("legal_entity", "contact_email", "TEXT"),
    ("legal_entity", "contact_phone", "TEXT"),
    ("apartment", "permalink_pin", "TEXT"),
    ("apartment", "archived_at", "TEXT"),
    ("reservation", "archived_at", "TEXT"),
    ("guest", "archived_at", "TEXT"),
)


def _add_missing_columns(conn: sqlite3.Connection) -> None:
    for table, column, decl in ADDED_COLUMNS:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if existing and column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def init_db() -> None:
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        _add_missing_columns(conn)
    finally:
        conn.close()


# --- small query helpers -------------------------------------------------

def query(sql: str, params: Iterable[Any] = ()) -> List[sqlite3.Row]:
    conn = connect()
    try:
        return conn.execute(sql, tuple(params)).fetchall()
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
    cols = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    return execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", list(values.values()))


def update(table: str, row_id: int, values: Dict[str, Any]) -> None:
    if not values:
        return
    sets = ", ".join(f"{k} = ?" for k in values)
    execute(f"UPDATE {table} SET {sets} WHERE id = ?", list(values.values()) + [row_id])


def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    row = query_one("SELECT value FROM settings WHERE key = ?", (key,))
    return row["value"] if row else default


def set_setting(key: str, value: Optional[str]) -> None:
    execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def audit(action: str, detail: str = "", actor: str = "host") -> None:
    insert("audit", {"at": utcnow(), "actor": actor, "action": action, "detail": detail})


# --- secret handling -----------------------------------------------------

def _fernet() -> Fernet:
    digest = hashlib.sha256(config.SECRET_KEY.encode("utf-8")).digest()
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
