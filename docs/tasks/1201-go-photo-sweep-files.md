# 1201: Go photo sweep, part 1: golden fixture and the two file steps

Status: todo
Depends on: none | Base commit: a83df541 | Branch: task/1201-go-photo-sweep (1202 continues on the same branch; one PR)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier A (guest data, deletion)

## 1. Objective

First half of porting the Python job `photo_sweep` (`App/app/scheduler.py` `_job_photo_sweep`) to Go (plan `docs/plans/go-full-move.md` J1): a Python golden script that runs the real job steps on a fixture with a frozen clock, and the Go code for the two file steps (passport photos, guide photos) plus the audit helpers. Brief 1202 adds the three database steps, the parity test and the job registration; the job stays off until an operator lists `photo_sweep` in `UBYHOST_GO_JOB_KINDS`.

## 2. Context

Hard rules that apply: rule 2 (privacy: this job deletes guest data, it must delete exactly what Python deletes, no more, no less), rule 3 (the fixture holds only made-up values), rule 4 (no new dependency: only the Go standard library, pgx and `go/internal/deadlines`, all already in go.mod), rule 5 (the Python side is not touched at all; the SQL is the same SQL Python runs on PostgreSQL).

What the Python job does (do not edit any of it), in this order inside ONE try (the first exception fails the job, later steps do not run):

1. `passport_photos.purge_stale()`: guests with `identity_verified_at` set, OR `COALESCE(date(stay_from), date(r.date_from)) <= today-7`, OR `date(passport_photo_at) <= today-30` (today = `date.today()`, the server-local date) lose every file `DATA_DIR/passport_photos/<id><ext>[.enc]` (ext in `.jpg .pdf .png .webp`, lower case only) and, when `passport_photo_at` is truthy (an empty string is not), that column is set to NULL. Then orphans: every regular file whose name (minus `.enc`) has a known suffix (case-insensitive) and whose stem `int()` parses, and whose id has no guest row, gets `delete_photo(id)` (canonical lower-case names only) and counts 1 per id. Then `db.audit_retention("passport_photos", removed, "check-in on or before <d7>; upload on or before <d30>; or verified")`.
2. `guide_photos.purge_orphans()`: files in `DATA_DIR/guide_photos` not named in `guide_photo.file_name` and with mtime more than 1 hour ago are unlinked (`missing_ok=True`).
3. to 5.: brief 1202.

Findings the code below already handles (keep them, they are the parity traps):

- PostgreSQL text columns here are all `COLLATE "C"` (`App/migrations_pg/00001_baseline.sql`), so comparisons are byte order, as in SQLite. `db.sqlite_date_expr` is `ubyhost_sqlite_date(...)` on PostgreSQL (baseline function, also used by `go/internal/calendar/dsr_due.go`).
- `db.audit_retention` detail is `json.dumps(..., sort_keys=True)` with the default separators and `ensure_ascii=True`: `{"class": "...", "count": N, "cutoff": "...", "dry_run": false, "owner_user_id": null}`; actor `system`, action `retention_delete`, the three user ids NULL. `db.utcnow()` is `YYYY-MM-DDTHH:MM:SS+00:00`.
- Python `int()` on a file stem accepts `02002`, `+2003`, `-5`, `1_002`, surrounding whitespace and Unicode digits; ids are de-duplicated by value, and `delete_photo` only looks at canonical names, so `2001.JPG` or `02002.pdf` is counted but stays on disk. `pathlib.is_file` follows symlinks and answers false on ENOENT, ENOTDIR, EBADF, ELOOP.
- Today (TZ): neither `ubyhost`/`worker` (python:3.12-slim) nor `ubyhost-go` (alpine) sets `TZ` in `deploy/lightsail/docker-compose.yml`, so `date.today()` is the UTC date; Go uses `now.Local()`, the same thing under the same `TZ`.
- Mount: `deploy/lightsail/docker-compose.yml` mounts `ubyhost-data:/data:ro` in `ubyhost-go` (read-write in `worker`; both run as uid 10001). On that mount every unlink fails with EROFS: Go fails the job loudly on any unlink error other than "not found". Switching the job to Go needs that mount made read-write first (owner step, not this brief).
- Accepted differences: Python's `unlink()` in `delete_photo` raises if a file vanishes between `is_file` and `unlink`; Go treats "already gone" as done. Go leaves out Python's `(? IS NULL OR a.owner_user_id = ?)` filter (always true for the global sweep).

