"""Demo data, so the app can be explored before any real credentials exist.

Seeding is only reachable while pointed at the mock UbyPort server, but
detection is not environment-bound: a demo seeded under mock and then switched
to test or prod is still recognised, so its invented guests can never be put in
front of the real police register.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from . import auth, claim, codelists, config, db, icalsync, reporting, validation
from .sample_calendar import sample_airbnb_ics

log = logging.getLogger("ubyhost.demo")

DEMO_ENTITY = "Josef Novák (demo)"
DEMO_CONTROLLER = "Demo Controller s.r.o."
DEMO_APARTMENT = "Vinohrady Studio (demo)"
DEMO_LOFT = "Karlín Loft (demo)"
DEMO_PINS = {
    DEMO_APARTMENT: "246810",
    DEMO_LOFT: "135790",
}
# A drawn signature is a data URL, so the demo record carries the smallest real
# PNG (1x1). It has to be a real image: the save paths check magic bytes, and a
# placeholder that is not one would stop behaving like a signed record as soon
# as a host re-saved the form.
DEMO_SIGNATURE = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg=="
)


def _demo_passport_png() -> bytes:
    import io

    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (8, 8), (200, 200, 200)).save(out, format="PNG")
    return out.getvalue()


def is_demo_apartment(apartment) -> bool:
    if not apartment:
        return False
    # The name is what the seed writes and what clear() matches on, so it is
    # checked in every environment. This used to return False off the mock
    # environment, which meant a demo seeded under mock and then switched to
    # test or prod stopped being recognised: its guests were sent to the real
    # register and the "Clear demo" button disappeared.
    if apartment["internal_name"] in (DEMO_APARTMENT, DEMO_LOFT):
        return True
    # The legal_entity fallback is the expensive half - a query per dashboard
    # row - and a demo can only be *seeded* while pointed at the mock server,
    # so it is the only part that stays mock-only.
    if config.UBYPORT_ENV != "mock":
        return False
    entity = db.query_one(
        "SELECT name FROM legal_entity WHERE id = ?", (apartment["legal_entity_id"],)
    )
    return bool(entity and entity["name"] in (DEMO_ENTITY, DEMO_CONTROLLER))


# 0100: the setup guide's "Try it out" makes one demo stay inside a real
# property, so the host can fill the guest form with made-up details. The stay
# is marked by ``reservation.source`` (an existing free-text column, so no
# schema change). It is never reported: ``reporting.collect_sendable`` drops it
# before any lease or batch, and ``reporting.submit_batch`` refuses it again.
# The stay fee report, invoices, the house book and stays exports, the deadline
# watch, the filing watchdog, door codes, guest e-mail and the guest stay
# picker leave it out too. tests/test_demo_stay_exclusion.py pins each one.
DEMO_STAY_SOURCE = "demo"
# For SQL that names the reservation ``r``.
NOT_DEMO_STAY_SQL = "COALESCE(r.source, '') != 'demo'"


def is_demo_stay(reservation) -> bool:
    if not reservation:
        return False
    try:
        source = reservation["source"]
    except (KeyError, IndexError):
        return False
    return (source or "") == DEMO_STAY_SOURCE


def demo_stay_for(apartment_id: int):
    """The setup guide's demo stay of this property, or None."""
    return db.query_one(
        "SELECT * FROM reservation WHERE apartment_id = ? AND source = ? "
        "AND archived_at IS NULL ORDER BY id DESC LIMIT 1",
        (int(apartment_id), DEMO_STAY_SOURCE),
    )


def create_demo_stay(apartment_id: int) -> int:
    """One night from today for one person; the existing one if there is one."""
    existing = demo_stay_for(apartment_id)
    if existing:
        return int(existing["id"])
    import secrets

    today = claim.prague_today()
    now = db.utcnow()
    return db.insert(
        "reservation",
        {
            "apartment_id": int(apartment_id),
            "source": DEMO_STAY_SOURCE,
            "uid": f"demo-{secrets.token_hex(8)}",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=1)).isoformat(),
            "summary": "Demo",
            "expected_guests_override": 1,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )


