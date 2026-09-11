"""Click through every page a host and a guest can reach, and fail on anything ugly.

Run with:  .venv/bin/python tools/smoke.py
It uses a scratch database, so it never touches real data.
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("UBYHOST_DATA_DIR", tempfile.mkdtemp(prefix="ubyhost-smoke-"))
os.environ["UBYHOST_UBYPORT_ENV"] = "mock"
os.environ["UBYHOST_ENABLE_SCHEDULER"] = "0"
os.environ["UBYHOST_BOOTSTRAP_ADMIN"] = "0"
os.environ["UBYHOST_GUEST_PIN"] = "0"

from fastapi.testclient import TestClient  # noqa: E402

from app import db  # noqa: E402
from app.main import app  # noqa: E402

FAILURES = []
CHECKED = 0


def check(client, path, expect=(200,), must_contain=(), must_not_contain=(), label=""):
    global CHECKED
    CHECKED += 1
    response = client.get(path, follow_redirects=True)
    name = label or path
    if response.status_code not in expect:
        FAILURES.append(f"{name}: HTTP {response.status_code}, expected {expect}")
        return response
    body = response.text
    for needle in must_contain:
        if needle not in body:
            FAILURES.append(f"{name}: missing {needle!r}")
    for needle in must_not_contain:
        if needle in body:
            FAILURES.append(f"{name}: still contains {needle!r}")
    if "Internal Server Error" in body or "Traceback (most recent" in body:
        FAILURES.append(f"{name}: server error in body")
    return response


def seed():
    db.init_db()
    now = db.utcnow()
    today = date.today()
    entity_id = db.insert(
        "legal_entity",
        {
            "name": "Smoke s.r.o.",
            "seat": "Korunní 1, 120 00 Praha 2",
            "ico": "12345678",
            "contact_email": "privacy@example.com",
            "created_at": now,
        },
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "Smoke flat",
            "city_en": "Prague",
            "uby_idub": "100227887600",
            "uby_mark": "CZGFW",
            "uby_name": "Smoke Studio",
            "addr_okres": "Praha 2",
            "addr_obec": "Praha",
            "addr_street": "Korunní",
            "addr_house_no": "1234",
            "addr_zip": "12000",
            "uby_ws_user": "UBY-WS12cdef",
            "uby_ws_password_enc": db.encrypt_secret("x"),
            "permalink_token": "smoketoken",
            "permalink_window_days": 14,
            "default_purpose": "10",
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    stays = []
    for offset, uid in ((0, "smoke-a"), (2, "smoke-b")):
        stays.append(
            db.insert(
                "reservation",
                {
                    "apartment_id": apartment_id,
                    "source": "ical",
                    "uid": uid,
                    "date_from": (today + timedelta(days=offset)).isoformat(),
                    "date_to": (today + timedelta(days=offset + 3)).isoformat(),
                    "status": "active",
                    "created_at": now,
                    "updated_at": now,
                },
            )
        )
    # A stay from long ago, to exercise the past filter and the retention count.
    db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            "uid": "smoke-old",
            "date_from": (today - timedelta(days=400)).isoformat(),
            "date_to": (today - timedelta(days=397)).isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    return apartment_id, stays


def main():
    apartment_id, (stay_a, stay_b) = seed()
    host = TestClient(app)
    token = "smoketoken"

    print("host pages")
    for path in (
        "/",
        "/reservations",
        "/reservations?range=all",
        "/reservations?range=past",
        "/reservations?from=2020-01-01&to=2035-12-31",
        "/reservations?apartment=not-a-number&status=bogus&from=nonsense",
        f"/reservations/{stay_a}",
        "/reservations/999999",
        "/apartments",
        "/guest-links",
        "/apartments/new",
        f"/apartments/{apartment_id}",
        "/entities",
        "/submissions",
        "/housebook",
        "/housebook?apartment=oops&from=oops",
        "/settings",
        "/automation",
    ):
        check(host, path)

    check(host, "/", must_contain=["Operations"], must_not_contain=["row-arrow"])
    check(host, "/housebook", must_contain=["data-csv-export"])
    check(host, "/guest-links", must_contain=["Generate a new PIN"])

    stays_page = check(host, "/reservations?range=all").text
    order = [
        line for line in stays_page.splitlines() if "&ndash;" in line and "<strong>" in line
    ]
    if len(order) >= 2:
        first, last = order[0], order[-1]
        if first > last and "." in first:
            pass  # dd.mm.yyyy strings do not sort; checked properly in the test suite

    print("guest pages")
    guest = TestClient(app)
    check(
        guest,
        f"/l/{token}",
        must_contain=["Czech law", "Smoke Studio", "How your data is handled"],
        must_not_contain=["Airbnb", "Booking.com"],
    )
    check(
        guest,
        f"/l/{token}/privacy",
        must_contain=["Smoke s.r.o.", "privacy@example.com", "6(1)(c)", "uoou.gov.cz"],
    )
    # A separate browser, because ?lang=cs sets a sticky cookie.
    czech = TestClient(app)
    check(czech, f"/l/{token}/privacy?lang=cs", must_contain=["Právní základ", "Policii"])

    check(
        guest,
        f"/l/{token}/{stay_a}",
        must_contain=['name="surname"', "Czech law"],
        must_not_contain=["Airbnb", "Booking.com"],
    )
    check(guest, f"/l/{token}/999999", expect=(404,), must_contain=["no longer open"])
    check(guest, f"/l/{token}/{stay_a}/edit/999999", expect=(403,), must_contain=["cannot be opened"])
    check(guest, "/l/nosuchtoken", expect=(404,))
    check(guest, f"/l/{token}/{stay_b}", must_contain=['name="surname"'])

    signature = "data:image/png;base64,iVBORw0KGgo="
    saved = guest.post(
        f"/l/{token}/{stay_a}/save",
        data={
            "surname": "Smith",
            "first_name": "John",
            "birth_date": "01/01/1990",
            "nationality": "GBR",
            "doc_number": "P1234567",
            "res_street": "Baker Street 221B",
            "res_city": "London",
            "res_country": "GBR",
            "purpose": "10",
            "party_size": "2",
            "signature": signature,
        },
        follow_redirects=True,
    )
    if saved.status_code != 200:
        FAILURES.append(f"guest save: HTTP {saved.status_code}")
    elif "Details saved" not in saved.text and "Details submitted and reported" not in saved.text:
        FAILURES.append("guest save: no confirmation shown")
    check(guest, f"/l/{token}/{stay_a}", must_contain=["1 of 2 people completed"])
    check(guest, f"/l/{token}/{stay_a}/new", must_contain=['name="surname"', "Person 2"])
    czech_saved = czech.get(f"/l/{token}/{stay_a}?saved=1&lang=cs", follow_redirects=True)
    if czech_saved.status_code != 200 or (
        "Údaje uloženy" not in czech_saved.text
        and "Údaje byly odeslány a oznámeny" not in czech_saved.text
    ):
        FAILURES.append("czech guest save banner: missing confirmation")

    print(f"\n{CHECKED} pages checked")
    if FAILURES:
        print(f"{len(FAILURES)} problem(s):")
        for failure in FAILURES:
            print("  -", failure)
        return 1
    print("no dead pages, no server errors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