The golden script follows `App/scripts/dsr_due_golden.py`: it runs on a throwaway SQLite database (CI also runs it on PostgreSQL in `test-postgres-full`; checked locally: identical output), patches `datetime`/`date`/`time` in the modules the steps use, and writes `go/internal/photosweep/testdata/photo_sweep_golden.json`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/scripts/photo_sweep_golden.py` | create | golden script (runs the real Python steps) |
| `App/tests/test_go_photo_sweep_golden.py` | create | fails when the golden file is stale |
| `go/internal/photosweep/testdata/photo_sweep_golden.json` | create | written by the script, never by hand |
| `go/internal/photosweep/files.go` | create | passport photo and guide photo steps |
| `go/internal/photosweep/audit.go` | create | `iso`, `pyJSONString`, `auditRetention`, `auditHost` |
| `go/internal/photosweep/files_test.go` | create | unit tests, no database |
| `docs/tasks/1201-report.md` | create | the report |

No other file may change.

## 4. Steps

Work from `/home/user/jsfpecharoperations` (the repo root). Create each file with the heredoc exactly as given (tabs in Go are real tabs; copy the block verbatim).

### Step 0: check the start

```bash
git branch --show-current; ls go/internal/photosweep 2>&1 | tail -1; grep -c '"photo_sweep":      "passport photo cleanup",' go/internal/jobs/queue.go; grep -c 'def _job_photo_sweep() -> None:' App/app/scheduler.py
```

Expected: `task/1201-go-photo-sweep`, `ls: cannot access ...: No such file or directory`, `1`, `1`. Otherwise STOP (§8).

### Step 1: create `App/scripts/photo_sweep_golden.py`

```bash
mkdir -p App/scripts && cat > App/scripts/photo_sweep_golden.py <<'EOF'
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
EOF
sha256sum App/scripts/photo_sweep_golden.py 2>&1 | tail -1
```

Expected: `cb3320ae4b477ea6cf0490a8c3da5404627993224bc67d12cd9a0e49b0f2b656  App/scripts/photo_sweep_golden.py`. Different: delete the file and repeat the step once; still different: STOP (§8).

### Step 2: create `App/tests/test_go_photo_sweep_golden.py`

```bash
mkdir -p App/tests && cat > App/tests/test_go_photo_sweep_golden.py <<'EOF'
"""go/internal/photosweep/sweep_test.go reads go/internal/photosweep/testdata/photo_sweep_golden.json."""

import importlib.util
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "photo_sweep_golden", APP_DIR / "scripts" / "photo_sweep_golden.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_photo_sweep_golden_matches_python_photo_sweep(monkeypatch, tmp_path):
    from app import config

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "photo-sweep-golden.sqlite3")
    generator = _load_generator()
    committed = generator.OUT.read_bytes()
    assert generator.render().encode("utf-8") == committed
    assert committed.count(b'"retention_delete"') == 2