def delete_demo_stay(reservation_id: int, apartment_id: int) -> bool:
    """Delete a demo stay and its made-up guests. Never touches a real stay."""
    reservation = db.query_one(
        "SELECT * FROM reservation WHERE id = ? AND apartment_id = ?",
        (int(reservation_id), int(apartment_id)),
    )
    if not is_demo_stay(reservation):
        return False
    from . import passport_photos

    for guest in db.query("SELECT id FROM guest WHERE reservation_id = ?", (reservation["id"],)):
        passport_photos.delete_photo(int(guest["id"]))
    db.execute("DELETE FROM alert WHERE reservation_id = ?", (reservation["id"],))
    db.execute("DELETE FROM guest WHERE reservation_id = ?", (reservation["id"],))
    db.execute(
        "DELETE FROM reservation WHERE id = ? AND source = ?",
        (reservation["id"], DEMO_STAY_SOURCE),
    )
    return True


def sample_calendar_url() -> str:
    """The app serves this feed itself, so it never points at the mock server.

    A mock endpoint is a loopback address, which the SSRF screening in
    feed_url.py rejects everywhere except local development.
    """
    return f"{config.PUBLIC_BASE_URL}/sample-airbnb.ics"


def _guest(reservation_id: int, is_lead: bool, **fields) -> int:
    now = db.utcnow()
    values = validation.normalise_guest(fields)
    return db.insert(
        "guest",
        dict(
            values,
            reservation_id=reservation_id,
            is_lead=1 if is_lead else 0,
            signature_png=DEMO_SIGNATURE,
            signed_at=now,
            filled_at=now,
            entered_by="guest",
            submit_state=(
                reporting.NOT_REQUIRED
                if not validation.guest_is_reportable(values["nationality"])
                else reporting.PENDING
            ),
            created_at=now,
            updated_at=now,
        ),
    )


def _stay_on(apartment_id: int, day: date):
    return db.query_one(
        "SELECT * FROM reservation WHERE apartment_id = ? AND date_from = ?",
        (apartment_id, day.isoformat()),
    )


def _claim_provisional(apartment, reservation, *, email: str, party_size: int) -> Optional[str]:
    """Start a claim so staging console mail shows a copyable #c= link."""
    ok, err, secret = claim.start_claim(
        reservation,
        apartment,
        email=email,
        party_size=party_size,
        lang="en",
    )
    if not ok:
        log.warning(
            "demo: provisional claim failed for reservation %s (%s)",
            reservation["id"],
            err,
        )
        return None
    return secret


def _claim_assigned(apartment, reservation, *, email: str, party_size: int) -> None:
    secret = _claim_provisional(
        apartment, reservation, email=email, party_size=party_size
    )
    if not secret:
        return
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation["id"],))
    if not claim.confirm(reservation, secret):
        log.warning("demo: could not confirm claim for reservation %s", reservation["id"])


def _seed_apartment(
    *,
    owner_user_id: Optional[int],
    entity_id: int,
    controller_id: Optional[int],
    internal_name: str,
    city_en: str,
    uby_idub: str,
    uby_mark: str,
    uby_name: str,
    addr_okres: str,
    addr_obec_cast: str,
    addr_street: str,
    addr_house_no: str,
    addr_orient_no: str,
    addr_zip: str,
    uby_ws_user: str,
    automation_mode: str,
    passport_photo_policy: str,
    permalink_window_days: int,
    guest_message: str,
) -> int:
    return db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "data_controller_entity_id": controller_id,
            "owner_user_id": owner_user_id,
            "internal_name": internal_name,
            "city_en": city_en,
            "uby_idub": uby_idub,
            "uby_mark": uby_mark,
            "uby_name": uby_name,
            "uby_contact": "host@example.com",
            "addr_okres": addr_okres,
            "addr_obec": "Praha",
            "addr_obec_cast": addr_obec_cast,
            "addr_street": addr_street,
            "addr_house_no": addr_house_no,
            "addr_orient_no": addr_orient_no,
            "addr_zip": addr_zip,
            "uby_ws_user": uby_ws_user,
            "uby_ws_password_enc": db.encrypt_secret("demo-password"),
            "automation_mode": automation_mode,
            "submit_after_hours": 24,
            "permalink_window_days": permalink_window_days,
            "default_purpose": "10",
            "guest_message": guest_message,
            "passport_photo_policy": passport_photo_policy,
            "permalink_token": auth.new_permalink_token(),
            "permalink_pin": DEMO_PINS[internal_name],
            "active": 1,
            "created_at": db.utcnow(),
        },
    )


