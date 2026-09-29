"""Click through every page a host and a guest can reach, and fail on anything ugly.

Run with:  .venv/bin/python tools/smoke.py [http://host:port]
It uses a scratch database, so it never touches real data.

With a URL the run is a real HTTP client against a real server - the server has
to answer, has to serve the data seeded below, and has to render every page.
That is the mode CI uses, because a smoke run that drives the app in-process
cannot fail when the server never booted. The URL is therefore not decoration:
if the server is down, or answers on a different database, this exits non-zero.
"""
from __future__ import annotations

import base64
import io
import os
import re
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("UBYHOST_DATA_DIR", tempfile.mkdtemp(prefix="ubyhost-smoke-"))
os.environ["UBYHOST_UBYPORT_ENV"] = "mock"
os.environ["UBYHOST_ENABLE_SCHEDULER"] = "0"
os.environ["UBYHOST_BOOTSTRAP_ADMIN"] = "0"
os.environ["UBYHOST_GUEST_PIN"] = "0"

import httpx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app import claim, db, i18n, mail  # noqa: E402
from app.landing_i18n import LANDING_STRINGS  # noqa: E402
from app.routes import guest as guest_routes  # noqa: E402
from app.main import app  # noqa: E402

FAILURES = []
CHECKED = 0

# Minimal valid PNG for passport-photo upload in guest form smoke.
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8"
    "z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

# The public permalink the seeded apartment answers on, shared by seed() and the
# checks so a rerun can recognise and clear its own fixtures.
SMOKE_TOKEN = "smoketoken"


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


def csrf_field(client, token):
    """The CSRF token a rendered guest page carries, with its cookie in the jar.

    Guest POSTs need the proof in every deployment, so the smoke run has to
    load a page first, exactly like a browser.
    """
    page = client.get(f"/l/{token}")
    match = re.search(r'<meta name="csrf-token" content="([^"]*)"', page.text)
    if not match:
        FAILURES.append(f"csrf: /l/{token} rendered no csrf-token meta tag")
        return {}
    return {"_csrf": match.group(1)}


def seed():
    db.init_db()
    # A rerun can land in the same scratch database (CI passes a data directory
    # in, so the server and this script agree on it), so clear this run's
    # fixtures first. Guests and reservations go with the apartment.
    previous = db.query_one(
        "SELECT id FROM apartment WHERE permalink_token = ?", (SMOKE_TOKEN,)
    )
    if previous:
        db.execute("DELETE FROM apartment WHERE id = ?", (previous["id"],))
        db.execute("DELETE FROM legal_entity WHERE name = ?", ("Smoke s.r.o.",))
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
            "permalink_token": SMOKE_TOKEN,
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


def claim_stay(client, token, reservation_id, email, party_size=2):
    """Open the guest forms the way the configured mail backend allows.

    With mail disabled the guest declares the headcount behind the PIN and no
    e-mail is collected, so only the claim-enabled build has a magic link.
    """
    if not mail.mail_enabled():
        declared = client.post(
            f"/l/{token}/{reservation_id}/party",
            data={"party_size": str(party_size), **csrf_field(client, token)},
            follow_redirects=False,
        )
        if declared.status_code != 303:
            FAILURES.append(
                f"party {reservation_id}: HTTP {declared.status_code}"
            )
        return

    reservation = db.query_one(
        "SELECT * FROM reservation WHERE id = ?", (reservation_id,)
    )
    apartment = db.query_one(
        "SELECT * FROM apartment WHERE permalink_token = ?", (token,)
    )
    ok, error, secret = claim.start_claim(
        reservation,
        apartment,
        email=email,
        party_size=party_size,
        lang="en",
    )
    if not ok:
        FAILURES.append(f"claim {reservation_id}: {error}")
        return
    # GET only renders the confirmation page. The POST is what assigns the stay.
    check(
        client,
        f"/l/{token}/{reservation_id}/claim#c={secret}",
        must_contain=["Yes, this is my stay"],
    )
    confirmed = client.post(
        f"/l/{token}/{reservation_id}/claim/confirm",
        data={"secret": secret, **csrf_field(client, token)},
        follow_redirects=False,
    )
    if confirmed.status_code != 303:
        FAILURES.append(
            f"claim {reservation_id}: confirmation HTTP {confirmed.status_code}"
        )


