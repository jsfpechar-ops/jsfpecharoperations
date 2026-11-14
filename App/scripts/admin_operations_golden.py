"""Write go/internal/web/auth/opspage/testdata/admin_operations_golden.json from the real Python page.

Port plumbing for brief 1508 (go-first exception 1). Run from App/ (create the
venv first if missing: python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    .venv/bin/python scripts/admin_operations_golden.py          write the file
    .venv/bin/python scripts/admin_operations_golden.py --check  exit 1 when it is stale

It seeds a throwaway SQLite database with SEED (the Go test seeds PostgreSQL
from the same rows in the JSON), signs in as the admin through TestClient,
freezes the clock of admin_ops, ttlock and ai at NOW and renders
GET /admin/operations for each case. A case keeps visible_lines() of the page
area (div.ui-page): the visible text and the key attributes, not the bytes.
go/internal/web/auth/opspage/page_test.go compares with the same normaliser.
The "helpers" section pins havel.normalise_question, admin_ops.age_minutes and
Jinja's capitalize on fixed inputs. App/tests/test_go_admin_operations_golden.py
fails when the file is stale. Nothing here is real data.
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "auth" / "opspage" / "testdata" / "admin_operations_golden.json"

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)
C = "2026-01-01T00:00:00+00:00"  # created_at of rows whose age the page does not show


def _seed() -> list[dict]:
    """Every row, as {table, rows}. Made up: example.test addresses only."""
    users = [
        {"id": 1, "username": "admin", "email": "admin@example.test", "password_hash": "x", "role": "admin",
         "must_change_password": 0, "created_at": C},
        {"id": 2, "username": "host-anna", "password_hash": "x", "role": "host", "must_change_password": 0, "created_at": C},
        {"id": 3, "username": "bob & Co", "password_hash": "x", "role": "host", "must_change_password": 0, "created_at": C},
        {"id": 4, "username": "zeta", "password_hash": "x", "role": "host", "must_change_password": 0, "created_at": C},
    ]
    entities = [
        {"id": 20, "name": "Anna s.r.o.", "owner_user_id": 2, "contact_email": "anna@example.test", "created_at": C},
        {"id": 21, "name": "Anna bez mailu", "owner_user_id": 2, "contact_email": None, "created_at": C},
        {"id": 22, "name": "Bob <B>", "owner_user_id": 3, "contact_email": "bob@example.test", "created_at": C},
        {"id": 23, "name": "Anna Two", "owner_user_id": 2, "contact_email": "two@example.test", "created_at": C},
    ]
    apartments = [
        {"id": 10, "owner_user_id": 2, "internal_name": "Flat A", "legal_entity_id": 20, "created_at": C},
        {"id": 11, "owner_user_id": 3, "internal_name": "Flat <B>", "legal_entity_id": 22, "created_at": C},
        {"id": 12, "owner_user_id": None, "internal_name": "Orphan", "created_at": C},
        {"id": 13, "owner_user_id": 2, "internal_name": "Archived flat", "created_at": C, "archived_at": C},
        {"id": 14, "owner_user_id": 2, "internal_name": "Off flat", "created_at": C, "active": 0},
    ]

    def res(i, apt, archived=None):
        return {"id": i, "apartment_id": apt, "uid": f"uid-{i}", "date_from": "2026-11-01", "date_to": "2026-11-05",
                "created_at": C, "updated_at": C, "archived_at": archived}

    reservations = [res(100, 10), res(101, 11), res(102, 12), res(103, 10, archived=C), res(104, 10), res(105, 11)]
    reservations += [res(i, 10) for i in range(260, 266)]  # one per door code (reservation_id is unique there)
    submissions = [
        {"id": 500, "apartment_id": 10, "state": "outcome_unknown", "created_at": "2026-11-13T09:00:00+00:00",
         "finished_at": "2026-11-13T09:30:00+00:00"},
        {"id": 501, "apartment_id": 11, "state": "running", "created_at": "2026-11-13T10:00:00+00:00"},
        {"id": 502, "apartment_id": 11, "state": "running", "created_at": "2026-11-13T11:50:00+00:00"},
        {"id": 503, "apartment_id": 12, "state": "running", "created_at": "2026-11-10T12:00:00+00:00"},
        {"id": 504, "apartment_id": 10, "state": "ok", "created_at": "2026-11-12T12:00:00+00:00"},
    ]

    def guest(i, r, state, sub=None, attempts=0, updated="2026-11-12T08:00:00+00:00", archived=None):
        return {"id": i, "reservation_id": r, "submit_state": state, "submission_id": sub, "submit_attempts": attempts,
                "created_at": C, "updated_at": updated, "archived_at": archived}

    guests = [
        guest(1, 100, "pending", sub=500),                      # outcome unknown: severity 3
        guest(2, 101, "blocked", updated="2026-11-11T12:00:00+00:00"),  # rejected: 2
        guest(3, 102, "error", attempts=1, updated="2026-11-13T11:00:00+00:00"),  # retry cap: 1
        guest(4, 100, "error", updated="2026-11-13T11:59:30+00:00"),  # same stay as 1
        guest(5, 103, "error"),                                  # archived stay: not listed
        guest(6, 104, "error", archived=C),                      # archived guest: not listed
        guest(7, 104, "sent", sub=500),                          # sent: not listed
        guest(8, 105, "error", updated="2026-10-01T12:00:00+00:00"),  # error, 43 days
    ]
    feeds = [
        {"id": 30, "apartment_id": 10, "url": "https://cal.example.test/a", "label": "Airbnb", "last_status": "ok",
         "last_checked_at": "2026-11-13T11:00:00+00:00", "created_at": C},
        {"id": 31, "apartment_id": 10, "url": "https://cal.example.test/b", "label": "Booking", "last_status": "error",
         "last_checked_at": "2026-11-13T11:30:00+00:00", "created_at": C},
        {"id": 32, "apartment_id": 11, "url": "https://cal.example.test/c", "label": None, "last_status": "ok",
         "last_sync_at": "2026-11-13T05:00:00+00:00", "created_at": C},
        {"id": 33, "apartment_id": 11, "url": "https://cal.example.test/d", "label": "New", "created_at": C},
        {"id": 34, "apartment_id": 12, "url": "https://cal.example.test/e", "label": "Odd", "last_status": "suspect",
         "last_checked_at": "2026-11-12T12:00:00+00:00", "created_at": C},
        {"id": 35, "apartment_id": 12, "url": "https://cal.example.test/f", "label": "Weird", "last_status": "http_418",
         "last_checked_at": "2026-11-13T11:58:00+00:00", "created_at": C},
        {"id": 36, "apartment_id": 10, "url": "https://cal.example.test/g", "label": "Off", "last_status": "error",
         "active": 0, "created_at": C},
        {"id": 37, "apartment_id": 13, "url": "https://cal.example.test/h", "label": "Archived", "last_status": "error",
         "created_at": C},
        {"id": 39, "apartment_id": 10, "url": "https://cal.example.test/j", "label": "Three and a half hours",
         "last_status": "ok", "last_checked_at": "2026-11-13T08:30:00+00:00", "last_sync_at": C, "created_at": C},
        {"id": 40, "apartment_id": 10, "url": "https://cal.example.test/k", "label": "Two and a half hours",
         "last_status": "ok", "last_checked_at": "2026-11-13T09:30:00+00:00", "created_at": C},
        {"id": 38, "apartment_id": 14, "url": "https://cal.example.test/i", "label": "Inactive flat",
         "last_status": "error", "created_at": C},
    ]
    settings = [
        {"key": "job_last_ok:ical", "value": "2026-11-13T11:30:00+00:00"},
        {"key": "job_last_ok:mail", "value": "2026-11-12T12:00:00+00:00"},
        {"key": "job_last_ok:push", "value": "2026-11-13T11:44:00"},
        {"key": "job_last_ok:retention", "value": "2026-11-12T13:00:00Z"},
        {"key": "job_last_ok:submit", "value": "2026-11-13T11:55:00+00:00"},
        {"key": "job_last_ok:deadlines", "value": "not a time"},
        {"key": "job_last_ok:posthog", "value": "2026-11-13T12:30:00+00:00"},
    ]
    alerts = [
        {"id": 1, "level": "error", "kind": "job_failed", "dedupe_key": "job_failed:submit", "message": "Job failed",
         "created_at": "2026-11-13T11:00:00+00:00"},
        {"id": 2, "level": "warning", "kind": "deadline", "message": "Deadline", "created_at": "2026-11-10T12:00:00+00:00"},
        {"id": 3, "level": "warning", "kind": "deadline", "message": "Deadline", "created_at": "2026-11-12T12:00:00+00:00"},
        {"id": 4, "level": "warning", "kind": "zz_unknown_kind", "message": "Other", "created_at": "2026-11-13T10:30:00+00:00"},
        {"id": 5, "level": "warning", "kind": "incident_review", "message": "Repeated guest PIN failures <b>",
         "detail": "7 guest links were rate-limited in the last 24 hours.", "created_at": "2026-11-13T07:00:00+00:00"},
        {"id": 6, "level": "warning", "kind": "incident_review", "message": "Second review", "detail": None,
         "created_at": "2026-11-13T08:00:00+00:00"},
        {"id": 7, "level": "error", "kind": "deadline", "message": "Old", "created_at": C, "resolved_at": C},
        {"id": 8, "level": "error", "kind": "job_failed", "dedupe_key": "job_failed:mail", "message": "Gone",
         "created_at": C, "resolved_at": C},
    ]
    outbox = [
        {"id": 40, "idempotency_key": "k40", "kind": "guest_link", "state": "failed", "attempts": 3,
         "created_at": "2026-11-13T09:00:00+00:00", "updated_at": "2026-11-13T09:00:00+00:00"},
        {"id": 41, "idempotency_key": "k41", "kind": "login_link", "state": "bounced", "attempts": 1,
         "created_at": "2026-11-11T09:00:00+00:00", "updated_at": "2026-11-11T09:00:00+00:00"},
        {"id": 42, "idempotency_key": "k42", "kind": "digest", "state": "queued", "attempts": 0,
         "created_at": "2026-11-13T11:00:00+00:00", "updated_at": "2026-11-13T11:00:00+00:00"},
        {"id": 43, "idempotency_key": "k43", "kind": "digest", "state": "queued", "attempts": 0,
         "created_at": "2026-11-13T11:45:00+00:00", "updated_at": "2026-11-13T11:45:00+00:00"},
        {"id": 44, "idempotency_key": "k44", "kind": "receipt", "state": "sending", "attempts": 2,
         "created_at": "2026-11-13T11:50:00+00:00", "updated_at": "2026-11-13T11:00:00+00:00"},
        {"id": 45, "idempotency_key": "k45", "kind": "receipt", "state": "sent", "attempts": 1,
         "created_at": "2026-11-01T11:00:00+00:00", "updated_at": "2026-11-01T11:00:00+00:00"},
        {"id": 46, "idempotency_key": "k46", "kind": "complaint_x", "state": "complained", "attempts": 1,
         "created_at": "2026-10-01T11:00:00+00:00", "updated_at": "2026-10-01T11:00:00+00:00"},
    ]

    def code(i, state, issued=None):
        return {"id": i, "reservation_id": i + 200, "apartment_id": 10, "lock_id": "L1", "state": state,
                "issued_at": issued, "created_at": C, "updated_at": C}

    codes = [code(60, "issued", "2026-11-02T10:00:00+00:00"), code(61, "issued", "2026-11-13T10:00:00+00:00"),
             code(62, "issued", "2026-10-30T10:00:00+00:00"), code(63, "failed"), code(64, "revoke_failed"),
             code(65, "pending")]
    usage = [{"month": "2026-11", "provider": "ttlock", "calls": 25000},
             {"month": "2026-10", "provider": "ttlock", "calls": 999}]

    def gap(i, at, lang, page, kind, q):
        return {"id": i, "created_at": at, "lang": lang, "page": page, "kind": kind, "question": q}

    gaps = [
        gap(70, "2026-11-01T00:00:00+00:00", "en", "stays", "escalate", "How do I add a stay?"),
        gap(71, "2026-11-03T00:00:00+00:00", "cs", "add_stay", "not_helped", "how do I   add a STAY"),
        gap(72, "2026-11-05T00:00:00+00:00", "en", "stays", "fail", "How do I add a stay!!"),
        gap(73, "2026-11-06T00:00:00+00:00", "vi", None, "escalate", "Tôi đổi mã PIN thế nào?"),
        gap(74, "2026-11-07T00:00:00+00:00", "en", "reports", "not_helped", "Where is the <report>?"),
        gap(75, "2026-11-07T00:00:00+00:00", "en", "unknown_page", "escalate", "Straße ändern"),
        gap(76, "2026-11-08T00:00:00+00:00", "de", "smart_locks", "escalate", "STRASSE ändern"),
        gap(77, "2026-11-09T00:00:00+00:00", "en", "dashboard", "escalate", "???"),
        gap(78, "2026-11-04T00:00:00+00:00", "en", "reports", "escalate", "where is the report"),
        gap(79, "2026-11-04T00:00:00+00:00", "en", "dashboard", "fail", "Where is the report"),
    ]
    stats = [{"day": "2026-11-13", "kind": "answer", "count": 5}, {"day": "2026-10-20", "kind": "answer", "count": 2},
             {"day": "2026-10-15", "kind": "answer", "count": 100}, {"day": "2026-11-01", "kind": "escalate", "count": 3},
             {"day": "2026-11-02", "kind": "guardrail_fail", "count": 0}]
    ai_usage = [{"day": "2026-11-05", "feature": "havel", "key": "", "requests": 3, "input_tokens": 12_000_000,
                 "cache_write_tokens": 0, "cache_read_tokens": 1_000_000, "output_tokens": 1_500_000},
                {"day": "2026-10-31", "feature": "havel", "key": "", "requests": 3, "input_tokens": 99_000_000,
                 "cache_write_tokens": 0, "cache_read_tokens": 0, "output_tokens": 0}]
    incidents = [
        {"id": 90, "detected_at": "2026-11-10T08:00:00+00:00", "reported_by": "ops", "summary": "Laptop lost <x>",
         "data_categories": "names", "affected_owner_ids": "[2, 3]", "approx_subjects": 12, "risk_level": "high",
         "contained_at": "2026-11-10T09:00:00+00:00", "notes": "", "created_at": C, "updated_at": C},
        {"id": 91, "detected_at": "2026-11-12T08:00:00+00:00", "reported_by": "", "summary": "Mail to wrong host",
         "data_categories": "", "affected_owner_ids": "[]", "approx_subjects": None, "risk_level": None,
         "notes": "", "created_at": C, "updated_at": C},
        {"id": 92, "detected_at": "2026-11-10T08:00:00+00:00", "reported_by": "", "summary": "Same day, higher id",
         "data_categories": None, "affected_owner_ids": "not json", "approx_subjects": 0, "risk_level": "low",
         "closed_at": "2026-11-11T08:00:00+00:00", "notes": "", "created_at": C, "updated_at": C},
        {"id": 93, "detected_at": "2026-11-01T08:00:00+00:00", "reported_by": "", "summary": "Owner list of strings",
         "data_categories": "ids", "affected_owner_ids": "[\"4\", 99]", "approx_subjects": 1, "risk_level": "none",
         "notes": "", "created_at": C, "updated_at": C},
    ]
    accepted = [{"id": i + 1, "user_account_id": 1, "document": doc, "version": "{ver}", "accepted_at": C,
                 "method": "clickwrap"} for i, doc in enumerate(("terms", "privacy", "dpa"))]
    return [
        {"table": "user_account", "rows": users}, {"table": "legal_acceptance", "rows": accepted},
        {"table": "legal_entity", "rows": entities},
        {"table": "apartment", "rows": apartments}, {"table": "reservation", "rows": reservations},
        {"table": "submission", "rows": submissions}, {"table": "guest", "rows": guests},
        {"table": "ical_feed", "rows": feeds}, {"table": "settings", "rows": settings},
        {"table": "alert", "rows": alerts}, {"table": "email_outbox", "rows": outbox},
        {"table": "door_code", "rows": codes}, {"table": "lock_api_usage", "rows": usage},
        {"table": "havel_gap", "rows": gaps}, {"table": "havel_stats", "rows": stats},
        {"table": "ai_usage", "rows": ai_usage}, {"table": "security_incident", "rows": incidents},
    ]


KEEP = ("user_account", "legal_acceptance")

# name, language, seed ("full" or "users": only the KEEP tables), env. The env keys are the ones the page reads.
ENV_ON = {"UBYHOST_DOOR_CODES": "1", "UBYHOST_DOOR_CODES_LIVE": "1", "UBYHOST_TTLOCK_MONTHLY_CALLS": "30000",
          "UBYHOST_AI_FEATURES": "havel", "UBYHOST_ANTHROPIC_API_KEY": "test-key-not-real",
          "UBYHOST_AI_MONTHLY_USD_HAVEL": "4", "UBYHOST_ICAL_POLL_MINUTES": "60", "UBYHOST_SUBMIT_SWEEP_MINUTES": "10"}
ENV_OFF = {"UBYHOST_ICAL_POLL_MINUTES": "45", "UBYHOST_SUBMIT_SWEEP_MINUTES": "5"}
ENV_TEST_MODE = {"UBYHOST_DOOR_CODES": "true", "UBYHOST_TTLOCK_MONTHLY_CALLS": "40000",
                 "UBYHOST_AI_FEATURES": "havel", "UBYHOST_AI_MONTHLY_USD_HAVEL": "0"}
CASES = [
    ("full, door codes live, Havel on", "en", "full", ENV_ON),
    ("full in Czech, everything off", "cs", "full", ENV_OFF),
    ("full in Vietnamese, door codes test mode, no AI key", "vi", "full", ENV_TEST_MODE),
    ("empty in English", "en", "users", ENV_ON),
    ("empty in Czech", "cs", "users", ENV_OFF),
]

NORMALISE = ["How do I add a stay?", "  how do I   add a STAY ", "Straße", "ΣΊΣΥΦΟΣ ς", "ﬁle №5 ½", "Tab\tand\x1cfs",
             "a_b-c.d", "İstanbul", "é café", "???", "", "ǅungla", "x y z"]
AGES = ["2026-11-13T11:00:00+00:00", "2026-11-13T11:00:00Z", "2026-11-13T11:00:00", "2026-11-13 10:00:00+01:00",
        "2026-11-13T11:59:59.999999+00:00", "2026-11-13", "2026-11-14T00:00:00+00:00", " 2026-11-13T10:00:00+00:00 ",
        "2026-11-13T11:00", "2026-11-13T11:00:30.5+00:00", "garbage", "", None, "2026-11-13T12:00:00-02:00"]
CAPITALIZE = ["calendar sync", "Mail SENDING", "ěščř job", "", "x"]

# visible_lines: keep in step with visibleLines in go/internal/web/auth/opspage/page_test.go.
DROP = [re.compile(p, re.S | re.I) for p in (
    r"<!--.*?-->", r"<script\b.*?</script>", r"<style\b.*?</style>", r"<svg\b.*?</svg>")]
TOKEN = re.compile(r"<[^>]*>|[^<]+")
TAG = re.compile(r"^<[ \t\n\r\f\v]*(/?)([A-Za-z][A-Za-z0-9]*)")
ATTR = re.compile(
    r"""([^ \t\n\r\f\v=/>"']+)(?:[ \t\n\r\f\v]*=[ \t\n\r\f\v]*(?:"([^"]*)"|'([^']*)'|([^ \t\n\r\f\v>"']+)))?""")
SPACE = re.compile(r"[ \t\n\r\f\v]+")
KEPT = {"id", "href", "action", "method", "name", "value", "type", "selected", "checked", "required", "for",
        "aria-current", "open", "disabled", "class", "data-label", "placeholder", "inputmode", "data-turbo",
        "aria-controls"}


def visible_lines(page: str) -> list[str]:
    """The page area as lines: each text run, and each tag that has a KEPT attribute."""
    start = page.find('<div class="ui-page"')
    if start < 0:
        return []
    page = page[start:]
    end = page.find('<div class="page-skeleton"')
    if end >= 0:
        page = page[:end]
    for pattern in DROP:
        page = pattern.sub("", page)
    out = []
    skip = False  # inside the header back link: Python shows an icon, Go a label (layout gap)
    for tok in TOKEN.findall(page):
        if not tok.startswith("<"):
            text = SPACE.sub(" ", html.unescape(tok)).strip(" ")
            if text and not skip:
                out.append(text)
            continue
        m = TAG.match(tok)
        if not m:
            continue
        name = m.group(2).lower()
        if m.group(1) == "/":
            if name == "a":
                skip = False
            continue
        attrs = {}
        for a in ATTR.finditer(tok[m.end():]):
            key = a.group(1).lower()
            has_value = "=" in a.group(0)
            value = SPACE.sub(" ", html.unescape((a.group(2) or "") + (a.group(3) or "") + (a.group(4) or ""))).strip(" ")
            attrs[key] = (has_value, value)
        if "ui-ph-back" in attrs.get("class", (False, ""))[1].split():
            skip = True
        if attrs.get("name", (False, ""))[1] == "_csrf":
            attrs["value"] = (True, "*")
        parts = [k + ("=" + v if has else "") for k, (has, v) in sorted(attrs.items()) if k in KEPT]
        if parts:
            out.append("<" + name + " " + " ".join(parts) + ">")
    return out


class _Frozen(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW if tz is None else NOW.astimezone(tz)


def _apply_env(env: dict) -> None:
    """Set the config values the page reads, as config.py would read env."""
    from app import config

    flag = lambda k: env.get(k, "0") in ("1", "true", "yes")  # noqa: E731
    config.DOOR_CODES_ENABLED = flag("UBYHOST_DOOR_CODES")
    config.DOOR_CODES_LIVE = flag("UBYHOST_DOOR_CODES_LIVE")
    config.TTLOCK_MONTHLY_CALLS = int(env.get("UBYHOST_TTLOCK_MONTHLY_CALLS", "30000"))
    config.ICAL_POLL_MINUTES = int(env.get("UBYHOST_ICAL_POLL_MINUTES", "60"))
    config.SUBMIT_SWEEP_MINUTES = int(env.get("UBYHOST_SUBMIT_SWEEP_MINUTES", "10"))
    config.AI_FEATURES = frozenset(
        p.strip().lower() for p in env.get("UBYHOST_AI_FEATURES", "").split(",") if p.strip())
    config.ANTHROPIC_API_KEY = env.get("UBYHOST_ANTHROPIC_API_KEY", "").strip()
    for key in [k for k in os.environ if k.startswith("UBYHOST_AI_MONTHLY_USD_")]:
        del os.environ[key]
    for key, value in env.items():
        if key.startswith("UBYHOST_AI_MONTHLY_USD_"):
            os.environ[key] = value


def render() -> str:
    from fastapi.testclient import TestClient

    from app import acceptance, admin_ops, ai, db, havel, incidents, login_link, scheduler, ttlock
    from app.main import app

    db.init_db()
    seed = _seed()
    tables = [t["table"] for t in seed]

    versions = acceptance.current_versions()
    for row in seed[1]["rows"]:
        row["version"] = versions[row["document"]]

    def load(which: str) -> None:
        """The users and their acceptances stay (the sessions point at them); every other table is
        emptied and, for "full", seeded. "first" seeds everything."""
        for table in reversed(tables):
            if table not in KEEP or which == "first":
                db.execute(f"DELETE FROM {table}")
        for table in seed:
            if table["table"] in KEEP and which != "first":
                continue
            if which == "users" and table["table"] not in KEEP:
                continue
            for row in table["rows"]:
                cols = ", ".join(row)
                marks = ", ".join("?" for _ in row)
                db.execute(f"INSERT INTO {table['table']} ({cols}) VALUES ({marks})", list(row.values()))

    load("first")

    def csrf(client) -> str:
        page = client.get("/l/does-not-exist").text
        return re.search(r'<meta name="csrf-token" content="([^"]*)"', page).group(1)

    def admin_client(lang):
        client = TestClient(app)
        client.cookies.set("ubyhost_lang", lang)
        account = db.query_one("SELECT * FROM user_account WHERE username = ?", ("admin",))
        response = client.post("/login/link", data={"t": login_link.issue(account), "_csrf": csrf(client)},
                               follow_redirects=False)
        assert response.status_code == 303 and "/login" not in response.headers["location"]
        return client

    clients = {lang: admin_client(lang) for lang in ("en", "cs", "vi")}
    for module in (admin_ops, ttlock, ai):
        module.datetime = _Frozen
    cases = []
    for name, lang, which, env in CASES:
        load(which)
        _apply_env(env)
        response = clients[lang].get("/admin/operations", follow_redirects=False)
        cases.append({"name": name, "lang": lang, "seed": which, "env": env,
                      "status": response.status_code, "lines": visible_lines(response.text)})
    load("full")
    drafts = [[row["id"], incidents.controller_notification_draft(row)] for row in incidents.list_all()]
    helpers = {
        "drafts": drafts,
        "normalise": [[q, havel.normalise_question(q)] for q in NORMALISE],
        "age": [[v, admin_ops.age_minutes(v, NOW)] for v in AGES],
        "capitalize": [[s, s.capitalize()] for s in CAPITALIZE],
        "late": [[m, scheduler.late_after_minutes(m)] for m in (1, 5, 14, 15, 60)],
    }
    golden = {"now": NOW.isoformat(), "versions": versions, "seed": seed, "cases": cases, "helpers": helpers}
    return json.dumps(golden, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main(argv: list[str]) -> int:
    text = render()
    if "--check" in argv:
        if OUT.read_text(encoding="utf-8") == text:
            return 0
        print(f"stale: {OUT}; run scripts/admin_operations_golden.py")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(APP.parent)}")
    return 0


if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-golden-"))
    os.environ.setdefault("UBYHOST_DATA_DIR", str(tmp))
    os.environ.setdefault("UBYHOST_DB", str(tmp / "admin_operations_golden.sqlite3"))
    os.environ.setdefault("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
    sys.path.insert(0, str(APP))
    sys.exit(main(sys.argv[1:]))