def _sync_sample_feed(apartment_id: int) -> None:
    feed_id = db.insert(
        "ical_feed",
        {
            "apartment_id": apartment_id,
            "url": sample_calendar_url(),
            "label": "Airbnb (sample feed)",
            "own_name": "Airbnb",
            "active": 1,
            "created_at": db.utcnow(),
        },
    )
    feed = db.query_one("SELECT * FROM ical_feed WHERE id = ?", (feed_id,))
    stats = icalsync.sync_feed(feed, ics_text=sample_airbnb_ics())
    log.info(
        "demo: imported %s stay(s) for apartment %s",
        stats.get("created"),
        apartment_id,
    )


def _enrich_studio(apartment_id: int) -> None:
    """Vinohrady: picker, claims, house book, locked stay, past recovery."""
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    today = claim.prague_today()
    yesterday = today - timedelta(days=1)

    # Finished foreign stay → house book + mock Doručenka.
    reported = _stay_on(apartment_id, yesterday)
    if reported:
        db.update(
            "reservation",
            reported["id"],
            {"declared_guests": 2, "updated_at": db.utcnow()},
        )
        _guest(
            reported["id"],
            True,
            surname="Smith",
            first_name="John Paul",
            birth_date="01011990",
            nationality="GBR",
            doc_number="P1234567",
            res_street="Baker Street 221B",
            res_city="London",
            res_country="GBR",
            purpose="10",
        )
        _guest(
            reported["id"],
            False,
            surname="Smith",
            first_name="Anna",
            birth_date="15031992",
            nationality="GBR",
            doc_number="P7654321",
            res_street="Baker Street 221B",
            res_city="London",
            res_country="GBR",
            purpose="10",
        )
        if config.UBYPORT_ENV == "mock":
            try:
                reporting.submit_for_apartment(
                    apartment_id, mode="demo", ignore_automation=True
                )
            except Exception as exc:
                log.warning("demo: could not report to the mock server (%s)", exc)

    # Arriving today — incomplete party the host needs to chase.
    today_stay = _stay_on(apartment_id, today)
    if today_stay:
        db.update(
            "reservation",
            today_stay["id"],
            {"declared_guests": 3, "updated_at": db.utcnow()},
        )
        _guest(
            today_stay["id"],
            True,
            surname="Rossi",
            first_name="Marco",
            birth_date="09071988",
            nationality="ITA",
            doc_number="YA1122334",
            res_street="Via Roma 1",
            res_city="Roma",
            res_country="ITA",
            purpose="01",
        )
        _claim_provisional(
            apartment,
            today_stay,
            email="marco.rossi@demo.ubyhost.test",
            party_size=3,
        )

    # Tomorrow — unclaimed so the arrival-lane picker stays busy; leave open.
    # Two days out — assigned (claimed) for the assigned/resend host screen.
    assigned = _stay_on(apartment_id, today + timedelta(days=5))
    if assigned:
        _claim_assigned(
            apartment,
            assigned,
            email="assigned.guest@demo.ubyhost.test",
            party_size=2,
        )

    # Czech nationals → house book only, not reported to police.
    czech = _stay_on(apartment_id, today + timedelta(days=12))
    if czech:
        db.update(
            "reservation",
            czech["id"],
            {"declared_guests": 2, "updated_at": db.utcnow()},
        )
        _guest(
            czech["id"],
            True,
            surname="Novák",
            first_name="Petr",
            birth_date="12051985",
            nationality="CZE",
            doc_number="123456789",
            res_street="Národní 1",
            res_city="Praha",
            res_country="CZE",
            purpose="10",
        )
        _guest(
            czech["id"],
            False,
            surname="Nováková",
            first_name="Eva",
            birth_date="03081987",
            nationality="CZE",
            doc_number="987654321",
            res_street="Národní 1",
            res_city="Praha",
            res_country="CZE",
            purpose="10",
        )

    # Incomplete past stay — stay-specific link still recovers it.
    past = _stay_on(apartment_id, today - timedelta(days=8))
    if past:
        db.update(
            "reservation",
            past["id"],
            {"declared_guests": 2, "updated_at": db.utcnow()},
        )
        _guest(
            past["id"],
            True,
            surname="Weber",
            first_name="Lena",
            birth_date="22111991",
            nationality="DEU",
            doc_number="C01X2Y3Z",
            res_street="Unter den Linden 1",
            res_city="Berlin",
            res_country="DEU",
            purpose="10",
        )
        _claim_assigned(
            apartment,
            past,
            email="lena.weber@demo.ubyhost.test",
            party_size=2,
        )

    # Locked stay — host has closed guest forms.
    locked = _stay_on(apartment_id, today + timedelta(days=7))
    if locked:
        claim.ensure_row(locked["id"])
        claim.lock_guest_access(locked["id"])