def base_url(url: Optional[str] = None) -> Optional[str]:
    """Probe the server the run was pointed at and return its base URL.

    ``None`` means "no URL was given" - drive the app in-process instead. The
    probe is ``/healthz``, the same check the deploy does, so a server that is
    up but unhealthy stops the run here rather than as a pile of page failures.
    """
    if not url:
        print("smoke: no URL given, driving the app in-process")
        return None
    base = url.rstrip("/")
    try:
        probe = httpx.get(f"{base}/healthz", timeout=15)
    except httpx.HTTPError as exc:
        print(f"smoke: {base} is not answering: {type(exc).__name__}: {exc}")
        raise SystemExit(1)
    if probe.status_code != 200:
        print(f"smoke: {base}/healthz returned HTTP {probe.status_code}")
        raise SystemExit(1)
    print(f"smoke: driving the server at {base}")
    return base


def browser(base: Optional[str]):
    """One browser with its own cookie jar, on the server or in-process."""
    if base is None:
        return TestClient(app)
    return httpx.Client(base_url=base, timeout=30)


def main(url=None):
    # Contact the server before seeding: a URL that does not answer is the
    # headline failure, and it should not be buried under fixture work.
    base = base_url(url)
    host = browser(base)
    apartment_id, (stay_a, stay_b) = seed()
    token = SMOKE_TOKEN

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

    check(
        host,
        "/",
        must_contain=["UbyHost", LANDING_STRINGS["cs"]["landing.footer.guestbook"]],
        must_not_contain=["row-arrow"],
    )
    check(
        host,
        "/?lang=en",
        must_contain=["UbyPort", LANDING_STRINGS["en"]["landing.benefit.calendar.title"]],
        must_not_contain=["row-arrow"],
    )
    check(host, "/housebook?lang=en", must_contain=["data-csv-export"])
    check(host, "/guest-links?lang=en", must_contain=["Generate a new PIN"])

    stays_page = check(host, "/reservations?range=all").text
    order = [
        line for line in stays_page.splitlines() if "&ndash;" in line and "<strong>" in line
    ]
    if len(order) >= 2:
        first, last = order[0], order[-1]
        if first > last and "." in first:
            pass  # dd.mm.yyyy strings do not sort; checked properly in the test suite

    print("guest pages")
    # A guest who has made no choice gets Czech: that is the page default
    # (host_i18n.PUBLIC_DEFAULT_LANGUAGE), not English. English is one click
    # away, and both are asserted below so neither default can rot unnoticed.
    # The cookie is the guest's own, not the host's: the two share a browser
    # and a guest choosing English must not switch the host's UI.
    guest = browser(base)
    guest.cookies.set(guest_routes.LANG_COOKIE, "en")
    default = browser(base)
    check(
        default,
        f"/l/{token}",
        must_contain=[
            "Který pobyt je váš?",
            "To je můj pobyt",
            "Jak nakládáme s vašimi údaji",
        ],
    )
    check(default, f"/l/{token}/privacy", must_contain=["Nezbytné cookies"])
    check(
        guest,
        f"/l/{token}",
        must_contain=[
            "Czech law",
            "Smoke flat",
            "How your data is handled",
            "Which stay is yours?",
            "That’s my stay",
        ],
        must_not_contain=["Airbnb", "Booking.com", "Smoke Studio"],
    )
    privacy_expected = [
        "Smoke s.r.o.",
        "privacy@example.com",
        "6(1)(c)",
        "uoou.gov.cz",
        "Necessary cookies",
    ]
    privacy_absent = ["Temporary passport photo"]
    if mail.mail_enabled():
        privacy_expected.append("E-mail messages and masking")
    else:
        privacy_expected.append("does not collect your e-mail")
        privacy_absent.append("E-mail messages and masking")
    check(
        guest,
        f"/l/{token}/privacy",
        must_contain=privacy_expected,
        must_not_contain=privacy_absent,
    )
    # A separate browser, because ?lang=cs sets a sticky cookie.
    czech = browser(base)
    check(czech, f"/l/{token}/privacy?lang=cs", must_contain=["Právní základ", "Policii"])

    entry_marker = 'name="guest_email"' if mail.mail_enabled() else 'name="surname"'
    check(
        guest,
        f"/l/{token}/{stay_a}",
        must_contain=[entry_marker, "Czech law"],
        must_not_contain=["Airbnb", "Booking.com"],
    )
    check(guest, f"/l/{token}/999999", expect=(404,), must_contain=["no longer open"])
    check(guest, "/l/nosuchtoken", expect=(404,))
    check(guest, f"/l/{token}/{stay_b}", must_contain=[entry_marker])

    claim_stay(guest, token, stay_a, "lead@example.test")
    check(
        guest,
        f"/l/{token}/{stay_a}",
        must_contain=['name="surname"', "Legal information", "legal_ack"],
    )
    check(
        guest,
        f"/l/{token}/{stay_a}/edit/999999",
        expect=(403,),
        must_contain=["cannot be opened"],
    )
    claim_stay(guest, token, stay_b, "other@example.test")
    check(guest, f"/l/{token}/{stay_b}", must_contain=['name="surname"'])

    signature_buffer = io.BytesIO()
    Image.new("RGB", (10, 10), "white").save(signature_buffer, "PNG")
    signature = "data:image/png;base64," + base64.b64encode(
        signature_buffer.getvalue()
    ).decode()
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
            "legal_ack": "1",
            **csrf_field(guest, token),
        },
        files={"passport_photo": ("passport.png", PNG_BYTES, "image/png")},
        follow_redirects=True,
    )
    if saved.status_code != 200:
        FAILURES.append(f"guest save: HTTP {saved.status_code}")
    elif (
        i18n.STRINGS["en"]["saved_title"] not in saved.text
        and i18n.STRINGS["en"]["reported_title"] not in saved.text
    ):
        FAILURES.append("guest save: no confirmation shown")
    # Read the expected copy out of the catalogue rather than repeating it here,
    # so a deliberate wording change cannot leave this script asserting copy
    # the app no longer ships.
    progress_en = i18n.STRINGS["en"]["people_progress"] % {"done": 1, "total": 2}
    progress_cs = i18n.STRINGS["cs"]["people_progress"] % {"done": 1, "total": 2}
    check(guest, f"/l/{token}/{stay_a}", must_contain=[progress_en])
    check(guest, f"/l/{token}/{stay_a}/new", must_contain=['name="surname"', "Person 2"])
    czech.cookies.update(guest.cookies)
    # Drop the English choice so this browser is again "a guest who chose
    # nothing" - the state whose default language is under test.
    czech.cookies.delete(guest_routes.LANG_COOKIE)
    check(
        czech,
        f"/l/{token}/{stay_a}",
        must_contain=[progress_cs],
    )
    # The legal notice lives on the form page, not on the stay overview.
    check(czech, f"/l/{token}/{stay_a}/new", must_contain=["Osoba 2 z 2", "Právní informace"])
    czech_saved = czech.get(f"/l/{token}/{stay_a}?saved=1&lang=cs", follow_redirects=True)
    if czech_saved.status_code != 200 or (
        i18n.STRINGS["cs"]["saved_title"] not in czech_saved.text
        and i18n.STRINGS["cs"]["reported_title"] not in czech_saved.text
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
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else None))
