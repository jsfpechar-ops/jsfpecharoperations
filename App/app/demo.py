"""Demo data, so the app can be explored before any real credentials exist.

Only reachable while pointed at the mock UbyPort server, so it can never put
invented guests in front of the real police register.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional
from urllib.parse import urlparse

from . import auth, codelists, config, db, icalsync, reporting, validation

log = logging.getLogger("ubyhost.demo")

DEMO_ENTITY = "Josef Novák (demo)"
DEMO_APARTMENT = "Vinohrady Studio (demo)"


def is_demo_apartment(apartment) -> bool:
    if not apartment:
        return False
    if apartment["internal_name"] == DEMO_APARTMENT:
        return True
    entity = db.query_one(
        "SELECT name FROM legal_entity WHERE id = ?", (apartment["legal_entity_id"],)
    )
    return bool(entity and entity["name"] == DEMO_ENTITY)


def sample_calendar_url() -> str:
    """Sample feed on the mock server locally, or bundled with the app in production."""
    if config.UBYPORT_ENV == "mock":
        parsed = urlparse(config.endpoint_for("mock"))
        return f"{parsed.scheme}://{parsed.netloc}/sample-airbnb.ics"
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
            # A drawn signature is a data URL; this is a placeholder so the
            # record looks and behaves like a signed one.
            signature_png="data:image/png;base64,demo",
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


def seed(owner_user_id: Optional[int] = None) -> Optional[int]:
    """Create one apartment with stays and guests. Returns the apartment id."""
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
            "owner_user_id": owner_user_id,
            "created_at": db.utcnow(),
        },
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": owner_user_id,
            "internal_name": DEMO_APARTMENT,
            "city_en": "Prague",
            "uby_idub": "100227887600",
            "uby_mark": "CZGFW",
            "uby_name": "Vinohrady Studio",
            "uby_contact": "host@example.com",
            "addr_okres": "Praha 2",
            "addr_obec": "Praha",
            "addr_obec_cast": "Vinohrady",
            "addr_street": "Korunní",
            "addr_house_no": "1234",
            "addr_orient_no": "12a",
            "addr_zip": "12000",
            "uby_ws_user": "UBY-WS12cdef",
            "uby_ws_password_enc": db.encrypt_secret("demo-password"),
            "automation_mode": "immediate",
            "submit_after_hours": 24,
            "permalink_window_days": 3,
            "default_purpose": "10",
            "checkin_info": "Self check-in. Key box code arrives on the morning of arrival.",
            "permalink_token": auth.new_permalink_token(),
            "permalink_pin": auth.new_permalink_pin(),
            "active": 1,
            "created_at": db.utcnow(),
        },
    )
    db.insert(
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

    stats = icalsync.sync_all(apartment_id)
    log.info("demo: imported %s stay(s) from the sample calendar", stats.get("created"))

    try:
        codelists.refresh_all(reporting.client_for(db.query_one(
            "SELECT * FROM apartment WHERE id = ?", (apartment_id,)
        )))
    except Exception as exc:  # the mock may not be up; the app still works
        log.warning("demo: could not fetch the code lists (%s)", exc)

    # A stay that arrived yesterday, fully filled in and reported: shows the
    # finished state, the Doručenka and the house book with something in them.
    yesterday = date.today() - timedelta(days=1)
    reported = db.query_one(
        "SELECT * FROM reservation WHERE apartment_id = ? AND date_from = ? ",
        (apartment_id, yesterday.isoformat()),
    )
    if reported:
        db.update("reservation", reported["id"], {"declared_guests": 2, "updated_at": db.utcnow()})
        _guest(
            reported["id"], True,
            surname="Smith", first_name="John Paul", birth_date="01011990", nationality="GBR",
            doc_number="P1234567", res_street="Baker Street 221B", res_city="London",
            res_country="GBR", purpose="10",
        )
        _guest(
            reported["id"], False,
            surname="Smith", first_name="Anna", birth_date="15031992", nationality="GBR",
            doc_number="P7654321", res_street="Baker Street 221B", res_city="London",
            res_country="GBR", purpose="10",
        )
        if config.UBYPORT_ENV == "mock":
            try:
                reporting.submit_for_apartment(
                    apartment_id, mode="demo", ignore_automation=True
                )
            except Exception as exc:
                log.warning("demo: could not report to the mock server (%s)", exc)

    # A stay that arrived today with only one of three forms in: this is the
    # state the host actually needs to see and chase.
    today_stay = db.query_one(
        "SELECT * FROM reservation WHERE apartment_id = ? AND date_from = ?",
        (apartment_id, date.today().isoformat()),
    )
    if today_stay:
        db.update("reservation", today_stay["id"], {"declared_guests": 3, "updated_at": db.utcnow()})
        _guest(
            today_stay["id"], True,
            surname="Rossi", first_name="Marco", birth_date="09071988", nationality="ITA",
            doc_number="YA1122334", res_street="Via Roma 1", res_city="Roma",
            res_country="ITA", purpose="01",
        )

    reporting.check_deadlines(owner_user_id=owner_user_id)
    db.audit("demo_seeded", f"apartment={apartment_id}", owner_user_id=owner_user_id)
    return apartment_id


def clear(owner_user_id: Optional[int] = None) -> bool:
    """Remove only the built-in demo dataset, never user production data."""
    entity = db.query_one(
        "SELECT * FROM legal_entity WHERE name = ? AND (? IS NULL OR owner_user_id = ?)",
        (DEMO_ENTITY, owner_user_id, owner_user_id),
    )
    apartment = db.query_one(
        "SELECT * FROM apartment WHERE internal_name = ? AND legal_entity_id = ? "
        "AND (? IS NULL OR owner_user_id = ?)",
        (DEMO_APARTMENT, entity["id"] if entity else -1, owner_user_id, owner_user_id),
    )
    if not entity or not apartment:
        return False
    db.execute("DELETE FROM alert WHERE apartment_id = ?", (apartment["id"],))
    db.execute("DELETE FROM apartment WHERE id = ?", (apartment["id"],))
    db.execute("DELETE FROM legal_entity WHERE id = ?", (entity["id"],))
    db.audit("demo_cleared", owner_user_id=owner_user_id)
    return True