def _enrich_loft(apartment_id: int) -> None:
    """Karlín: alternate controller + required passport for foreign guests."""
    from . import passport_photos

    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    today = claim.prague_today()

    today_stay = _stay_on(apartment_id, today)
    if today_stay:
        db.update(
            "reservation",
            today_stay["id"],
            {"declared_guests": 2, "updated_at": db.utcnow()},
        )
        _claim_provisional(
            apartment,
            today_stay,
            email="loft.guest@demo.ubyhost.test",
            party_size=2,
        )

    # Foreign guest with a temporary passport photo awaiting host review.
    passport_stay = _stay_on(apartment_id, today + timedelta(days=1))
    if passport_stay:
        db.update(
            "reservation",
            passport_stay["id"],
            {"declared_guests": 1, "updated_at": db.utcnow()},
        )
        guest_id = _guest(
            passport_stay["id"],
            True,
            surname="Dupont",
            first_name="Claire",
            birth_date="18041989",
            nationality="FRA",
            doc_number="12AB34567",
            res_street="Rue de Rivoli 1",
            res_city="Paris",
            res_country="FRA",
            purpose="10",
        )
        # A small grey PNG, enough for the host review UI, never sent to Police.
        # Built with Pillow: uploads are decoded and re-encoded now (WP08), and
        # the old hand-written bytes had a broken data stream.
        tiny_png = _demo_passport_png()
        passport_photos.save_photo(guest_id, tiny_png, "image/png")
        db.update(
            "guest",
            guest_id,
            {"passport_photo_at": db.utcnow(), "updated_at": db.utcnow()},
        )
        _claim_assigned(
            apartment,
            passport_stay,
            email="claire.dupont@demo.ubyhost.test",
            party_size=1,
        )

    # Cancelled booking — host can filter Stays by cancelled status.
    cancelled = _stay_on(apartment_id, today + timedelta(days=45))
    if cancelled:
        db.update(
            "reservation",
            cancelled["id"],
            {"status": "cancelled", "updated_at": db.utcnow()},
        )

    # One completed Czech stay so house book shows non-reportable guests here too.
    czech = _stay_on(apartment_id, today + timedelta(days=12))
    if czech:
        db.update(
            "reservation",
            czech["id"],
            {"declared_guests": 1, "updated_at": db.utcnow()},
        )
        _guest(
            czech["id"],
            True,
            surname="Svobodová",
            first_name="Jana",
            birth_date="05021980",
            nationality="CZE",
            doc_number="112233445",
            res_street="Karlínské náměstí 1",
            res_city="Praha",
            res_country="CZE",
            purpose="10",
        )