EOF
sha256sum App/tests/test_go_photo_sweep_golden.py 2>&1 | tail -1
```

Expected: `50dc8bb4e62c71d177be28fbe15b91a0754522fe6503b47ec251040ab0d26b0d  App/tests/test_go_photo_sweep_golden.py`. Different: delete the file and repeat the step once; still different: STOP (§8).

### Step 3: write the golden file and test it

```bash
cd App && (test -x .venv/bin/python || (python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt)) 2>&1 | tail -3; .venv/bin/python scripts/photo_sweep_golden.py 2>&1 | tail -3; sha256sum ../go/internal/photosweep/testdata/photo_sweep_golden.json; .venv/bin/python -m pytest tests/test_go_photo_sweep_golden.py -q --tb=short -x 2>&1 | tail -5; .venv/bin/ruff check scripts/photo_sweep_golden.py tests/test_go_photo_sweep_golden.py 2>&1 | tail -2; cd ..
```

Expected: `wrote .../photo_sweep_golden.json`, sha256 `e206f31b996d883a13fbc94625aa0a82feb5dda8dfb1f5bd2f0b37da858971f2`, `1 passed`, `All checks passed!`. A different sha: STOP (§8), do not edit the JSON.

### Step 4: create `go/internal/photosweep/audit.go`

```bash
mkdir -p go/internal/photosweep && cat > go/internal/photosweep/audit.go <<'EOF'
package photosweep

// The audit helpers of App/app/db.py that the sweep steps use, and the
// timestamp format they write.

import (
	"context"
	"fmt"
	"strconv"
	"strings"
	"time"
	"unicode/utf16"

	"github.com/jackc/pgx/v5/pgxpool"
)

// iso is datetime.now(timezone.utc).replace(microsecond=0).isoformat(), the
// format of db.utcnow and of every cutoff these steps compare with.
func iso(t time.Time) string {
	return t.UTC().Format("2006-01-02T15:04:05") + "+00:00"
}

// pyJSONString is json.dumps(s) with the default ensure_ascii=True.
func pyJSONString(s string) string {
	var b strings.Builder
	b.WriteByte('"')
	for _, r := range s {
		switch {
		case r == '"':
			b.WriteString(`\"`)
		case r == '\\':
			b.WriteString(`\\`)
		case r == '\n':
			b.WriteString(`\n`)
		case r == '\r':
			b.WriteString(`\r`)
		case r == '\t':
			b.WriteString(`\t`)
		case r == '\b':
			b.WriteString(`\b`)
		case r == '\f':
			b.WriteString(`\f`)
		case r < 0x20 || (r >= 0x7f && r <= 0xffff):
			fmt.Fprintf(&b, `\u%04x`, r)
		case r > 0xffff:
			hi, lo := utf16.EncodeRune(r)
			fmt.Fprintf(&b, `\u%04x\u%04x`, hi, lo)
		default:
			b.WriteRune(r)
		}
	}
	b.WriteByte('"')
	return b.String()
}

// auditRetention is db.audit_retention(class, count, cutoff) with no owner and
// no dry run: the detail is json.dumps(..., sort_keys=True) byte for byte.
func auditRetention(ctx context.Context, pool *pgxpool.Pool, now time.Time, class string, count int, cutoff string) error {
	detail := `{"class": ` + pyJSONString(class) + `, "count": ` + strconv.Itoa(count) +
		`, "cutoff": ` + pyJSONString(cutoff) + `, "dry_run": false, "owner_user_id": null}`
	_, err := pool.Exec(ctx,
		`INSERT INTO audit (at, actor, action, detail) VALUES ($1, 'system', 'retention_delete', $2)`,
		iso(now), detail)
	return err
}

// auditHost is db.audit(action, detail) from a background job: no signed-in
// actor, so the actor is "host" and the three user ids are NULL.
func auditHost(ctx context.Context, pool *pgxpool.Pool, now time.Time, action, detail string) error {
	_, err := pool.Exec(ctx,
		`INSERT INTO audit (at, actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id)
		 VALUES ($1, 'host', $2, $3, NULL, NULL, NULL)`,
		iso(now), action, detail)
	return err
}
EOF
sha256sum go/internal/photosweep/audit.go 2>&1 | tail -1
```

Expected: `95a8ea1a70c0471edffc133dd138dd8521c9ee305e80fc5e0220f8387042571c  go/internal/photosweep/audit.go`. Different: delete the file and repeat the step once; still different: STOP (§8).

### Step 5: create `go/internal/photosweep/files.go`

```bash
mkdir -p go/internal/photosweep && cat > go/internal/photosweep/files.go <<'EOF'
// Package photosweep is the photo_sweep job, App/app/scheduler.py
// _job_photo_sweep, in Go. This file holds the two file steps:
// passport_photos.purge_stale (App/app/passport_photos.py) and
// guide_photos.purge_orphans (App/app/guide_photos.py). db.go holds the three
// database steps, sweep.go runs all five in the job's order.
//
// Parity: testdata/photo_sweep_golden.json, written by
// App/scripts/photo_sweep_golden.py from the real Python, is what the Go test
// must reproduce. Python is the reference: when they differ, Go is wrong.
package photosweep

