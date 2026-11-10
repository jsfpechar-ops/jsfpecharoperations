"""Brief 1089 (K-L04): a guest under 15 on the arrival date does not sign.

Act 326/1999 § 103(b): no signature is asked of, or stored for, a child under
15. § 103(u): an adult guest on the same stay may sign for the child, as a
parent or guardian or as the adult responsible during the stay. The child is
reported to the police exactly as before.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import auth, claim, db, housebook, reporting, stay_fee, validation
from app.main import app
from app.ubyport import client as client_module
from app.ubyport import soap
from app.ubyport.client import UbyportClient
from tests.conftest import complete_guest_claim, login_as
from tests.test_guest_child_document import SIGNATURE
from tests.test_ubyport_golden import SUCCESS_RESPONSE

TOKEN = "under15tok1089"
OTHER_TOKEN = "under15tok1089b"
USERNAME = "under15-1089"
ARRIVAL = date(2026, 10, 20)
RES = {"date_from": "2026-10-20", "date_to": "2026-10-25"}
SIGN_FOR = ("signed_for_guest_id", "signed_for_role", "signed_for_at", "signed_for_wording")
EXEMPT_TEXT = "Under 15, no signature required (§ 103(b))"


# --- seed ---------------------------------------------------------------------

def _cleanup():
    for token in (TOKEN, OTHER_TOKEN):
        apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (token,))
        if not apartment:
            continue
        for table in ("alert", "submission"):
            db.execute(f"DELETE FROM {table} WHERE apartment_id = ?", (apartment["id"],))
        db.execute(
            "DELETE FROM guest WHERE reservation_id IN "
            "(SELECT id FROM reservation WHERE apartment_id = ?)",
            (apartment["id"],),
        )
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment["id"],))
        db.execute("DELETE FROM apartment WHERE id = ?", (apartment["id"],))
        db.execute("DELETE FROM legal_entity WHERE id = ?", (apartment["legal_entity_id"],))


def _seed_stay(token=TOKEN, owner_id=None):
    now = db.utcnow()
    today = claim.prague_today()
    entity_id = db.insert(
        "legal_entity",
        {"name": "Under15 1089", "seat": "Praha", "ico": "12345678", "created_at": now},
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "Under15 flat",
            "uby_name": "Under15 Facility",
            "city_en": "Prague",
            "permalink_token": token,
            "permalink_window_days": 14,
            "default_purpose": "10",
            "passport_photo_policy": "off",
            "automation_mode": "manual",
            "submit_after_hours": 24,
            "stay_fee_rate_czk": 50,
            "active": 1,
            "created_at": now,
            "owner_user_id": owner_id,
        },
    )
    reservation_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "airbnb",
            "uid": f"under15-{token}",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=3)).isoformat(),
            "status": "active",
            "expected_guests_override": 12,
            "created_at": now,
            "updated_at": now,
        },
    )
    return apartment_id, reservation_id


@pytest.fixture()
def stay():
    db.init_db()
    _cleanup()
    existing = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    owner_id = (
        existing["id"]
        if existing
        else auth.create_account(f"{USERNAME}@example.test", "Under15 Owner", username=USERNAME)
    )
    apartment_id, reservation_id = _seed_stay(TOKEN, owner_id)
    try:
        yield {
            "owner": owner_id,
            "apartment_id": apartment_id,
            "reservation_id": reservation_id,
            "today": claim.prague_today(),
        }
    finally:
        _cleanup()


def _apartment(stay):
    return db.query_one("SELECT * FROM apartment WHERE id = ?", (stay["apartment_id"],))


def _reservation(stay):
    return db.query_one("SELECT * FROM reservation WHERE id = ?", (stay["reservation_id"],))


def _born(stay, years: int) -> str:
    """A stored birth date: 1 January, ``years`` calendar years before the arrival year."""
    return f"0101{stay['today'].year - years}"


_DOC = iter(range(1000000, 9999999))


def _insert(stay, first_name, birth, *, signature=SIGNATURE, reservation_id=None, **over):
    """A complete guest row written by the host (so no device owns it)."""
    now = db.utcnow()
    row = {
        "reservation_id": reservation_id or stay["reservation_id"],
        "surname": "Under",
        "first_name": first_name,
        "birth_date": birth,
        "nationality": "GBR",
        "doc_number": f"P{next(_DOC)}",
        "res_street": "Street 1",
        "res_city": "London",
        "res_country": "GBR",
        "purpose": "10",
        "is_lead": 0,
        "entered_by": "host",
        "signature_png": signature,
        "signed_at": now if signature else None,
        "identity_verified_at": now,
        "submit_state": reporting.PENDING,
        "created_at": now,
        "updated_at": now,
    }
    row.update(over)
    return db.insert("guest", row)


def _guest(guest_id):
    return db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))


def _client(stay) -> TestClient:
    browser = TestClient(app)
    complete_guest_claim(browser, TOKEN, stay["reservation_id"], party_size=12)
    return browser


def _post(browser, stay, first_name, birth, **over):
    data = {
        "surname": "Under",
        "first_name": first_name,
        "birth_date": birth,
        "nationality": "GBR",
        "doc_number": f"P{next(_DOC)}",
        "res_street": "Baker Street 221B",
        "res_city": "London",
        "res_country": "GBR",
        "purpose": "10",
        "party_size": "12",
        "signature": SIGNATURE,
        "legal_ack": "1",
    }
    data.update(over)
    return browser.post(
        f"/l/{TOKEN}/{stay['reservation_id']}/save?lang=en", data=data, follow_redirects=False
    )


def _saved(stay, first_name):
    # Names are encrypted at rest, so match on the decrypted row.
    rows = db.query("SELECT * FROM guest WHERE reservation_id = ?", (stay["reservation_id"],))
    return next((row for row in rows if row["first_name"].upper() == first_name.upper()), None)


def _save(browser, stay, first_name, birth, **over):
    response = _post(browser, stay, first_name, birth, **over)
    assert response.status_code == 303, response.text[-600:]
    row = _saved(stay, first_name)
    assert row is not None
    return row


def _snapshot(guest_id, reservation):
    row = _guest(guest_id)
    return (
        row["submit_state"],
        row["submit_attempts"],
        row["last_errors"],
        row["updated_at"],
        reporting.guest_payload(row, reservation),
    )


def _link(guest_id):
    row = _guest(guest_id)
    return tuple(row[key] for key in SIGN_FOR)


def _issue_fields(row, reservation):
    return [issue.field for issue in reporting.guest_issues(row, reservation)]


# --- a. the age rule ----------------------------------------------------------

def test_under_age_is_true_only_when_certain():
    under = validation.certainly_under_age
    assert under("21102011", ARRIVAL, 15) is True  # 14 years 364 days
    assert under("20102011", ARRIVAL, 15) is False  # 15 on the arrival day
    assert under("00002012", ARRIVAL, 15) is True
    assert under("00002011", ARRIVAL, 15) is False
    assert under("00102011", ARRIVAL, 15) is False  # earliest birthday 1 October 2011
    assert under("00000000", ARRIVAL, 15) is False
    assert under("", ARRIVAL, 15) is False
    assert under("31022012", ARRIVAL, 15) is False  # no such date
    assert under("21102011", None, 15) is False


def test_a_29_february_birthday():
    under = validation.certainly_under_age
    assert under("29022012", date(2027, 2, 28), 15) is True
    assert under("29022012", date(2027, 3, 1), 15) is False


def test_at_least_age_reads_an_unknown_part_as_the_latest_birthday():
    at_least = validation.certainly_at_least_age
    assert at_least("20102008", ARRIVAL, 18) is True  # 18th birthday on the day
    assert at_least("21102008", ARRIVAL, 18) is False  # the day before it
    assert at_least("00122008", date(2026, 12, 30), 18) is False  # could be born 31 December
    assert at_least("00122008", date(2026, 12, 31), 18) is True
    assert at_least("00002008", date(2026, 12, 30), 18) is False  # month unknown: December
    assert at_least("00002008", date(2026, 12, 31), 18) is True
    assert at_least("00022008", date(2026, 2, 28), 18) is False  # 2008 is a leap year
    assert at_least("00002007", ARRIVAL, 18) is True
    assert at_least("00000000", ARRIVAL, 18) is False
    assert at_least("", ARRIVAL, 18) is False
    assert at_least("20102008", None, 18) is False


# --- b. completeness ----------------------------------------------------------

def _row(birth, signature, **over):
    row = {
        "reservation_id": 0, "surname": "Under", "first_name": "Kid", "birth_date": birth,
        "nationality": "GBR", "doc_number": "P1234567", "visa_number": None,
        "res_street": "Street 1", "res_city": "London", "res_country": "GBR",
        "purpose": "10", "note": None, "stay_from": None, "stay_to": None,
        "signature_png": signature, "entered_by": "host", "identity_verified_at": "x",
        "passport_photo_at": None, "submit_state": reporting.PENDING,
    }
    row.update(over)
    return row


def test_an_unsigned_child_is_complete(stay):
    reservation = _reservation(stay)
    child = _guest(_insert(stay, "Kid", _born(stay, 10), signature=""))
    assert "signature" not in _issue_fields(child, reservation)
    assert reporting.guest_is_complete(child, reservation) is True
    assert reporting.guest_under_15(child, reservation) is True
    assert reporting.guest_has_signature(child) is False
    assert reporting.guest_signature_settled(child, reservation) is True


def test_15_to_17_still_sign(stay):
    reservation = _reservation(stay)
    for years in (16, 17):
        teen = _guest(_insert(stay, f"Teen{years}", _born(stay, years), signature=""))
        assert "signature" in _issue_fields(teen, reservation)
        assert reporting.guest_is_complete(teen, reservation) is False
        assert reporting.guest_signature_settled(teen, reservation) is False


def test_the_boundary_with_fixed_dates():
    assert reporting.guest_under_15(_row("21102011", ""), RES) is True
    assert reporting.guest_under_15(_row("20102011", ""), RES) is False
    assert reporting.guest_under_15(_row("21102011", "", stay_from="2026-10-22"), RES) is False
    assert reporting.guest_under_15(_row("21102011", ""), {"date_from": "", "date_to": ""}) is False


def test_a_childs_imported_or_junk_value_is_judged_as_before():
    issue = reporting.guest_signature_issue
    assert issue("", under_15=True) is None
    assert issue("   ", under_15=True) is None
    assert issue("", under_15=False) is not None
    for value in ("imported", "junk", "data:image/png;base64,QUJ"):
        before = issue(value)
        after = issue(value, under_15=True)
        assert (before is None) == (after is None)
        assert before is None or (before.field, before.message) == (after.field, after.message)
    assert issue("imported", allow_imported=False, under_15=True) is not None


# --- b2. host send and stay fee -----------------------------------------------

def test_the_host_can_send_a_stay_whose_only_pending_guest_is_an_unsigned_child(stay):
    db.update("reservation", stay["reservation_id"], {"expected_guests_override": 1})
    child_id = _insert(stay, "Kid", _born(stay, 10), signature="", is_lead=1)
    reservation, apartment = _reservation(stay), _apartment(stay)
    progress = reporting.reservation_progress(reservation)
    guests = progress["reportable"]
    assert [g["id"] for g in reporting.pending_reportable(guests, reservation)] == [child_id]
    assert reporting.pending_reportable(guests) == []  # no reservation: as before the brief
    controls = reporting.send_controls(reservation, apartment, progress)
    assert controls["send_enabled"] is True
    assert controls["send_hint_key"] != "hint.need_signature"


def test_an_unsigned_15_year_old_still_blocks_the_send(stay):
    db.update("reservation", stay["reservation_id"], {"expected_guests_override": 1})
    _insert(stay, "Teen", _born(stay, 16), signature="", is_lead=1)
    reservation, apartment = _reservation(stay), _apartment(stay)
    progress = reporting.reservation_progress(reservation)
    assert reporting.pending_reportable(progress["reportable"], reservation) == []
    controls = reporting.send_controls(reservation, apartment, progress)
    assert controls["send_enabled"] is False
    assert controls["send_hint_key"] == "hint.need_signature"


def test_the_stay_fee_unsigned_count_ignores_children_under_15(stay):
    apartment = _apartment(stay)
    month = stay["today"].replace(day=1)
    first, last = stay_fee.period_bounds(stay_fee.cadence_of(apartment), month)
    last = max(last, stay["today"] + timedelta(days=3))

    child_id = _insert(stay, "Kid", _born(stay, 10), signature="")
    assert stay_fee.unsigned_stays(stay["apartment_id"], first, last) == 0
    assert stay_fee.property_period(apartment, month, live_only=True)["unsigned_guests"] == 0

    db.update("guest", child_id, {"birth_date": _born(stay, 16)})
    assert stay_fee.unsigned_stays(stay["apartment_id"], first, last) == 1
    assert stay_fee.property_period(apartment, month, live_only=True)["unsigned_guests"] == 1


# --- c. filing unchanged ------------------------------------------------------

def test_the_envelope_is_the_same_with_and_without_a_child_signature_or_link(stay, monkeypatch):
    db.update("reservation", stay["reservation_id"], {"expected_guests_override": 2})
    adult_id = _insert(stay, "Adult", "01011990", is_lead=1)
    child_id = _insert(stay, "Kid", _born(stay, 10), signature="", signed_at=None)
    apartment = _apartment(stay)

    real = UbyportClient("https://ubyport.invalid", use_ntlm=False)
    captured = []

    def capture(_self, *args):
        captured.extend(a for a in args if isinstance(a, str) and a.startswith("<?xml"))
        return SUCCESS_RESPONSE

    monkeypatch.setattr(UbyportClient, "_post", capture)
    monkeypatch.setattr(reporting, "client_for", lambda *_a, **_k: real)
    monkeypatch.setattr(reporting.validation, "validate_apartment", lambda _a: [])

    pairs = reporting.collect_sendable(stay["apartment_id"], ignore_automation=True)
    assert sorted(g["id"] for g, _r in pairs) == sorted([adult_id, child_id])
    payloads = {g["id"]: reporting.guest_payload(g, r) for g, r in pairs}
    order = [g["id"] for g, _r in pairs]
    reservation = pairs[0][1]

    def envelope():
        return soap.build_zapis_ubytovane(
            reporting.header_from_apartment(apartment),
            [reporting.guest_payload(_guest(i), reservation) for i in order],
            real.auth_code,
            client_module.include_wsa_header(),
        )

    expected = envelope()
    reporting.submit_batch(apartment, pairs, mode="manual")
    assert captured == [expected]

    # The same child with a drawn signature and a full link files the same bytes.
    db.update(
        "guest",
        child_id,
        {
            "signature_png": SIGNATURE,
            "signed_for_guest_id": adult_id,
            "signed_for_role": "parent",
            "signed_for_at": db.utcnow(),
            "signed_for_wording": reporting.SIGN_FOR_WORDING_VERSION,
        },
    )
    assert _guest(child_id)["signature_png"] == SIGNATURE
    assert _guest(child_id)["signed_for_guest_id"] == adult_id
    assert envelope() == expected
    for guest_id in order:
        assert reporting.guest_payload(_guest(guest_id), reservation) == payloads[guest_id]


# --- d. the save path ---------------------------------------------------------

def test_a_foreign_child_saves_without_a_signature(stay):
    browser = _client(stay)
    child = _save(browser, stay, "Kid", f"1.1.{stay['today'].year - 10}", signature="")
    assert not child["signature_png"]
    assert child["signed_at"] is None
    assert child["filled_at"]
    assert child["submit_state"] == reporting.PENDING
    assert _link(child["id"]) == (None, None, None, None)


def test_a_czech_child_is_not_required(stay):
    browser = _client(stay)
    child = _save(
        browser, stay, "Kid", f"1.1.{stay['today'].year - 10}", signature="",
        nationality="CZE", res_country="CZE", res_city="Brno",
    )
    assert child["submit_state"] == reporting.NOT_REQUIRED
    assert not child["signature_png"]


def test_a_drawn_signature_posted_for_a_child_is_not_kept(stay):
    browser = _client(stay)
    child = _save(browser, stay, "Kid", f"1.1.{stay['today'].year - 10}")
    assert not child["signature_png"]
    assert child["signed_at"] is None


def test_a_15_year_old_and_an_adult_must_still_sign(stay):
    browser = _client(stay)
    for name, years in (("Teen", 16), ("Adult", 36)):
        response = _post(browser, stay, name, f"1.1.{stay['today'].year - years}", signature="")
        assert response.status_code == 422
        assert _saved(stay, name) is None


# --- e. adult first, then the child -------------------------------------------

def test_the_child_names_the_adult_who_signs_for_them(stay):
    browser = _client(stay)
    adult = _save(browser, stay, "Adult", "1.1.1990")
    child = _save(
        browser, stay, "Kid", f"1.1.{stay['today'].year - 10}", signature="",
        signed_by=str(adult["id"]), child_sign_role="parent",
    )
    assert child["signed_for_guest_id"] == adult["id"]
    assert child["signed_for_role"] == "parent"
    assert child["signed_for_at"]
    assert child["signed_for_wording"] == "u15-2026-11-10"
    assert child["submit_state"] == reporting.PENDING
    assert not child["signature_png"]

    # An edit without a posted signer keeps the link.
    again = _save(
        browser, stay, "Kid", f"1.1.{stay['today'].year - 10}", signature="",
        guest_id=str(child["id"]), doc_number=child["doc_number"],
    )
    assert again["id"] == child["id"]
    assert again["signed_for_guest_id"] == adult["id"]


def test_no_link_for_a_signer_who_may_not_sign(stay):
    browser = _client(stay)
    own_adult = _save(browser, stay, "Adult", "1.1.1990")
    own_teen = _save(browser, stay, "Teen", f"1.1.{stay['today'].year - 17}")
    _other_apartment, other_reservation = _seed_stay(OTHER_TOKEN, stay["owner"])
    elsewhere = _insert(stay, "Elsewhere", "01011990", reservation_id=other_reservation)
    another_device = _insert(stay, "Stranger", "01011990")

    cases = [
        ("Kone", str(another_device), "parent"),  # saved on another phone
        ("Ktwo", str(elsewhere), "parent"),  # another reservation
        ("Kthree", str(own_teen["id"]), "parent"),  # 17 years old
        ("Kfour", str(own_adult["id"]), "boss"),  # not a role
        ("Kfive", "abc", "parent"),
    ]
    for name, signed_by, role in cases:
        child = _save(
            browser, stay, name, f"1.1.{stay['today'].year - 10}", signature="",
            signed_by=signed_by, child_sign_role=role,
        )
        assert _link(child["id"]) == (None, None, None, None), name

    # An adult this device saved whose signature is the host's paper marker.
    db.update("guest", own_adult["id"], {"signature_png": reporting.IMPORTED_SIGNATURE})
    child = _save(
        browser, stay, "Ksix", f"1.1.{stay['today'].year - 10}", signature="",
        signed_by=str(own_adult["id"]), child_sign_role="parent",
    )
    assert _link(child["id"]) == (None, None, None, None)


def test_a_linked_child_corrected_to_15_loses_the_link_and_must_sign(stay):
    browser = _client(stay)
    adult = _save(browser, stay, "Adult", "1.1.1990")
    child = _save(
        browser, stay, "Kid", f"1.1.{stay['today'].year - 10}", signature="",
        signed_by=str(adult["id"]), child_sign_role="responsible_adult",
    )
    older = f"1.1.{stay['today'].year - 16}"
    edit = {"guest_id": str(child["id"]), "doc_number": child["doc_number"]}

    response = _post(browser, stay, "Kid", older, signature="", **edit)
    assert response.status_code == 422
    assert _link(child["id"])[0] == adult["id"]  # nothing was saved

    saved = _save(browser, stay, "Kid", older, **edit)
    assert saved["id"] == child["id"]
    assert saved["signature_png"] == SIGNATURE
    assert saved["signed_at"]
    assert _link(child["id"]) == (None, None, None, None)


# --- f. child first, then the adult -------------------------------------------

def test_the_adult_links_the_children_without_touching_their_filing_columns(stay):
    browser = _client(stay)
    reservation = _reservation(stay)
    kid = _save(browser, stay, "Kid", f"1.1.{stay['today'].year - 10}", signature="")
    filed = _save(browser, stay, "Filed", f"1.1.{stay['today'].year - 8}", signature="")
    db.execute(
        "UPDATE guest SET submit_state = ?, submit_attempts = 2, last_errors = ? WHERE id = ?",
        (reporting.SENT, "kept", filed["id"]),
    )
    teen = _save(browser, stay, "Teen", f"1.1.{stay['today'].year - 16}")
    stranger = _insert(stay, "Stranger", _born(stay, 10), signature="")
    taken = _save(browser, stay, "Taken", f"1.1.{stay['today'].year - 9}", signature="")
    first_adult = _insert(stay, "First", "01011985")
    db.execute(
        "UPDATE guest SET signed_for_guest_id = ?, signed_for_role = 'parent', "
        "signed_for_at = 'then', signed_for_wording = 'old' WHERE id = ?",
        (first_adult, taken["id"]),
    )
    ids = [kid["id"], filed["id"], teen["id"], stranger, taken["id"]]
    before = {i: _snapshot(i, reservation) for i in ids}

    # No role: nobody is linked.
    silent = _save(browser, stay, "Silent", "1.1.1991", sign_for_ids=[str(i) for i in ids])
    assert all(_guest(i)["signed_for_guest_id"] in (None, first_adult) for i in ids)
    assert _link(kid["id"]) == (None, None, None, None)

    adult = _save(
        browser, stay, "Adult", "1.1.1990",
        sign_for_ids=[str(i) for i in ids] + [str(kid["id"]), "x"],
        sign_for_role="responsible_adult",
    )
    assert adult["id"] != silent["id"]
    for child_id in (kid["id"], filed["id"]):
        row = _guest(child_id)
        assert row["signed_for_guest_id"] == adult["id"]
        assert row["signed_for_role"] == "responsible_adult"
        assert row["signed_for_at"]
        assert row["signed_for_wording"] == "u15-2026-11-10"
    assert _guest(filed["id"])["submit_state"] == reporting.SENT
    assert _link(teen["id"]) == (None, None, None, None)  # 15 or over
    assert _link(stranger) == (None, None, None, None)  # another device's child
    assert _link(taken["id"]) == (first_adult, "parent", "then", "old")  # the first adult wins
    assert _link(adult["id"]) == (None, None, None, None)
    assert {i: _snapshot(i, reservation) for i in ids} == before


def test_a_17_year_old_cannot_sign_for_a_child(stay):
    browser = _client(stay)
    kid = _save(browser, stay, "Kid", f"1.1.{stay['today'].year - 10}", signature="")
    _save(
        browser, stay, "Teen", f"1.1.{stay['today'].year - 17}",
        sign_for_ids=[str(kid["id"])], sign_for_role="parent",
    )
    assert _link(kid["id"]) == (None, None, None, None)


# --- g. remove ----------------------------------------------------------------

def test_removing_the_adult_clears_the_link(stay):
    browser = _client(stay)
    reservation = _reservation(stay)
    kid = _save(browser, stay, "Kid", f"1.1.{stay['today'].year - 10}", signature="")
    adult = _save(
        browser, stay, "Adult", "1.1.1990",
        sign_for_ids=[str(kid["id"])], sign_for_role="parent",
    )
    assert _link(kid["id"])[0] == adult["id"]
    before = _snapshot(kid["id"], reservation)

    response = browser.post(
        f"/l/{TOKEN}/{stay['reservation_id']}/remove/{adult['id']}?lang=en",
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text[-400:]
    assert _guest(adult["id"]) is None
    assert _link(kid["id"]) == (None, None, None, None)
    assert _snapshot(kid["id"], reservation) == before


# --- h. the record, the house book --------------------------------------------

def _linked_child(stay, adult_id, name="Kid"):
    return _insert(
        stay, name, _born(stay, 10), signature="", signed_at=None,
        signed_for_guest_id=adult_id, signed_for_role="parent",
        signed_for_at="2026-11-10T09:00:00+00:00",
        signed_for_wording=reporting.SIGN_FOR_WORDING_VERSION,
    )


def test_the_signature_record(stay):
    reservation = _reservation(stay)
    adult_id = _insert(stay, "Adult", "01011990")
    child_id = _linked_child(stay, adult_id)
    record = lambda guest_id: reporting.signature_record(_guest(guest_id), reservation)  # noqa: E731

    assert record(child_id) == {
        "kind": "signed_for",
        "text": (
            "Signed by Adult Under for Kid Under, as parent or legal guardian, "
            "2026-11-10T09:00:00+00:00, wording u15-2026-11-10"
        ),
    }
    assert record(adult_id) == {"kind": "own", "text": ""}
    exempt = {"kind": "exempt", "text": EXEMPT_TEXT}
    assert record(_insert(stay, "Free", _born(stay, 10), signature="")) == exempt
    assert record(_insert(stay, "Paper", "01011990", signature="imported")) == {
        "kind": "imported", "text": "Signature on paper (host)",
    }
    assert record(_insert(stay, "None", "01011990", signature="")) == {"kind": "missing", "text": ""}
    assert record(_insert(stay, "Teen", _born(stay, 16), signature="")) == {"kind": "missing", "text": ""}

    # The adult no longer holds a valid drawn signature.
    db.update("guest", adult_id, {"signature_png": reporting.IMPORTED_SIGNATURE})
    assert record(child_id) == exempt
    # The adult is no longer certainly 18.
    db.update("guest", adult_id, {"signature_png": SIGNATURE, "birth_date": _born(stay, 17)})
    assert record(child_id) == exempt
    db.update("guest", adult_id, {"birth_date": "01011990"})
    assert record(child_id)["kind"] == "signed_for"
    # The adult row moved to another reservation, then is gone.
    _other_apartment, other_reservation = _seed_stay(OTHER_TOKEN, stay["owner"])
    db.execute("UPDATE guest SET reservation_id = ? WHERE id = ?", (other_reservation, adult_id))
    assert record(child_id) == exempt
    db.execute("DELETE FROM guest WHERE id = ?", (adult_id,))
    assert record(child_id) == exempt


def test_the_house_book_csv_pdf_and_page(stay):
    adult_id = _insert(stay, "Adult", "01011990")
    linked = _linked_child(stay, adult_id, "Linked")
    free = _insert(stay, "Free", _born(stay, 10), signature="")
    unsigned = _insert(stay, "Unsigned", "01011991", signature="")

    rows = {
        row["_guest_id"]: row
        for row in housebook.housebook_rows(owner_user_id=stay["owner"])
    }
    assert rows[adult_id]["signed"] == "yes"
    assert rows[linked]["signed"] == "by adult"
    assert rows[free]["signed"] == "not required"
    assert rows[unsigned]["signed"] == "no"

    for guest_id in (linked, free, adult_id):
        assert housebook.registration_form_pdf(guest_id).startswith(b"%PDF")

    client = TestClient(app)
    response = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303
    page = client.get("/housebook?lang=en").text
    assert '<span class="pill p-ok">By an adult</span>' in page
    assert '<span class="pill p-ok">Not required (under 15)</span>' in page
    assert '<span class="pill p-ok">Yes</span>' in page
    assert '<span class="pill p-warn">No</span>' in page