def _enrich_extras(studio_id: int, loft_id: int, owner_user_id: Optional[int]) -> None:
    """Stay fee, guest pay, payment requests, door code, cleaning, property page."""
    from . import payment_request, property_page, stay_fee_filing

    now = db.utcnow()
    today = claim.prague_today()

    # Stay fee: configured on the studio only, so both states are visible.
    db.update(
        "apartment",
        studio_id,
        {
            "stay_fee_rate_czk": 500,
            "stay_fee_cadence": "monthly",
            "stay_fee_council_account": "123/0600",
            "stay_fee_council_iban": "CZ9106000000000000000123",
            "stay_fee_vs": "2026001",
            "stay_fee_authority_name": "Demo městský úřad",
            "stay_fee_authority_address": "Demo 1, 100 00 Praha",
            "stay_fee_authority_contact": "podatelna@demo.example",
            "stay_fee_payee": "Demo městský úřad",
            "stay_fee_instruction": "Demo: pay the stay fee by QR code or bank transfer.",
            "stay_fee_collect": 1,
            "stay_fee_guest_rails": "qr,iban",
            "stay_fee_guest_cash_note": "Cash at check-in with a receipt (demo).",
        },
    )
    db.insert(
        "stay_fee_rate",
        {
            "apartment_id": studio_id,
            "rate_czk": 500,
            "effective_from": "2026-01-01",
            "created_at": now,
        },
    )
    last_month = today.replace(day=1) - timedelta(days=1)
    period_key = stay_fee_filing.period_key("monthly", last_month)
    filing_id = db.insert(
        "stay_fee_filing",
        {
            "apartment_id": studio_id,
            "period_key": period_key,
            "version": 1,
            "cadence": "monthly",
            "rate_czk": 500,
            "liable_days": 4,
            "exempt_days": 1,
            "total_due_czk": 2000,
            "total_collected_czk": 1500,
            "created_at": now,
        },
    )
    db.insert(
        "stay_fee_adjustment",
        {
            "apartment_id": studio_id,
            "period_key": period_key,
            "direction": "add",
            "mode": "people",
            "people_count": 1,
            "bed_days": 2,
            "reason_enc": db.encrypt_secret("Two extra person-days from the demo house book."),
            "created_by": owner_user_id,
            "created_at": now,
            "filing_id": filing_id,
        },
    )

    today_stay = _stay_on(studio_id, today)
    loft_today = _stay_on(loft_id, today)
    if today_stay:
        lead = db.query_one(
            "SELECT id FROM guest WHERE reservation_id = ? AND is_lead = 1",
            (today_stay["id"],),
        )
        if lead:
            db.update("guest", lead["id"], {"fee_host_decision": "charge", "updated_at": now})
        if owner_user_id is not None:
            # Guest pay (0897): one paid QR request, one still awaiting payment.
            paid_id = payment_request.create(
                owner_user_id,
                apartment_id=studio_id,
                reservation_id=today_stay["id"],
                reason="cleaning",
                amount_czk=800,
                rail="qr",
                expires_at=f"{(today + timedelta(days=30)).isoformat()}T23:59:59+00:00",
                guest_email="marco.rossi@demo.ubyhost.test",
                guest_note="Cleaning fee for the demo stay.",
            )
            db.update(
                "payment_request",
                paid_id,
                {"status": "paid", "paid_at": now, "updated_at": now},
            )
            open_id = payment_request.create(
                owner_user_id,
                apartment_id=studio_id,
                reservation_id=today_stay["id"],
                reason="extra_guest",
                amount_czk=500,
                rail="qr",
                expires_at=f"{(today + timedelta(days=14)).isoformat()}T23:59:59+00:00",
                guest_email="marco.rossi@demo.ubyhost.test",
                guest_note="Extra guest fee for the demo stay.",
            )
            db.update(
                "payment_request",
                open_id,
                {"status": "awaiting_payment", "updated_at": now},
            )
        # Door-code window for the stay (locks are off; the row renders only).
        db.insert(
            "door_code",
            {
                "reservation_id": today_stay["id"],
                "apartment_id": studio_id,
                "lock_id": "demo-lock-1",
                "state": "pending",
                "pin_enc": db.encrypt_secret("864209"),
                "valid_from": f"{today.isoformat()}T15:00:00+00:00",
                "valid_to": f"{(today + timedelta(days=2)).isoformat()}T11:00:00+00:00",
                "created_at": now,
                "updated_at": now,
            },
        )
        db.insert(
            "cleaning_event",
            {
                "apartment_id": studio_id,
                "source_reservation_id": today_stay["id"],
                "source_date": today.isoformat(),
                "scheduled_date": (today + timedelta(days=1)).isoformat(),
                "start_time": "11:00",
                "end_time": "13:00",
                "state": "scheduled",
                "created_at": now,
                "updated_at": now,
            },
        )
    if loft_today:
        db.insert(
            "cleaning_event",
            {
                "apartment_id": loft_id,
                "source_reservation_id": loft_today["id"],
                "source_date": today.isoformat(),
                "scheduled_date": (today + timedelta(days=1)).isoformat(),
                "state": "dismissed",
                "created_at": now,
                "updated_at": now,
            },
        )
    for apartment_id in (studio_id, loft_id):
        db.insert(
            "cleaning_property",
            {
                "apartment_id": apartment_id,
                "instructions": "Demo cleaning: change linens, take out the trash.",
                "checkout_time": "11:00",
                "checkin_time": "15:00",
                "updated_at": now,
            },
        )
    # Public property page with a booking-widget price, plus one paid booking
    # in a free gap (after the czech-visit stay at +12).
    db.insert(
        "property_page",
        {
            "apartment_id": studio_id,
            "description": "Demo studio in Vinohrady with a park view. Sample listing content only.",
            "checkin_text": "Check-in from 15:00, self check-in with the PIN.",
            "checkout_text": "Check-out by 11:00.",
            "published": 0,
            "hide_from_search": 0,
            "nightly_price_czk": 1500,
            "house_rules": "No smoking. Quiet hours after 22:00.",
            "created_at": now,
            "updated_at": now,
        },
    )
    property_page.publish_page(studio_id, published=True)
    if owner_user_id is not None:
        db.insert(
            "site_booking",
            {
                "apartment_id": studio_id,
                "owner_user_id": owner_user_id,
                "status": "paid",
                "date_from": (today + timedelta(days=14)).isoformat(),
                "date_to": (today + timedelta(days=16)).isoformat(),
                "guests": 2,
                "guest_name": "Demo Site Guest",
                "guest_email": "site.guest@demo.ubyhost.test",
                "lang": "en",
                "nights": 2,
                "nightly_czk": 1500,
                "cleaning_fee_czk": 0,
                "total_czk": 3000,
                "cancellation_policy": "non_refundable",
                "terms_version": config.TERMS_VERSION,
                "terms_accepted_at": now,
                "pay_method": "direct",
                "paid_at": now,
                "created_at": now,
                "updated_at": now,
            },
        )