import (
	"context"
	"errors"
	"fmt"
	"io/fs"
	"math/big"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"syscall"
	"time"
	"unicode"

	"github.com/jackc/pgx/v5/pgxpool"
)

const (
	// photoAfterCheckinDays is passport_photos.PHOTO_AFTER_CHECKIN_DAYS.
	photoAfterCheckinDays = 7
	// photoMaxAgeDays is passport_photos.PHOTO_MAX_AGE_DAYS.
	photoMaxAgeDays = 30
	// encSuffix is passport_photos.ENC_SUFFIX.
	encSuffix = ".enc"
	// guideOrphanAge is the one hour guide_photos.purge_orphans leaves a new
	// file alone (add writes the file before its row).
	guideOrphanAge = time.Hour
)

// allExtensions is passport_photos.ALL_EXTENSIONS, in the same sorted order.
var allExtensions = []string{".jpg", ".pdf", ".png", ".webp"}

// staleGuestsSQL is the query of passport_photos.purge_stale for the global
// sweep (owner_user_id None, so its "? IS NULL OR" filter is always true and
// left out). ubyhost_sqlite_date is what db.sqlite_date_expr names on
// PostgreSQL. ORDER BY only makes runs repeatable.
const staleGuestsSQL = `SELECT g.id, g.passport_photo_at FROM guest g
	JOIN reservation r ON r.id = g.reservation_id
	JOIN apartment a ON a.id = r.apartment_id
	WHERE (g.identity_verified_at IS NOT NULL
	OR COALESCE(ubyhost_sqlite_date(g.stay_from), ubyhost_sqlite_date(r.date_from)) <= $1
	OR ubyhost_sqlite_date(g.passport_photo_at) <= $2)
	ORDER BY g.id`

// photosDir and guideDir are passport_photos.PHOTOS_DIR and
// guide_photos.PHOTOS_DIR under the data directory.
func photosDir(dataDir string) string { return filepath.Join(dataDir, "passport_photos") }
func guideDir(dataDir string) string  { return filepath.Join(dataDir, "guide_photos") }

// ignoredStatError is pathlib's _ignore_error (Python 3.12): these errors make
// is_file and is_dir answer false; every other error is raised.
func ignoredStatError(err error) bool {
	return errors.Is(err, fs.ErrNotExist) || errors.Is(err, syscall.ENOTDIR) ||
		errors.Is(err, syscall.EBADF) || errors.Is(err, syscall.ELOOP)
}

// statMode is the shared part of isFile and isDir: os.Stat follows symlinks,
// like Path.stat().
func statMode(path string) (fs.FileMode, bool, error) {
	info, err := os.Stat(path)
	if err != nil {
		if ignoredStatError(err) {
			return 0, false, nil
		}
		return 0, false, err
	}
	return info.Mode(), true, nil
}

// isFile is pathlib.Path.is_file.
func isFile(path string) (bool, error) {
	mode, ok, err := statMode(path)
	return ok && mode.IsRegular(), err
}

// isDir is pathlib.Path.is_dir.
func isDir(path string) (bool, error) {
	mode, ok, err := statMode(path)
	return ok && mode.IsDir(), err
}

// removeFile unlinks one file. A file that is already gone is not an error
// (another process won the race); any other error, a read-only mount
// included, fails the job.
func removeFile(path string) error {
	if err := os.Remove(path); err != nil && !errors.Is(err, fs.ErrNotExist) {
		return fmt.Errorf("photo sweep: remove %s: %w", filepath.Base(path), err)
	}
	return nil
}

