"""Write go/internal/calendar/testdata/filing_watchdog_golden.json from the real Python.

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    .venv/bin/python scripts/filing_watchdog_golden.py

It seeds a throwaway SQLite database with the fixed rows in SEED and, for each
instant in INSTANTS, records what filing_watchdog.at_risk_stays (with the
stays awaiting the automatic resend) and unknown_risk_stays return. It also
records heartbeat_url for each URL in HEARTBEATS. Nothing is written to the
database after the seed, so the instants are independent.
go/internal/calendar/filing_watchdog_test.go seeds PostgreSQL from the same
file and compares. App/tests/test_filing_watchdog_golden.py fails when this
file is stale. Brief 1159b's run golden imports SEED and _seed from here.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "calendar" / "testdata" / "filing_watchdog_golden.json"

# filing_watchdog reads these at import time (RETRY_GRACE is 2 x 10 minutes).
GOLDEN_ENV = {
    "UBYHOST_SUBMIT_SWEEP_MINUTES": "10",
    "UBYHOST_APP_BASE_URL": "https://app.example.test",
    "UBYHOST_PUBLIC_BASE_URL": "https://www.example.test",
    "UBYHOST_MAIL_BACKEND": "console",
    "UBYHOST_OPERATOR_EMAIL": "ops@example.test",
    "UBYHOST_WEB_PUSH": "1",
    "UBYHOST_HEARTBEAT_FILING_URL": "",
}

STAMP = "2026-09-01T00:00:00+00:00"

_GUEST_COLUMNS = ["id", "reservation_id", "surname", "nationality", "submit_state",
                  "submission_id", "stay_from", "is_lead", "archived_at",
                  "created_at", "updated_at"]


def _guest(gid, rid, nationality="DEU", state="pending", submission=None,
           stay_from=None, archived=None):
    return [gid, rid, "Test", nationality, state, submission, stay_from, 0, archived,
            STAMP, STAMP]


def _stay(rid, apt, date_from, *, status="active", source="host", archived=None,
          mailed=None):
    return [rid, apt, f"u{rid}", date_from, "2026-09-30", status, source, archived,
            mailed, STAMP, STAMP]


def _sub(sid, state, finished, *, retried=None, mode="auto"):
    return [sid, 1, STAMP, mode, state, finished, retried]


# T0 is 2026-09-17 10:00 UTC, 12:00 in Prague (a Thursday). The deadline of an
# arrival on 09-15 is 09-17 23:59:59 (12 h left at T0), of 09-16 is 09-18
# 23:59:59 (36 h, not yet at risk), of 09-14 is 09-16 23:59:59 (overdue). The
# comment on each stay says what T0 must do with it.
SEED = [
    {
        "table": "user_account",
        "columns": ["id", "username", "password_hash", "role", "created_at"],
        "rows": [
            [1, "host-one@example.test", "x", "host", STAMP],
            [2, "host-two@example.test", "x", "host", STAMP],
        ],
    },
    {
        "table": "legal_entity",
        "columns": ["id", "name", "contact_email", "created_at"],
        "rows": [
            [1, "Entity One", " Contact.One@Example.TEST ", STAMP],
            [2, "Entity Blank", None, STAMP],
        ],
    },
    {
        "table": "apartment",
        "columns": ["id", "owner_user_id", "legal_entity_id", "internal_name", "city_en",
                    "uby_name", "permalink_token", "active", "created_at"],
        "rows": [
            [1, 1, 1, "Byt Dole", "Brno", "UBY", "tok1", 1, STAMP],
            [2, 1, 1, "Byt Vypnuty", "Brno", "UBY", "tok2", 0, STAMP],
            [3, 2, None, "Cizi byt", "Brno", "UBY", "tok3", 1, STAMP],
            [4, 1, 1, 'Byt <Žižkov> & "Co"', "Praha", "UBY", "tok4", 1, STAMP],
            [5, None, 2, "", "Brno", "UBY", "tok5", 1, STAMP],
        ],
    },
    {
        "table": "submission",
        "columns": ["id", "apartment_id", "created_at", "mode", "state", "finished_at",
                    "retried_at"],
        "rows": [
            _sub(301, "outcome_unknown", "2026-09-17T09:45:00+00:00"),
            _sub(302, "outcome_unknown", "2026-09-17T09:55:00+00:00"),
            _sub(303, "outcome_unknown", "2026-09-17T09:50:00+00:00", mode="auto_resend"),
            _sub(304, "outcome_unknown", "2026-09-17T09:50:00+00:00",
                 retried="2026-09-17T09:58:00+00:00"),
            _sub(305, "outcome_unknown", "2026-09-17T09:30:00+00:00", mode="auto_resend"),
            _sub(306, "outcome_unknown", "2026-09-17T10:30:00+00:00"),
            _sub(307, "outcome_unknown", "2026-09-17T09:55:00"),
            _sub(308, "outcome_unknown", None),
            _sub(309, "error", "2026-09-17T09:55:00+00:00"),
        ],
    },
    {
        "table": "reservation",
        "columns": ["id", "apartment_id", "uid", "date_from", "date_to", "status", "source",
                    "archived_at", "at_risk_mailed_at", "created_at", "updated_at"],
        "rows": [
            _stay(201, 1, "2026-09-15"),  # at risk, 1 unfiled (lower-case cze not counted)
            _stay(202, 1, "2026-09-10"),  # overdue, 1 unfiled (CZE pending, DEU sent)
            _stay(203, 1, "2026-09-16"),  # 36 h left: not yet; overdue on 09-20
            _stay(204, 1, "2026-09-15"),  # awaiting resend until 10:05, at risk at 11:00
            _stay(205, 1, "2026-09-14"),  # overdue: awaiting does not hide it
            _stay(206, 1, "2026-09-15"),  # one guest awaiting, one not: at risk
            _stay(207, 1, "2026-09-15"),  # batch already resent once: at risk
            _stay(208, 1, "2026-09-15"),  # auto_resend batch past the grace: at risk
            _stay(209, 1, "2026-09-15", mailed="2026-09-16T08:00:00+00:00"),  # mailed before
            _stay(210, 3, "2026-09-15"),  # owner 2, no legal entity
            _stay(211, 1, "2026-09-15", status="cancelled"),  # not watched
            _stay(212, 1, "2026-09-15", archived="2026-09-16"),  # not watched
            _stay(213, 1, "2026-09-15", source="demo"),  # not watched
            _stay(214, 2, "2026-09-15"),  # property switched off
            _stay(215, 1, "2026-09-15"),  # only an archived guest: unknown risk
            _stay(216, 1, "2026-09-15"),  # Czech only: neither list
            _stay(217, 1, "2026-09-08"),  # no guests, 6.5 days overdue: unknown risk
            _stay(218, 1, "2026-09-07"),  # no guests, over 7 days overdue: dropped
            _stay(219, 1, "2026-09-17"),  # no guests, arrives today, 4 days left: no
            _stay(220, 1, "2026-09-18"),  # no guests, not arrived: no
            _stay(221, 1, "2026-09-15"),  # nationality empty and NULL: neither list
            _stay(222, 1, "2026-09-16"),  # anchor from a guest's stay_from (09-14): overdue
            _stay(223, 1, "bad"),  # no anchor: skipped
            _stay(224, 4, "2026-09-15"),  # property name needs escaping
            _stay(225, 5, "2026-09-15"),  # no owner, entity without address
            _stay(226, 1, "2026-09-15"),  # finished in the future: not awaiting
            _stay(227, 1, "2026-09-15"),  # naive finished_at reads as UTC: awaiting
            _stay(228, 1, "2026-09-15"),  # finished_at NULL: not awaiting
            _stay(229, 1, "2026-09-15", mailed=""),  # empty stamp counts as not mailed
            _stay(230, 3, "2026-09-12"),  # no guests, owner 2, overdue: unknown risk
        ],
    },
    {
        "table": "guest",
        "columns": _GUEST_COLUMNS,
        "rows": [
            _guest(1, 201, "deu"),
            _guest(2, 201, "cze"),
            _guest(3, 202, "USA", state="error"),
            _guest(4, 202, "CZE"),
            _guest(5, 202, "DEU", state="sent"),
            _guest(6, 203),
            _guest(7, 204, submission=301),
            _guest(8, 205, submission=302),
            _guest(9, 206, submission=303),
            _guest(10, 206, "FRA", state="blocked"),
            _guest(11, 207, submission=304),
            _guest(12, 208, submission=305),
            _guest(13, 209),
            _guest(14, 210, "UKR"),
            _guest(15, 211),
            _guest(16, 212),
            _guest(17, 213),
            _guest(18, 214),
            _guest(19, 215, archived="2026-09-16"),
            _guest(20, 216, "CZE"),
            _guest(21, 221, ""),
            _guest(22, 221, None),
            _guest(23, 222),
            _guest(24, 222, "CZE", state="sent", stay_from="2026-09-14"),
            _guest(25, 223),
            _guest(26, 224, "ITA"),
            _guest(27, 225, "ESP"),
            _guest(28, 226, submission=306),
            _guest(29, 227, submission=307),
            _guest(30, 228, submission=308),
            _guest(31, 229, submission=309, state="error"),
        ],
    },
    {
        "table": "push_subscription",
        "columns": ["id", "user_account_id", "endpoint_hash", "endpoint_enc", "p256dh_enc",
                    "auth_enc", "lang", "device", "created_at", "last_seen_at"],
        "rows": [
            [501, 1, "h501", "x", "x", "x", "en", "phone", STAMP, STAMP],
            [502, 2, "h502", "x", "x", "x", "en", "phone", STAMP, STAMP],
            [503, 2, "h503", "x", "x", "x", "en", "laptop", STAMP, STAMP],
        ],
    },
]

# T0, T0 + 5 min (204's batch exactly at the 20-minute grace), T0 + 1 h (past
# the grace), and Sunday 2026-09-20 13:05 in Prague (09-16 arrivals overdue).
INSTANTS = [
    "2026-09-17T10:00:00+00:00",
    "2026-09-17T10:05:00+00:00",
    "2026-09-17T11:00:00+00:00",
    "2026-09-20T11:05:00+00:00",
]

HEARTBEATS = [
    "https://hc.example.test/ping/abc",
    "https://hc.example.test/ping/abc/",
    "  https://hc.example.test/ping/abc//  ",
    "",
    "   ",
]


def _seed(db) -> None:
    for table in SEED:
        cols = ", ".join(table["columns"])
        marks = ", ".join("?" for _ in table["columns"])
        for row in table["rows"]:
            db.execute(f"INSERT INTO {table['table']} ({cols}) VALUES ({marks})", row)


def stay_record(stay: dict) -> dict:
    """One stay as the golden records it; the Go test builds the same map."""
    return {
        "reservation_id": stay["reservation_id"],
        "date_from": stay["date_from"],
        "apartment_id": stay["apartment_id"],
        "property": stay["property"],
        "legal_entity_id": stay["legal_entity_id"],
        "owner_user_id": stay["owner_user_id"],
        "workspace": stay["workspace"],
        "mailed_at": stay["mailed_at"],
        "unfiled": stay["unfiled"],
        "awaiting_retry_guests": stay.get("awaiting_retry_guests", 0),
        "awaiting_retry": bool(stay.get("awaiting_retry")),
        "no_guests": bool(stay.get("no_guests")),
        "arrival": stay["arrival"].isoformat(),
        "deadline": stay["deadline"].isoformat(),
        "overdue": bool(stay["overdue"]),
    }


def render() -> str:
    """Seed a fresh database, ask both questions per instant, return the JSON text."""
    from app import config, db, filing_watchdog

    db.init_db()
    _seed(db)
    instants = []
    for at in INSTANTS:
        now = datetime.fromisoformat(at)
        every = filing_watchdog.at_risk_stays(now, include_awaiting_retry=True)
        instants.append({
            "at": at,
            "at_risk": [stay_record(s) for s in every],
            "at_risk_default": [s["reservation_id"] for s in filing_watchdog.at_risk_stays(now)],
            "unknown_risk": [stay_record(s) for s in filing_watchdog.unknown_risk_stays(now)],
        })
    saved = config.HEARTBEAT_FILING_URL
    heartbeats = []
    try:
        for url in HEARTBEATS:
            config.HEARTBEAT_FILING_URL = url
            for at_risk in (False, True):
                heartbeats.append({
                    "url": url,
                    "at_risk": at_risk,
                    "ping": filing_watchdog.heartbeat_url(at_risk),
                })
    finally:
        config.HEARTBEAT_FILING_URL = saved
    golden = {
        "env": GOLDEN_ENV,
        "retry_grace_minutes": int(filing_watchdog.RETRY_GRACE.total_seconds() // 60),
        "seed": SEED,
        "instants": instants,
        "heartbeats": heartbeats,
    }
    return json.dumps(golden, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def prepare_env() -> None:
    """The process environment both golden scripts need, before ``app`` is imported."""
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-golden-"))
    os.environ.setdefault("UBYHOST_DATA_DIR", str(tmp))
    os.environ.setdefault("UBYHOST_DB", str(tmp / "filing_watchdog_golden.sqlite3"))
    os.environ.setdefault("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
    os.environ.update(GOLDEN_ENV)
    sys.path.insert(0, str(APP))


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    prepare_env()
    main()
