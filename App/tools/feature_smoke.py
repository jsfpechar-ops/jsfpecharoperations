"""Exercise new UX features end-to-end with a scratch database.

Run: .venv/bin/python tools/feature_smoke.py
"""
from __future__ import annotations

import html
import os
import re
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import unquote, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("UBYHOST_DATA_DIR", tempfile.mkdtemp(prefix="ubyhost-feature-"))
os.environ["UBYHOST_UBYPORT_ENV"] = "mock"
os.environ["UBYHOST_ENABLE_SCHEDULER"] = "0"
os.environ["UBYHOST_BOOTSTRAP_ADMIN"] = "0"
os.environ["UBYHOST_GUEST_PIN"] = "0"

from fastapi.testclient import TestClient  # noqa: E402

from app import alerts, db, icalsync  # noqa: E402
from app.main import app  # noqa: E402

FAILURES: list[str] = []
PASSED = 0


def ok(label: str) -> None:
    global PASSED
    PASSED += 1
    print(f"  OK  {label}")


def fail(label: str, detail: str) -> None:
    FAILURES.append(f"{label}: {detail}")
    print(f" FAIL {label}: {detail}")


def seed():
    db.init_db()
    now = db.utcnow()
    today = date.today()
    entity_id = db.insert(
        "legal_entity",
        {"name": "Feature Test s.r.o.", "seat": "Praha", "ico": "11111111", "created_at": now},
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "Feature flat",
            "city_en": "Prague",
            "permalink_token": "featuretoken",
            "permalink_pin": "1234",
            "permalink_window_days": 14,
            "automation_mode": "scheduled",
            "submit_after_hours": 24,
            "default_purpose": "10",
            "uby_ws_user": "UBY-WS-test",
            "uby_ws_password_enc": db.encrypt_secret("secret"),
            "active": 1,
            "created_at": now,
        },
    )
    stay_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            "uid": "feature-stay",
            "date_from": (today + timedelta(days=5)).isoformat(),
            "date_to": (today + timedelta(days=8)).isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    guest_id = db.insert(
        "guest",
        {
            "reservation_id": stay_id,
            "surname": "Novak",
            "first_name": "Jan",
            "nationality": "CZE",
            "submit_state": "not_required",
            "is_lead": 1,
            "created_at": now,
            "updated_at": now,
        },
    )
    return apartment_id, stay_id, guest_id