// pathsFor is passport_photos._paths_for: id is the decimal guest id.
func pathsFor(dir, id string) []string {
	out := make([]string, 0, 2*len(allExtensions))
	for _, ext := range allExtensions {
		out = append(out, filepath.Join(dir, id+ext+encSuffix), filepath.Join(dir, id+ext))
	}
	return out
}

// hasPhoto is passport_photos.has_photo.
func hasPhoto(dir, id string) (bool, error) {
	for _, p := range pathsFor(dir, id) {
		ok, err := isFile(p)
		if err != nil || ok {
			return ok, err
		}
	}
	return false, nil
}

// deletePhoto is passport_photos.delete_photo.
func deletePhoto(dir, id string) error {
	for _, p := range pathsFor(dir, id) {
		ok, err := isFile(p)
		if err != nil {
			return err
		}
		if ok {
			if err := removeFile(p); err != nil {
				return err
			}
		}
	}
	return nil
}

// pySuffix is PurePath(name).suffix.
func pySuffix(name string) string {
	i := strings.LastIndex(name, ".")
	if 0 < i && i < len(name)-1 {
		return name[i:]
	}
	return ""
}

// pyStem is PurePath(name).stem.
func pyStem(name string) string {
	i := strings.LastIndex(name, ".")
	if 0 < i && i < len(name)-1 {
		return name[:i]
	}
	return name
}

// pySpace is str.isspace for one rune: Go's White_Space plus the four
// separators U+001C..U+001F that Python also strips.
func pySpace(r rune) bool {
	return unicode.IsSpace(r) || (r >= 0x1c && r <= 0x1f)
}

// pyDigit is the value of a Unicode decimal digit (category Nd), as int()
// reads it. Every Nd run in Unicode starts at its zero, so the value is the
// distance from the start of the run, modulo 10.
func pyDigit(r rune) (int64, bool) {
	if r >= '0' && r <= '9' {
		return int64(r - '0'), true
	}
	if !unicode.Is(unicode.Nd, r) {
		return 0, false
	}
	start := r
	for unicode.Is(unicode.Nd, start-1) {
		start--
	}
	return int64(r-start) % 10, true
}

// pyInt is Python's int(s) for a str in base 10: surrounding whitespace, one
// optional sign, Unicode decimal digits with single underscores between them.
// ok is false where int() raises ValueError.
func pyInt(s string) (*big.Int, bool) {
	s = strings.TrimFunc(s, pySpace)
	neg := false
	if strings.HasPrefix(s, "+") || strings.HasPrefix(s, "-") {
		neg = s[0] == '-'
		s = s[1:]
	}
	n := new(big.Int)
	ten := big.NewInt(10)
	digits := 0
	prevUnderscore := false
	for _, r := range s {
		if r == '_' {
			if digits == 0 || prevUnderscore {
				return nil, false
			}
			prevUnderscore = true
			continue
		}
		d, ok := pyDigit(r)
		if !ok {
			return nil, false
		}
		n.Mul(n, ten).Add(n, big.NewInt(d))
		digits++
		prevUnderscore = false
	}
	if digits == 0 || prevUnderscore {
		return nil, false
	}
	if neg {
		n.Neg(n)
	}
	return n, true
}

