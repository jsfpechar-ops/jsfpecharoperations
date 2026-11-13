"""Write go/internal/photosweep/testdata/photo_sweep_golden.json from the real Python.

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    .venv/bin/python scripts/photo_sweep_golden.py

It seeds a throwaway SQLite database with the rows in SEED and a throwaway data
directory with the files in FILES, freezes the clock at NOW, and runs the five
steps of scheduler._job_photo_sweep in the job's order: passport_photos.purge_stale,
guide_photos.purge_orphans, reporting.purge_submission_payloads,
guest_draft.purge and signup.purge. It records each step's return value, the
files left on disk, the rows in SNAPSHOT and every audit row. The Go test
go/internal/photosweep/sweep_test.go seeds PostgreSQL and a temp directory from
the same file, runs photosweep.run and compares. App/tests/test_go_photo_sweep_golden.py
fails when this file is stale.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import types
from contextlib import ExitStack
from datetime import date, datetime
from pathlib import Path
from unittest import mock

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "photosweep" / "testdata" / "photo_sweep_golden.json"

# The frozen clock: datetime.now() everywhere, date.today() in passport_photos
# (the server-local date) and time.time() in guide_photos.
NOW = "2026-11-13T10:00:00+00:00"
TODAY = "2026-11-13"
S = "2026-09-01T00:00:00+00:00"  # created_at / updated_at of every seeded row

SEED = [
    {
        "table": "user_account",
        "columns": ["id", "username", "password_hash", "role", "created_at", "active",
                    "email_verified_at", "signup_at"],
        "rows": [
            [1, "owner@example.test", "x", "host", S, 1, S, None],
            # 2 unconfirmed sign-up older than 7 days: deleted with its rows.
            [2, "stale@example.test", "x", "host", S, 0, None, "2026-11-01T00:00:00+00:00"],
            # 3 unconfirmed but recent, 6 old but verified: both stay.
            [3, "recent@example.test", "x", "host", S, 0, None, "2026-11-10T00:00:00+00:00"],
            # 4 verified before the Meta window: its pending event expires.
            [4, "meta-old@example.test", "x", "host", S, 1, "2026-11-01T00:00:00+00:00",
             "2026-11-01T00:00:00+00:00"],
            # 5 verified inside the window: its pending event stays.
            [5, "meta-new@example.test", "x", "host", S, 1, "2026-11-12T00:00:00+00:00",
             "2026-11-12T00:00:00+00:00"],
            [6, "verified@example.test", "x", "host", S, 0, "2026-10-02T00:00:00+00:00",
             "2026-10-01T00:00:00+00:00"],
            # one ad_click per account and platform: more plain accounts
            [7, "seven@example.test", "x", "host", S, 1, S, None],
            [8, "eight@example.test", "x", "host", S, 1, S, None],
            [9, "nine@example.test", "x", "host", S, 1, S, None],
        ],
    },
    {
        "table": "apartment",
        "columns": ["id", "internal_name", "owner_user_id", "created_at"],
        "rows": [[10, "Golden flat", 1, S]],
    },
    {
        "table": "reservation",
        "columns": ["id", "apartment_id", "uid", "date_from", "date_to", "status",
                    "created_at", "updated_at"],
        "rows": [
            [100, 10, "golden-100", "2026-11-01", "2026-11-04", "active", S, S],
            [101, 10, "golden-101", "2026-11-10", "2026-11-15", "active", S, S],
            [102, 10, "golden-102", "2026-11-12", "2026-11-20", "cancelled", S, S],
            # +02:00 is 2026-11-06 in UTC: on the check-in cutoff day.
            [103, 10, "golden-103", "2026-11-07T00:30:00+02:00", "2026-11-20", "active", S, S],
        ],
    },
    {
        "table": "guest",
        "columns": ["id", "reservation_id", "stay_from", "passport_photo_at",
                    "identity_verified_at", "created_at", "updated_at"],
        "rows": [
            # 1001 stay began 2026-11-01: photo deleted, mark cleared.
            [1001, 100, None, "2026-11-01T09:00:00+00:00", None, S, S],
            # 1002 recent stay, recent upload: kept.
            [1002, 101, None, "2026-11-12T09:00:00+00:00", None, S, S],
            # 1003 verified, empty mark: photo deleted, empty mark left as it is.
            [1003, 101, None, "", "2026-11-11T09:00:00+00:00", S, S],
            # 1004 the guest's own stay_from is old: both files go, counted once.
            [1004, 101, "2026-11-05", "2026-11-10T09:00:00+00:00", None, S, S],
            # 1005 stay_from not a date falls back to the booking; upload on the
            # 30-day cutoff day: deleted.
            [1005, 101, "garbage", "2026-10-14T23:00:00+00:00", None, S, S],
            # 1006 upload is 2026-10-14 in UTC, no file: mark cleared, not counted.
            [1006, 101, None, "2026-10-15T00:30:00+02:00", None, S, S],
            # 1007 booking start with an offset: on the cutoff day, deleted.
            [1007, 103, None, "2026-11-12T09:00:00+00:00", None, S, S],
            # 1008 upload one day after the cutoff, recent stay: kept.
            [1008, 102, None, "2026-10-15T09:00:00+00:00", None, S, S],
        ],
    },
    {
        "table": "submission",
        "columns": ["id", "apartment_id", "created_at", "state", "request_xml",
                    "request_xml_enc", "response_xml"],
        "rows": [
            [500, 10, "2026-08-01T00:00:00+00:00", "ok", "<req/>", "enc-req", "<resp/>"],
            [501, 10, "2026-08-01T00:00:00+00:00", "running", "<req/>", None, None],
            # exactly on the 90-day cutoff: not older, kept.
            [502, 10, "2026-08-15T10:00:00+00:00", "error", "<req/>", None, "<resp/>"],
            [503, 10, "2026-08-15T09:59:59+00:00", "outcome_unknown", None, None, "<resp/>"],
            # nothing to blank: not counted.
            [504, 10, "2026-07-01T00:00:00+00:00", "ok", None, None, None],
        ],
    },
    {
        "table": "guide_item",
        "columns": ["id", "apartment_id", "topic", "created_at", "updated_at"],
        "rows": [[50, 10, "wifi", S, S]],
    },
    {
        "table": "guide_photo",
        "columns": ["id", "item_id", "file_name", "created_at"],
        "rows": [[60, 50, "known.jpg", S]],
    },
    {
        "table": "guest_form_draft",
        "columns": ["id", "reservation_id", "device_key_hash", "claim_generation",
                    "owned_count", "fields_enc", "created_at", "updated_at"],
        "rows": [
            [700, 101, "dev-a", 0, 0, "x", S, "2026-11-12T00:00:00+00:00"],
            [701, 101, "dev-b", 0, 0, "x", S, "2026-11-05T00:00:00+00:00"],
            [702, 100, "dev-a", 0, 0, "x", S, "2026-11-12T00:00:00+00:00"],
            [703, 102, "dev-a", 0, 0, "x", S, "2026-11-12T00:00:00+00:00"],
            # exactly on the 7-day cutoff: kept.
            [704, 101, "dev-c", 0, 0, "x", S, "2026-11-06T10:00:00+00:00"],
            # check-out today (Prague): kept.
            [705, 103, "dev-a", 0, 0, "x", S, "2026-11-12T00:00:00+00:00"],
        ],
    },
    {
        "table": "legal_acceptance",
        "columns": ["id", "user_account_id", "document", "version", "accepted_at", "method"],
        "rows": [
            [800, 2, "terms", "v1", S, "clickwrap"],
            [801, 1, "terms", "v1", S, "clickwrap"],
        ],
    },
    {
        "table": "consent_texts",
        "columns": ["id", "version", "purpose", "lang", "text", "text_sha256", "created_at"],
        "rows": [[900, "ads-google-v1", "ads", "en", "golden", "0" * 64, S]],
    },
    {
        "table": "ad_click",
        "columns": ["id", "user_account_id", "platform", "clicked_at", "consent_text_id",
                    "consented_at", "created_at", "gclid", "gbraid", "wbraid", "fbc",
                    "client_user_agent", "uploaded_at", "withdrawn_at", "ids_deleted_at",
                    "send_state", "event_id"],
        "rows": [
            [600, 2, "google", "2026-11-01T00:00:00+00:00", 900, S, S,
             "g0", None, None, None, None, None, None, None, None, None],
            # 601 click older than 90 days: blanked.
            [601, 1, "google", "2026-08-01T00:00:00+00:00", 900, S, S,
             "g1", "b1", "w1", None, None, None, None, None, None, None],
            # 602 uploaded 24 days ago (Google keeps 30): kept.
            [602, 9, "google", "2026-11-01T00:00:00+00:00", 900, S, S,
             "g2", None, None, None, None, "2026-10-20T00:00:00+00:00", None, None, None, None],
            # 603 uploaded 43 days ago: blanked.
            [603, 7, "google", "2026-11-01T00:00:00+00:00", 900, S, S,
             "g3", None, None, None, None, "2026-10-01T00:00:00+00:00", None, None, None, None],
            # 604 pending Meta event of an account verified before the window:
            # expired, then blanked because it is expired.
            [604, 4, "meta", "2026-11-01T00:00:00+00:00", 900, S, S,
             None, None, None, "fb.1.a", "UA/1", None, None, None, "pending", "ev-604"],
            # 605 pending, account verified inside the window: kept.
            [605, 5, "meta", "2026-11-12T00:00:00+00:00", 900, S, S,
             None, None, None, "fb.1.b", "UA/2", None, None, None, "pending", "ev-605"],
            # 606 already blanked: untouched.
            [606, 1, "meta", "2026-11-01T00:00:00+00:00", 900, S, S,
             None, None, None, None, None, None, "2026-11-02T00:00:00+00:00",
             "2026-11-02T00:00:00+00:00", "withdrawn", "ev-606"],
            # 607 withdrawn, not blanked yet: blanked.
            [607, 8, "google", "2026-11-01T00:00:00+00:00", 900, S, S,
             "g7", None, None, None, None, None, "2026-11-10T00:00:00+00:00", None, None, None],
            # 608 Meta sent 8 days ago (Meta keeps 7): blanked.
            [608, 6, "meta", "2026-11-04T00:00:00+00:00", 900, S, S,
             None, None, None, "fb.1.c", "UA/3", "2026-11-05T00:00:00+00:00", None, None,
             "sent", "ev-608"],
        ],
    },
    {
        "table": "email_outbox",
        "columns": ["id", "idempotency_key", "kind", "owner_user_id", "created_at", "updated_at"],
        "rows": [
            [850, "golden-850", "signup_verify", 2, S, S],
            [851, "golden-851", "signup_verify", 1, S, S],
        ],
    },
    {
        "table": "audit",
        "columns": ["id", "at", "actor", "action", "detail", "owner_user_id"],
        "rows": [
            [950, S, "anonymous", "signup_started", "", 2],
            [951, S, "owner@example.test", "login", "", 1],
        ],
    },
]

# Files in the data directory. mtime_ago is seconds before NOW. A "dir" entry is
# a directory with that name (never a file to the sweep).
FILES = [
    # passport photos of guests
    {"dir": "passport_photos", "name": "1001.jpg.enc", "mtime_ago": 86400},
    {"dir": "passport_photos", "name": "1002.png.enc", "mtime_ago": 86400},
    {"dir": "passport_photos", "name": "1003.pdf", "mtime_ago": 86400},
    {"dir": "passport_photos", "name": "1004.webp.enc", "mtime_ago": 86400},
    {"dir": "passport_photos", "name": "1004.jpg", "mtime_ago": 86400},
    {"dir": "passport_photos", "name": "1005.jpg.enc", "mtime_ago": 86400},
    {"dir": "passport_photos", "name": "1007.jpg.enc", "mtime_ago": 86400},
    {"dir": "passport_photos", "name": "1008.jpg.enc", "mtime_ago": 86400},
    # names int() reads as a live guest id: not orphans, kept
    {"dir": "passport_photos", "name": "1_002.jpg", "mtime_ago": 86400},
    # orphans: 2000 has two files and is counted once
    {"dir": "passport_photos", "name": "2000.jpg.enc", "mtime_ago": 86400},
    {"dir": "passport_photos", "name": "2000.png", "mtime_ago": 86400},
    # counted, but delete_photo looks for the canonical lower-case name: kept
    {"dir": "passport_photos", "name": "2001.JPG", "mtime_ago": 86400},
    {"dir": "passport_photos", "name": "02002.pdf", "mtime_ago": 86400},
    {"dir": "passport_photos", "name": "+2003.webp.enc", "mtime_ago": 86400},
    # negative id: canonical name, deleted
    {"dir": "passport_photos", "name": "-5.jpg", "mtime_ago": 86400},
    # not photo names: skipped
    {"dir": "passport_photos", "name": "notes.txt", "mtime_ago": 86400},
    {"dir": "passport_photos", "name": "abc.jpg", "mtime_ago": 86400},
    {"dir": "passport_photos", "name": "2004.txt.enc", "mtime_ago": 86400},
    {"dir": "passport_photos", "name": "2006_.jpg", "mtime_ago": 86400},
    {"dir": "passport_photos", "name": ".jpg", "mtime_ago": 86400},
    {"dir": "passport_photos", "name": "2005.jpg", "kind": "dir"},
    # guide photos
    {"dir": "guide_photos", "name": "known.jpg", "mtime_ago": 86400},
    {"dir": "guide_photos", "name": "orphan-old.jpg", "mtime_ago": 7200},
    {"dir": "guide_photos", "name": "orphan-new.jpg", "mtime_ago": 600},
    # exactly one hour old: not older than the cutoff, kept
    {"dir": "guide_photos", "name": "orphan-edge.jpg", "mtime_ago": 3600},
    {"dir": "guide_photos", "name": "sub", "kind": "dir"},
]

# Rows compared after the run, ordered by id.
SNAPSHOT = [
    {"table": "guest", "columns": ["id", "passport_photo_at"]},
    {"table": "submission", "columns": ["id", "state", "request_xml", "request_xml_enc", "response_xml"]},
    {"table": "guide_photo", "columns": ["id", "file_name"]},
    {"table": "guest_form_draft", "columns": ["id"]},
    {"table": "user_account", "columns": ["id"]},
    {"table": "legal_acceptance", "columns": ["id"]},
    {"table": "email_outbox", "columns": ["id"]},
    {"table": "ad_click", "columns": ["id", "gclid", "gbraid", "wbraid", "fbc", "client_user_agent",
                                      "ids_deleted_at", "send_state", "last_error"]},
]
AUDIT_COLUMNS = ["at", "actor", "action", "detail", "owner_user_id", "actor_user_id",
                 "impersonator_user_id"]


def _now() -> datetime:
    return datetime.fromisoformat(NOW)


class _FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        moment = _now()
        return moment.astimezone(tz) if tz is not None else moment.replace(tzinfo=None)


class _FrozenDate(date):
    @classmethod
    def today(cls):
        return date.fromisoformat(TODAY)


def _seed(db) -> None:
    for table in SEED:
        cols = ", ".join(table["columns"])
        marks = ", ".join("?" for _ in table["columns"])
        for row in table["rows"]:
            db.execute(f"INSERT INTO {table['table']} ({cols}) VALUES ({marks})", row)


def _write_files(data_dir: Path) -> None:
    stamp = _now().timestamp()
    for entry in FILES:
        folder = data_dir / entry["dir"]
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / entry["name"]
        if entry.get("kind") == "dir":
            path.mkdir()
            continue
        path.write_bytes(b"golden")
        moment = stamp - entry["mtime_ago"]
        os.utime(path, (moment, moment))


def _files_left(data_dir: Path) -> list:
    left = []
    for entry in FILES:
        path = data_dir / entry["dir"] / entry["name"]
        if os.path.lexists(path):
            left.append(entry["dir"] + "/" + entry["name"])
    return sorted(left)


def _snapshot(db) -> dict:
    out = {}
    for spec in SNAPSHOT:
        cols = ", ".join(spec["columns"])
        rows = db.query(f"SELECT {cols} FROM {spec['table']} ORDER BY id")
        out[spec["table"]] = [[row[c] for c in spec["columns"]] for row in rows]
    rows = db.query(f"SELECT {', '.join(AUDIT_COLUMNS)} FROM audit")
    audit = [[row[c] for c in AUDIT_COLUMNS] for row in rows]
    audit.sort(key=lambda r: json.dumps(r, ensure_ascii=False))
    out["audit"] = audit
    return out


def render() -> str:
    """Seed a fresh database and data directory, run the sweep, return the JSON."""
    from app import (
        config,
        db,
        deadlines,
        guest_draft,
        guide_photos,
        meta_capi,
        passport_photos,
        reporting,
        signup,
    )

    db.init_db()
    _seed(db)
    data_dir = Path(tempfile.mkdtemp(prefix="ubyhost-photo-sweep-"))
    _write_files(data_dir)
    clock = types.SimpleNamespace(time=lambda: _now().timestamp())
    with ExitStack() as stack:
        for module in (db, deadlines, guest_draft, meta_capi, reporting, signup):
            stack.enter_context(mock.patch.object(module, "datetime", _FrozenDatetime))
        stack.enter_context(mock.patch.object(passport_photos, "date", _FrozenDate))
        stack.enter_context(mock.patch.object(guide_photos, "time", clock))
        stack.enter_context(
            mock.patch.object(passport_photos, "PHOTOS_DIR", data_dir / "passport_photos"))
        stack.enter_context(
            mock.patch.object(guide_photos, "PHOTOS_DIR", data_dir / "guide_photos"))
        # The order of scheduler._job_photo_sweep.
        counts = {
            "photos": passport_photos.purge_stale(),
            "guide_orphans": guide_photos.purge_orphans(),
            "payloads": reporting.purge_submission_payloads(),
            "drafts": guest_draft.purge(),
            "signup": signup.purge(),
        }
    assert config.DATA_DIR != data_dir
    files_left = _files_left(data_dir)
    shutil.rmtree(data_dir)
    golden = {
        "now": NOW,
        "today": TODAY,
        "seed": SEED,
        "files": FILES,
        "snapshot": SNAPSHOT,
        "audit_columns": AUDIT_COLUMNS,
        "counts": counts,
        "files_left": files_left,
        "after": _snapshot(db),
    }
    return json.dumps(golden, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-golden-"))
    os.environ.setdefault("UBYHOST_DATA_DIR", str(tmp))
    os.environ.setdefault("UBYHOST_DB", str(tmp / "photo_sweep_golden.sqlite3"))
    os.environ.setdefault("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
    sys.path.insert(0, str(APP))
    main()