def seed(owner_user_id: Optional[int] = None) -> Optional[int]:
    """Create two demo properties covering the main host/guest paths.

    Returns the Vinohrady Studio apartment id (primary walkthrough entry).

    Coverage map (mock-only; never touches real UbyPort):
    - Vinohrady: passport off, PM=controller, manual reporting, claim/assigned,
      late incomplete, locked, Czech house-book, foreign reported stay, guest message, PIN
    - Karlín: passport required + sample photo awaiting review, alternate controller,
      scheduled reporting, cancelled stay, Czech house-book, guest message, PIN
    - Shared sample calendar (stays never overlap) also includes an Airbnb block
      (Not available) that sync skips
    - Also seeded on top: stay fee config + rate + filing + adjustment on Vinohrady,
      guest pay rails, two payment requests, a door-code window, cleaning schedule,
      a published property page with one paid site booking (Vinohrady)
    """
    if config.UBYPORT_ENV != "mock":
        return None
    if db.query_one(
        "SELECT 1 AS x FROM apartment WHERE (? IS NULL OR owner_user_id = ?)",
        (owner_user_id, owner_user_id),
    ):
        return None

    entity_id = db.insert(
        "legal_entity",
        {
            "name": DEMO_ENTITY,
            "ico": "12345678",
            "seat": "Korunní 1234/12a, 120 00 Praha 2",
            "contact_email": "host@example.com",
            "contact_phone": "+420777100200",
            "bank_account": "123/0600",
            "iban": "CZ9106000000000000000123",
            "owner_user_id": owner_user_id,
            "created_at": db.utcnow(),
        },
    )
    controller_id = db.insert(
        "legal_entity",
        {
            "name": DEMO_CONTROLLER,
            "ico": "87654321",
            "seat": "Thámova 12, 186 00 Praha 8",
            "contact_email": "controller@example.com",
            "contact_phone": "+420777300400",
            "owner_user_id": owner_user_id,
            "created_at": db.utcnow(),
        },
    )

    # Passport off (default) and PM is also the GDPR controller.
    studio_id = _seed_apartment(
        owner_user_id=owner_user_id,
        entity_id=entity_id,
        controller_id=None,
        internal_name=DEMO_APARTMENT,
        city_en="Prague",
        uby_idub="100227887600",
        uby_mark="12CDEF",
        uby_name="Vinohrady Studio",
        addr_okres="Praha 2",
        addr_obec_cast="Vinohrady",
        addr_street="Korunní",
        addr_house_no="1234",
        addr_orient_no="12a",
        addr_zip="12000",
        uby_ws_user="UBY-WS12cdef",
        automation_mode="manual",
        passport_photo_policy="off",
        permalink_window_days=3,
        guest_message=(
            "Welcome to Vinohrady Studio. Please finish registration before arrival. "
            "Demo PIN: 246810."
        ),
    )
    # Passport required for foreign guests; separate data controller entity.
    loft_id = _seed_apartment(
        owner_user_id=owner_user_id,
        entity_id=entity_id,
        controller_id=controller_id,
        internal_name=DEMO_LOFT,
        city_en="Prague",
        uby_idub="100227887601",
        uby_mark="34ABCD",
        uby_name="Karlín Loft",
        addr_okres="Praha 8",
        addr_obec_cast="Karlín",
        addr_street="Thámova",
        addr_house_no="12",
        addr_orient_no="",
        addr_zip="18600",
        uby_ws_user="UBY-WS34abcd",
        automation_mode="scheduled",
        passport_photo_policy="required_foreign",
        permalink_window_days=3,
        guest_message=(
            "Welcome to Karlín Loft. Foreign guests upload a passport photo for host "
            "review only — it is never sent to Police. Demo PIN: 135790."
        ),
    )

    _sync_sample_feed(studio_id)
    _sync_sample_feed(loft_id)

    try:
        codelists.refresh_all(
            reporting.client_for(
                db.query_one("SELECT * FROM apartment WHERE id = ?", (studio_id,))
            )
        )
    except Exception as exc:  # the mock may not be up; the app still works
        log.warning("demo: could not fetch the code lists (%s)", exc)

    _enrich_studio(studio_id)
    _enrich_loft(loft_id)
    _enrich_extras(studio_id, loft_id, owner_user_id)

    reporting.check_deadlines(owner_user_id=owner_user_id)
    db.audit(
        "demo_seeded",
        f"apartment={studio_id},loft={loft_id}",
        owner_user_id=owner_user_id,
    )
    return studio_id