// orphanIDs is passport_photos._orphan_ids: the ids, as decimal strings in
// numeric order, that files in dir name and no guest row has. An id beyond the
// bigint range can name no guest row, so it is an orphan without a lookup.
func orphanIDs(ctx context.Context, pool *pgxpool.Pool, dir string) ([]string, error) {
	ok, err := isDir(dir)
	if err != nil || !ok {
		return nil, err
	}
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, err
	}
	found := map[string]*big.Int{}
	for _, e := range entries {
		file, err := isFile(filepath.Join(dir, e.Name()))
		if err != nil {
			return nil, err
		}
		if !file {
			continue
		}
		name := strings.TrimSuffix(e.Name(), encSuffix)
		ext := strings.ToLower(pySuffix(name))
		known := false
		for _, a := range allExtensions {
			known = known || ext == a
		}
		if !known {
			continue
		}
		if n, ok := pyInt(pyStem(name)); ok {
			found[n.String()] = n
		}
	}
	if len(found) == 0 {
		return nil, nil
	}
	var lookup []int64
	for _, n := range found {
		if n.IsInt64() {
			lookup = append(lookup, n.Int64())
		}
	}
	if len(lookup) > 0 {
		rows, err := pool.Query(ctx, `SELECT id FROM guest WHERE id = ANY($1)`, lookup)
		if err != nil {
			return nil, err
		}
		for rows.Next() {
			var id int64
			if err := rows.Scan(&id); err != nil {
				rows.Close()
				return nil, err
			}
			delete(found, strconv.FormatInt(id, 10))
		}
		rows.Close()
		if err := rows.Err(); err != nil {
			return nil, err
		}
	}
	nums := make([]*big.Int, 0, len(found))
	for _, n := range found {
		nums = append(nums, n)
	}
	sort.Slice(nums, func(i, j int) bool { return nums[i].Cmp(nums[j]) < 0 })
	out := make([]string, len(nums))
	for i, n := range nums {
		out[i] = n.String()
	}
	return out, nil
}

// purgePassportPhotos is passport_photos.purge_stale() for the global sweep.
// today is the server-local date (Python's date.today()). It returns the
// number of photos removed and writes the retention audit line, zero included.
func purgePassportPhotos(ctx context.Context, pool *pgxpool.Pool, dataDir string, today, now time.Time) (int, error) {
	dir := photosDir(dataDir)
	day := func(back int) string {
		return time.Date(today.Year(), today.Month(), today.Day()-back, 0, 0, 0, 0, time.UTC).Format("2006-01-02")
	}
	checkin, uploaded := day(photoAfterCheckinDays), day(photoMaxAgeDays)
	rows, err := pool.Query(ctx, staleGuestsSQL, checkin, uploaded)
	if err != nil {
		return 0, err
	}
	type stale struct {
		id     int64
		marked *string
	}
	var list []stale
	for rows.Next() {
		var s stale
		if err := rows.Scan(&s.id, &s.marked); err != nil {
			rows.Close()
			return 0, err
		}
		list = append(list, s)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return 0, err
	}
	removed := 0
	for _, s := range list {
		id := strconv.FormatInt(s.id, 10)
		has, err := hasPhoto(dir, id)
		if err != nil {
			return removed, err
		}
		if has {
			if err := deletePhoto(dir, id); err != nil {
				return removed, err
			}
			removed++
		}
		// Python: `if row["marked"]`, so an empty string is left as it is.
		if s.marked != nil && *s.marked != "" {
			if _, err := pool.Exec(ctx, `UPDATE guest SET passport_photo_at = NULL WHERE id = $1`, s.id); err != nil {
				return removed, err
			}
		}
	}
	orphans, err := orphanIDs(ctx, pool, dir)
	if err != nil {
		return removed, err
	}
	for _, id := range orphans {
		if err := deletePhoto(dir, id); err != nil {
			return removed, err
		}
		removed++
	}
	cutoff := "check-in on or before " + checkin + "; upload on or before " + uploaded + "; or verified"
	if err := auditRetention(ctx, pool, now, "passport_photos", removed, cutoff); err != nil {
		return removed, err
	}
	return removed, nil
}