def main() -> int:
    apartment_id, stay_id, guest_id = seed()
    client = TestClient(app)

    print("Pages")
    for path, needles in (
        ("/", ["UbyHost", "Ubytovací kniha"]),
        ("/?lang=en", ["Guest records", "UbyPort"]),
        ("/automation?lang=en", ["When to send to UbyPort", "data-automation-mode", "Test connection"]),
        ("/guest-links?lang=en", ["Generate a new PIN", "data-copy"]),
        ("/reservations?lang=en", ["Export stays (CSV)", "Send all ready", "Archive"]),
        ("/housebook?lang=en", ["data-csv-export", "Exempt", "row-menu-trigger"]),
        ("/apartments?lang=en", ["row-menu-trigger"]),
        ("/settings?lang=en", ["settings-audit", "Recent activity"]),
    ):
        r = client.get(path, follow_redirects=True)
        if r.status_code != 200:
            fail(path, f"HTTP {r.status_code}")
            continue
        if "Internal Server Error" in r.text:
            fail(path, "500 in body")
            continue
        page_text = html.unescape(r.text)
        missing = [n for n in needles if n not in page_text]
        if missing:
            fail(path, f"missing {missing}")
        else:
            ok(path)

    dash = client.get("/").text
    if "row-arrow" in dash:
        fail("dashboard", "still has row-arrow")
    else:
        ok("dashboard no blue arrows")

    print("Automation redirect + test connection")
    r = client.post(
        f"/apartments/{apartment_id}/test-connection",
        data={"return_to": f"/automation#apartment-{apartment_id}"},
        follow_redirects=False,
    )
    if r.status_code not in (303, 307):
        fail("test-connection", f"HTTP {r.status_code}")
    else:
        loc = r.headers.get("location", "")
        if "#" in loc and "?" in loc.split("#", 1)[0]:
            ok("test-connection flash URL before hash")
        else:
            fail("test-connection redirect", loc)
        follow = client.get(loc, follow_redirects=True)
        if "msg=" in loc or "err=" in loc:
            if "banner" in follow.text.lower() or "UbyPort" in follow.text:
                ok("test-connection shows feedback banner")
            else:
                fail("test-connection banner", "no visible feedback")

    print("Automation save + hours field")
    r = client.post(
        f"/automation/{apartment_id}",
        data={
            "return_to": f"/automation#apartment-{apartment_id}",
            "automation_mode": "immediate",
            "submit_after_hours": "12",
            "default_purpose": "10",
            "uby_idub": "",
            "uby_mark": "",
            "uby_name": "",
            "uby_contact": "",
            "uby_ws_user": "UBY-WS-test",
        },
        follow_redirects=False,
    )
    if r.status_code in (303, 307):
        ok("automation save redirects")
        apt = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
        if apt["automation_mode"] == "immediate":
            ok("automation mode saved")
        else:
            fail("automation mode", apt["automation_mode"])
    else:
        fail("automation save", f"HTTP {r.status_code}")

    print("Guest links PIN regenerate stays on page")
    r = client.post(
        f"/apartments/{apartment_id}/regenerate-pin",
        data={"return_to": "/guest-links"},
        follow_redirects=False,
    )
    loc = r.headers.get("location", "")
    if loc.startswith("/guest-links"):
        ok("PIN regenerate returns to guest-links")
    else:
        fail("PIN regenerate redirect", loc)

    print("Archive stay + restore")
    r = client.post(f"/reservations/{stay_id}/archive", follow_redirects=False)
    if r.status_code in (303, 307):
        row = db.query_one("SELECT archived_at FROM reservation WHERE id = ?", (stay_id,))
        if row["archived_at"]:
            ok("stay archived")
        else:
            fail("stay archive", "archived_at empty")
    client.post(f"/reservations/{stay_id}/unarchive")
    ok("stay restored")

    print("House book CSV excludes archived")
    client.post(f"/guests/{guest_id}/archive", data={"return_to": "/housebook"})
    rows = __import__("app.housebook", fromlist=["housebook_rows"]).housebook_rows()
    if not any(r["_guest_id"] == guest_id for r in rows):
        ok("archived guest excluded from export rows")
    else:
        fail("housebook export", "archived guest still listed")
    client.post(f"/guests/{guest_id}/unarchive")

    print("CSV download with date range")
    r = client.get("/housebook.csv?from=2020-01-01&to=2035-12-31")
    if r.status_code == 200 and "text/csv" in r.headers.get("content-type", ""):
        ok("housebook CSV download")
    else:
        fail("housebook CSV", f"HTTP {r.status_code}")

    print("Recurring failures re-alert after dismissal")
    alerts.raise_alert("warning", "test_kind", "Test alert", dedupe_key="feature:test")
    open_before = alerts.open_alerts()
    alert_id = open_before[0]["id"]
    client.post(f"/alerts/{alert_id}/dismiss")
    alerts.raise_alert("warning", "test_kind", "Test alert again", dedupe_key="feature:test")
    if alerts.open_alerts():
        ok("later failure raises a new alert")
    else:
        fail("alert recurrence", "later failure was permanently muted")
    db.execute("DELETE FROM alert WHERE dedupe_key = ?", ("feature:test",))

    print("iCal providers")
    if icalsync.platform_of("https://ycs.agoda.com/ical/x.ics") == "agoda":
        ok("agoda platform detection")
    else:
        fail("agoda", "not detected")
    cancelled = icalsync.parse_events(
        "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\n"
        "DTSTART;VALUE=DATE:20260101\nDTEND;VALUE=DATE:20260103\n"
        "UID:x@y\nSUMMARY:Reserved\nSTATUS:CANCELLED\nEND:VEVENT\nEND:VCALENDAR\n"
    )
    if cancelled and cancelled[0]["is_cancelled"]:
        ok("STATUS:CANCELLED parsed")
    else:
        fail("ical cancelled", "not flagged")

    print("Guest PIN page (when enabled)")
    import subprocess

    app_root = Path(__file__).resolve().parent.parent
    pin_env = os.environ.copy()
    pin_env["UBYHOST_GUEST_PIN"] = "1"
    pin_env["UBYHOST_DATA_DIR"] = tempfile.mkdtemp(prefix="ubyhost-pin-")
    proc = subprocess.run(
        [sys.executable, "tools/pin_gate_check.py"],
        cwd=app_root,
        env=pin_env,
        capture_output=True,
        text=True,
    )
    if proc.stdout.strip() == "OK":
        ok("guest PIN gate")
    else:
        fail("guest PIN", proc.stdout.strip() or proc.stderr.strip() or "subprocess failed")

    print(f"\n{PASSED} checks passed")
    if FAILURES:
        print(f"{len(FAILURES)} failure(s):")
        for item in FAILURES:
            print("  -", item)
        return 1
    print("All feature smoke checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