def clear(owner_user_id: Optional[int] = None) -> bool:
    """Remove only the built-in demo dataset, never user production data."""
    entities = db.query(
        "SELECT * FROM legal_entity WHERE name IN (?, ?) "
        "AND (? IS NULL OR owner_user_id = ?)",
        (DEMO_ENTITY, DEMO_CONTROLLER, owner_user_id, owner_user_id),
    )
    if not entities:
        return False
    entity_ids = [row["id"] for row in entities]
    placeholders = ",".join("?" * len(entity_ids))
    apartments = db.query(
        f"SELECT * FROM apartment WHERE ("
        f"internal_name IN (?, ?) OR legal_entity_id IN ({placeholders}) "
        f"OR data_controller_entity_id IN ({placeholders})"
        f") AND (? IS NULL OR owner_user_id = ?)",
        (
            DEMO_APARTMENT,
            DEMO_LOFT,
            *entity_ids,
            *entity_ids,
            owner_user_id,
            owner_user_id,
        ),
    )
    if not apartments:
        return False
    from . import passport_photos

    for apartment in apartments:
        guests = db.query(
            "SELECT g.id FROM guest g "
            "JOIN reservation r ON r.id = g.reservation_id "
            "WHERE r.apartment_id = ?",
            (apartment["id"],),
        )
        for guest in guests:
            passport_photos.delete_photo(int(guest["id"]))
        db.execute("DELETE FROM alert WHERE apartment_id = ?", (apartment["id"],))
        db.execute("DELETE FROM apartment_slug WHERE apartment_id = ?", (apartment["id"],))
        # Feature rows the apartment cascade does not reach (or that point at
        # the apartment without one): remove them explicitly.
        for table in (
            "payment_request",
            "stay_fee_adjustment",
            "stay_fee_filing",
            "stay_fee_rate",
            "door_code",
            "cleaning_event",
            "cleaning_property",
            "cleaning_code",
            "property_page",
            "property_slug",
            "property_slug_history",
            "site_booking",
            "booking_hold",
        ):
            db.execute(f"DELETE FROM {table} WHERE apartment_id = ?", (apartment["id"],))
        db.execute("DELETE FROM apartment WHERE id = ?", (apartment["id"],))
    for entity_id in entity_ids:
        db.execute("DELETE FROM legal_entity WHERE id = ?", (entity_id,))
    db.audit("demo_cleared", owner_user_id=owner_user_id)
    return True