// purgeGuideOrphans is guide_photos.purge_orphans: files in guide_photos that
// no guide_photo row names and that are more than an hour old.
func purgeGuideOrphans(ctx context.Context, pool *pgxpool.Pool, dataDir string, now time.Time) (int, error) {
	dir := guideDir(dataDir)
	ok, err := isDir(dir)
	if err != nil || !ok {
		return 0, err
	}
	known := map[string]bool{}
	rows, err := pool.Query(ctx, `SELECT file_name FROM guide_photo`)
	if err != nil {
		return 0, err
	}
	for rows.Next() {
		var name string
		if err := rows.Scan(&name); err != nil {
			rows.Close()
			return 0, err
		}
		known[name] = true
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return 0, err
	}
	entries, err := os.ReadDir(dir)
	if err != nil {
		return 0, err
	}
	cutoff := now.Add(-guideOrphanAge)
	removed := 0
	for _, e := range entries {
		path := filepath.Join(dir, e.Name())
		file, err := isFile(path)
		if err != nil {
			return removed, err
		}
		if !file || known[e.Name()] {
			continue
		}
		info, err := os.Stat(path)
		if err != nil {
			return removed, err
		}
		if !info.ModTime().Before(cutoff) {
			continue
		}
		if err := removeFile(path); err != nil {
			return removed, err
		}
		removed++
	}
	return removed, nil
}
EOF
sha256sum go/internal/photosweep/files.go 2>&1 | tail -1
```

Expected: `088e9617804ac115ff83e98cfc5064c5a08882f8d45ad06ed4e97db1bbc7c136  go/internal/photosweep/files.go`. Different: delete the file and repeat the step once; still different: STOP (§8).

### Step 6: create `go/internal/photosweep/files_test.go`

```bash
mkdir -p go/internal/photosweep && cat > go/internal/photosweep/files_test.go <<'EOF'
package photosweep

import (
	"os"
	"path/filepath"
	"testing"
)

func TestPyIntMatchesPythonInt(t *testing.T) {
	ok := map[string]string{"1001": "1001", "02002": "2002", "+2003": "2003", "-5": "-5",
		"1_002": "1002", " 7 ": "7", "\x1c8": "8", "\u0663\u0664": "34", "99999999999999999999": "99999999999999999999"}
	for in, want := range ok {
		n, good := pyInt(in)
		if !good || n.String() != want {
			t.Errorf("pyInt(%q) = %v, %v; want %s", in, n, good, want)
		}
	}
	for _, in := range []string{"", "abc", "2006_", "_1", "1__0", "+", "+_5", "1.5", "0x10", "1 0"} {
		if _, good := pyInt(in); good {
			t.Errorf("pyInt(%q) accepted; Python raises ValueError", in)
		}
	}
}

func TestPySuffixAndStem(t *testing.T) {
	cases := [][3]string{{"1001.jpg", ".jpg", "1001"}, {".jpg", "", ".jpg"}, {"x.", "", "x."},
		{"a.tar.jpg", ".jpg", "a.tar"}, {"noext", "", "noext"}, {"..jpg", ".jpg", "."}}
	for _, c := range cases {
		if got := pySuffix(c[0]); got != c[1] {
			t.Errorf("pySuffix(%q) = %q, want %q", c[0], got, c[1])
		}
		if got := pyStem(c[0]); got != c[2] {
			t.Errorf("pyStem(%q) = %q, want %q", c[0], got, c[2])
		}
	}
}

func TestPyJSONStringEnsureASCII(t *testing.T) {
	cases := map[string]string{"check-in on or before 2026-11-06": `"check-in on or before 2026-11-06"`,
		"a\"b\\c\n\x01": `"a\"b\\c\n\u0001"`, "\u00e9\u20ac": `"\u00e9\u20ac"`, "\U0001F600": `"\ud83d\ude00"`, "\x7f": `"\u007f"`}
	for in, want := range cases {
		if got := pyJSONString(in); got != want {
			t.Errorf("pyJSONString(%q) = %s, want %s", in, got, want)
		}
	}
}

func TestDeletePhotoRemovesCanonicalNamesOnly(t *testing.T) {
	dir := t.TempDir()
	for _, name := range []string{"5.jpg.enc", "5.pdf", "5.JPG", "05.png"} {
		if err := os.WriteFile(filepath.Join(dir, name), []byte("x"), 0o600); err != nil {
			t.Fatal(err)
		}
	}
	if has, err := hasPhoto(dir, "5"); err != nil || !has {
		t.Fatalf("hasPhoto = %v, %v", has, err)
	}
	if err := deletePhoto(dir, "5"); err != nil {
		t.Fatal(err)
	}
	for name, want := range map[string]bool{"5.jpg.enc": false, "5.pdf": false, "5.JPG": true, "05.png": true} {
		_, err := os.Lstat(filepath.Join(dir, name))
		if (err == nil) != want {
			t.Errorf("%s exists = %v, want %v", name, err == nil, want)
		}
	}
}

func TestRemoveFileFailsOnUnwritableDir(t *testing.T) {
	if os.Geteuid() == 0 {
		t.Skip("root ignores directory permissions")
	}
	dir := t.TempDir()
	path := filepath.Join(dir, "1.jpg")
	if err := os.WriteFile(path, []byte("x"), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := os.Chmod(dir, 0o555); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = os.Chmod(dir, 0o755) })
	if err := removeFile(path); err == nil {
		t.Fatal("removeFile in a read-only directory returned nil")
	}
	if err := removeFile(filepath.Join(dir, "gone.jpg")); err != nil {
		t.Fatalf("a missing file must not fail: %v", err)
	}
}
EOF
sha256sum go/internal/photosweep/files_test.go 2>&1 | tail -1
```

Expected: `8a9e1244e16804e2437fb2298c45097e906268e961d196a55f9d20200198d552  go/internal/photosweep/files_test.go`. Different: delete the file and repeat the step once; still different: STOP (§8).

### Step 7: build, vet, test, commit

```bash
cd go && gofmt -l internal/photosweep; go vet ./internal/photosweep 2>&1 | tail -5; go test ./internal/photosweep -count=1 2>&1 | tail -5; cd .. && git add App/scripts/photo_sweep_golden.py App/tests/test_go_photo_sweep_golden.py go/internal/photosweep && git commit -q -m "1201 steps 1-6" && git status --short | tail -5
```

Expected: no gofmt output, no vet output, `ok  .../internal/photosweep`, clean status.

## 5. Do not touch

Everything in `App/app/`, `App/tests/conftest.py`, `go/internal/jobs/`, `go/internal/metacapi/`, `go/internal/deadlines/`, `go/cmd/ubyhost-web/` (brief 1202 adds its one file), `deploy/`, `docs/ENVIRONMENT.md`, `docs/context/`. Rules 2, 3, 4, 5 (§2). Never push, never merge.

## 6. Commands

From the repo root, after step 7:

```bash
cd App && .venv/bin/python -m pytest tests/test_go_photo_sweep_golden.py tests/test_dsr_due_golden.py -q --tb=short -x 2>&1 | tail -5; cd ..
cd go && go vet ./internal/photosweep && go test ./internal/photosweep -count=1 2>&1 | tail -5; cd ..
git status --short | tail -5
```

Expected: `2 passed`; `ok`; empty status (re-running the golden script leaves `git status` clean: that is the parity check of this part).

## 7. Acceptance

- [ ] The six files exist with the sha256 values in §4 (the JSON: §4 step 3).
- [ ] `test_go_photo_sweep_golden.py` passes; `go test ./internal/photosweep` passes.
- [ ] `git diff --stat a83df541..HEAD` lists only the §3 files.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found or a sha256 differs twice;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1201-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

Then go straight on with `docs/tasks/1202-go-photo-sweep-job.md` only if the orchestrator told you to; otherwise stop.

## Risk list (for the reviewer)

`go/internal/photosweep/files.go` (what gets deleted: the stale-guest SQL, `orphanIDs`, `pyInt`, `deletePhoto`), `go/internal/photosweep/audit.go` (audit bytes), `App/scripts/photo_sweep_golden.py` (the clock patching: every module whose `datetime`/`date`/`time` a step reads must be patched, or the golden depends on the real date).

## Owner steps

None for this part. The switch steps are in brief 1202.
