"""1092: one writer for the guest's head count, with a floor, a ceiling and a lock.

Before this a claimed lead (or, with mail off, anyone with the link) could post
``party_size=1`` with three people registered, and an ``immediate`` apartment
filed the stay at once with people missing.
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app import claim, db, headcount, mail, reporting
from app.main import app
from app.routes import guest
from tests import test_guest_navigation as nav
from tests.conftest import complete_guest_claim

EMAIL = "lead@example.test"
PEOPLE = [
    {"surname": "Smith", "first_name": "John", "doc_number": "P1000001"},
    {"surname": "Jones", "first_name": "Mary", "doc_number": "P1000002"},
    {"surname": "Brown", "first_name": "Adam", "doc_number": "P1000003"},
    {"surname": "White", "first_name": "Emma", "doc_number": "P1000004"},
]


@pytest.fixture
def stay():
    token, stay_id, _right = nav._make_apartment_with_stays()
    db.execute("DELETE FROM rate_limit_event")
    db.execute("DELETE FROM audit WHERE action LIKE 'reservation_declared_guests%'")
    try:
        yield token, stay_id
    finally:
        nav._cleanup()


def _browser(token, stay_id, party_size=2):
    browser = TestClient(app)
    browser.cookies.set(guest.LANG_COOKIE, "en")
    complete_guest_claim(browser, token, stay_id, email=EMAIL, party_size=party_size)
    return browser


def _save(browser, token, stay_id, person=0, **overrides):
    data = nav._form(**PEOPLE[person])
    data.update(overrides)
    return browser.post(
        f"/l/{token}/{stay_id}/save",
        data=data,
        files=nav._passport_files(),
        follow_redirects=False,
    )


def _party(browser, token, stay_id, count, **extra):
    db.execute("DELETE FROM rate_limit_event")
    data = {"party_size": str(count)}
    data.update(extra)
    return browser.post(f"/l/{token}/{stay_id}/party", data=data, follow_redirects=False)


def _started_row(stay_id):
    """A person someone began and did not finish: live, not complete."""
    now = db.utcnow()
    return db.insert(
        "guest",
        {
            "reservation_id": stay_id,
            "surname": "STARTED",
            "entered_by": "guest",
            "is_lead": 0,
            "created_at": now,
            "updated_at": now,
        },
    )


def _count(stay_id):
    return db.query_one("SELECT declared_guests FROM reservation WHERE id = ?", (stay_id,))[
        "declared_guests"
    ]


def _live(stay_id):
    return db.query_one(
        "SELECT COUNT(*) AS n FROM guest WHERE reservation_id = ? AND archived_at IS NULL",
        (stay_id,),
    )["n"]


def _audit(stay_id, suffix):
    return db.query(
        "SELECT * FROM audit WHERE action = ? AND detail LIKE ?",
        (f"reservation_declared_guests_{suffix}", f"id={stay_id} %"),
    )


def _reservation(stay_id):
    return db.query_one("SELECT * FROM reservation WHERE id = ?", (stay_id,))


def _apartment(token):
    return db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (token,))


def _three_rows(token, stay_id):
    """Declared 3; two complete people and one started row."""
    browser = _browser(token, stay_id, party_size=3)
    assert _save(browser, token, stay_id, 0).status_code == 303
    assert _save(browser, token, stay_id, 1).status_code == 303
    _started_row(stay_id)
    assert _live(stay_id) == 3
    assert _count(stay_id) == 3
    db.execute("DELETE FROM audit WHERE action LIKE 'reservation_declared_guests%'")
    return browser


# --- floor -----------------------------------------------------------------


@pytest.mark.parametrize("typed", [2, 1])
def test_a_claimed_guest_cannot_lower_the_count_below_the_live_rows(stay, typed):
    token, stay_id = stay
    browser = _three_rows(token, stay_id)
    db.update("reservation", stay_id, {"declared_guests": 4})
    response = _party(browser, token, stay_id, typed)
    assert response.status_code == 303
    assert "party_error=1" in response.headers["location"]
    assert _count(stay_id) == 4
    assert len(_audit(stay_id, "refused")) == 1
    assert not _audit(stay_id, "set")


def test_the_count_may_be_lowered_to_the_live_rows_and_the_audit_holds_numbers_only(stay):
    token, stay_id = stay
    browser = _three_rows(token, stay_id)
    db.update("reservation", stay_id, {"declared_guests": 4})
    response = _party(browser, token, stay_id, 3)
    assert response.status_code == 303
    assert "party_error" not in response.headers["location"]
    assert _count(stay_id) == 3
    rows = _audit(stay_id, "set")
    assert len(rows) == 1
    assert rows[0]["actor"] == "guest"
    assert re.fullmatch(r"id=\d+ from=4 to=3 source=party", rows[0]["detail"])
    assert not _audit(stay_id, "refused")


# --- ceiling, host override ---------------------------------------------------


def test_the_ceiling_is_sixty(stay):
    token, stay_id = stay
    browser = _browser(token, stay_id, party_size=2)
    for typed in (61, 0):
        response = _party(browser, token, stay_id, typed)
        assert "party_error=1" in response.headers["location"]
        assert _count(stay_id) == 2
    owner = _apartment(token)["owner_user_id"]
    assert headcount.set_declared_guests(stay_id, 61, source="party", owner_user_id=owner) == "above_ceiling"
    assert headcount.set_declared_guests(stay_id, 0, source="party", owner_user_id=owner) == "out_of_range"
    assert _count(stay_id) == 2
    assert not _audit(stay_id, "refused")

    response = _party(browser, token, stay_id, 60)
    assert "party_error" not in response.headers["location"]
    assert _count(stay_id) == 60

    again = browser.post(f"/l/{token}/{stay_id}/another", follow_redirects=False)
    assert again.status_code == 303
    assert _count(stay_id) == 60


def test_a_host_set_count_is_never_written_over(stay):
    token, stay_id = stay
    browser = _browser(token, stay_id, party_size=2)
    db.execute("DELETE FROM audit WHERE action LIKE 'reservation_declared_guests%'")
    db.update("reservation", stay_id, {"expected_guests_override": 4})
    response = _party(browser, token, stay_id, 3)
    assert response.status_code == 303
    assert "party_error" not in response.headers["location"]
    assert _count(stay_id) == 2
    assert not _audit(stay_id, "set") and not _audit(stay_id, "refused")


# --- mail off -------------------------------------------------------------------


def test_with_mail_off_the_open_party_post_has_the_same_floor(stay, monkeypatch):
    token, stay_id = stay
    _three_rows(token, stay_id)
    db.update("reservation", stay_id, {"declared_guests": 4})
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    anyone = TestClient(app)
    response = _party(anyone, token, stay_id, 1)
    assert response.status_code == 303
    assert "party_error=1" in response.headers["location"]
    assert _count(stay_id) == 4
    assert len(_audit(stay_id, "refused")) == 1

    response = _party(anyone, token, stay_id, 3)
    assert "party_error" not in response.headers["location"]
    assert _count(stay_id) == 3


# --- the count waits for the confirmed e-mail -----------------------------------


def _start(token, stay_id, party_size, *, email=EMAIL, resend=False):
    db.execute("DELETE FROM rate_limit_event")
    db.execute(
        "UPDATE reservation_claim SET updated_at = ? WHERE reservation_id = ?",
        ("2000-01-01T00:00:00+00:00", stay_id),
    )
    ok, err, secret = claim.start_claim(
        _reservation(stay_id),
        _apartment(token),
        email=email,
        party_size=party_size,
        lang="en",
        resend=resend,
    )
    assert ok, err
    return secret


def test_an_unconfirmed_claim_does_not_touch_the_count_and_confirm_applies_it_once(stay):
    token, stay_id = stay
    db.update("reservation", stay_id, {"declared_guests": 3})
    secret = _start(token, stay_id, 1)
    assert _count(stay_id) == 3
    assert claim.confirm(_reservation(stay_id), secret) is True
    assert _count(stay_id) == 1
    assert len(_audit(stay_id, "set")) == 1
    assert _audit(stay_id, "set")[0]["detail"].endswith("source=claim_confirm")
    pending = db.query_one(
        "SELECT declared_guests FROM reservation_claim WHERE reservation_id = ?", (stay_id,)
    )
    assert pending["declared_guests"] is None

    # The spent link cannot apply anything a second time.
    db.update("reservation", stay_id, {"declared_guests": 3})
    assert claim.confirm(_reservation(stay_id), secret) is False
    assert _count(stay_id) == 3
    assert len(_audit(stay_id, "set")) == 1


def test_confirm_keeps_the_old_count_when_the_typed_one_is_below_the_rows(stay):
    token, stay_id = stay
    db.update("reservation", stay_id, {"declared_guests": 3})
    _started_row(stay_id)
    _started_row(stay_id)
    secret = _start(token, stay_id, 1)
    assert claim.confirm(_reservation(stay_id), secret) is True
    assert _count(stay_id) == 3
    assert len(_audit(stay_id, "refused")) == 1
    assert not _audit(stay_id, "set")


def test_a_hold_that_expires_unconfirmed_never_changes_the_count(stay):
    token, stay_id = stay
    db.update("reservation", stay_id, {"declared_guests": 3})
    secret = _start(token, stay_id, 1)
    db.execute(
        "UPDATE reservation_claim SET provisional_until = ? WHERE reservation_id = ?",
        ("2000-01-01T00:00:00+00:00", stay_id),
    )
    claim.expire_holds()
    assert claim.confirm(_reservation(stay_id), secret) is False
    assert _count(stay_id) == 3
    assert not _audit(stay_id, "set")


def test_on_a_claimed_stay_the_leads_address_alone_cannot_change_the_count(stay, monkeypatch):
    token, stay_id = stay
    _browser(token, stay_id, party_size=3)
    assert _count(stay_id) == 3
    db.execute("DELETE FROM audit WHERE action LIKE 'reservation_declared_guests%'")
    db.execute(
        "UPDATE reservation_claim SET updated_at = ? WHERE reservation_id = ?",
        ("2000-01-01T00:00:00+00:00", stay_id),
    )
    secrets = []
    real = claim.start_claim

    def _spy(*args, **kwargs):
        result = real(*args, **kwargs)
        secrets.append(result[2])
        return result

    monkeypatch.setattr(claim, "start_claim", _spy)
    stranger = TestClient(app)
    response = _party(stranger, token, stay_id, 1, guest_email=EMAIL)
    assert response.status_code == 303
    assert "claim_sent=1" in response.headers["location"]
    assert _count(stay_id) == 3
    assert secrets and secrets[0]
    assert claim.confirm(_reservation(stay_id), secrets[0]) is True
    assert _count(stay_id) == 3
    assert not _audit(stay_id, "set") and not _audit(stay_id, "refused")


def test_an_old_number_on_a_claimed_row_is_never_applied_by_a_resend_link(stay):
    token, stay_id = stay
    _browser(token, stay_id, party_size=3)
    db.execute("DELETE FROM audit WHERE action LIKE 'reservation_declared_guests%'")
    secret = _start(token, stay_id, 1, resend=True)
    # A row written before 1092 could still hold a number while CLAIMED.
    db.execute(
        "UPDATE reservation_claim SET declared_guests = 5 WHERE reservation_id = ?", (stay_id,)
    )
    assert claim.confirm(_reservation(stay_id), secret) is True
    assert _count(stay_id) == 3
    assert not _audit(stay_id, "set") and not _audit(stay_id, "refused")


# --- filing -----------------------------------------------------------------------


def test_confirming_a_first_claim_on_a_complete_stay_files_it_after_the_block(stay, monkeypatch):
    token, stay_id = stay
    browser = _browser(token, stay_id, party_size=3)
    assert _save(browser, token, stay_id, 0).status_code == 303
    assert _save(browser, token, stay_id, 1).status_code == 303
    # As if the host had entered both people before any guest claimed the stay.
    db.execute("UPDATE guest SET entered_by = 'host' WHERE reservation_id = ?", (stay_id,))
    db.execute("DELETE FROM reservation_claim WHERE reservation_id = ?", (stay_id,))
    db.update("reservation", stay_id, {"declared_guests": None})
    db.update("apartment", _apartment(token)["id"], {"automation_mode": "immediate"})
    secret = _start(token, stay_id, 2)
    assert _count(stay_id) is None

    calls = []

    def _spy(apartment_id, reservation_id):
        calls.append((apartment_id, reservation_id, getattr(db._local, "depth", 0)))

    monkeypatch.setattr(reporting, "submit_stay_if_complete", _spy)
    lead = TestClient(app)
    response = lead.post(
        f"/l/{token}/{stay_id}/claim/confirm", data={"secret": secret}, follow_redirects=False
    )
    assert response.status_code == 303
    assert _count(stay_id) == 2
    assert calls == [(_apartment(token)["id"], stay_id, 0)]


def test_a_stay_is_never_filed_below_the_floor(stay):
    token, stay_id = stay
    browser = _browser(token, stay_id, party_size=3)
    assert _save(browser, token, stay_id, 0).status_code == 303
    assert _save(browser, token, stay_id, 1).status_code == 303
    apartment_id = _apartment(token)["id"]
    db.update("apartment", apartment_id, {"automation_mode": "immediate"})

    response = _party(browser, token, stay_id, 1)
    assert "party_error=1" in response.headers["location"]
    assert _count(stay_id) == 3

    def _nothing_filed():
        assert not _reservation(stay_id)["registration_completed_at"]
        assert not db.query(
            "SELECT 1 AS x FROM guest WHERE reservation_id = ? AND submit_state = ?",
            (stay_id, reporting.SENT),
        )
        assert not db.query(
            "SELECT 1 AS x FROM submission_claim WHERE guest_id IN "
            "(SELECT id FROM guest WHERE reservation_id = ?)",
            (stay_id,),
        )

    _nothing_filed()
    reporting.submit_stay_if_complete(apartment_id, stay_id)
    _nothing_filed()


def test_typing_the_stored_count_is_no_error_even_with_a_host_added_row(stay):
    token, stay_id = stay
    browser = _browser(token, stay_id, party_size=2)
    for _ in range(3):
        _started_row(stay_id)
    db.execute("DELETE FROM audit WHERE action LIKE 'reservation_declared_guests%'")
    response = _party(browser, token, stay_id, 2)
    assert response.status_code == 303
    assert "party_error" not in response.headers["location"]
    assert _count(stay_id) == 2
    assert not _audit(stay_id, "set") and not _audit(stay_id, "refused")


# --- /save -------------------------------------------------------------------------


def test_two_phones_cannot_both_take_the_last_slot(stay):
    token, stay_id = stay
    phone_a = _browser(token, stay_id, party_size=2)
    assert _save(phone_a, token, stay_id, 0).status_code == 303
    phone_b = _browser(token, stay_id, party_size=2)
    assert phone_a.get(f"/l/{token}/{stay_id}/new?lang=en").status_code == 200
    assert _save(phone_b, token, stay_id, 1).status_code == 303
    assert _live(stay_id) == 2

    late = _save(phone_a, token, stay_id, 2)
    assert late.status_code == 303
    assert late.headers["location"].split("?")[0].endswith(f"/{stay_id}")
    assert _live(stay_id) == 2 == _count(stay_id)


def test_a_started_row_does_not_block_a_new_person(stay):
    token, stay_id = stay
    browser = _browser(token, stay_id, party_size=2)
    assert _save(browser, token, stay_id, 0).status_code == 303
    _started_row(stay_id)
    assert browser.get(f"/l/{token}/{stay_id}/new?lang=en").status_code == 200
    assert _save(browser, token, stay_id, 1).status_code == 303
    assert _live(stay_id) == 3


def test_the_first_form_sets_the_count_with_one_audit_row(stay, monkeypatch):
    token, stay_id = stay
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    browser = TestClient(app)
    browser.cookies.set(guest.LANG_COOKIE, "en")
    assert _count(stay_id) is None
    assert _save(browser, token, stay_id, 0, party_size="2").status_code == 303
    assert _count(stay_id) == 2
    assert _live(stay_id) == 1
    rows = _audit(stay_id, "set")
    assert len(rows) == 1
    assert rows[0]["detail"].endswith("to=2 source=first_form")
    lead = db.query_one("SELECT is_lead FROM guest WHERE reservation_id = ?", (stay_id,))
    assert lead["is_lead"] == 1


def test_a_save_after_the_count_was_lowered_is_refused(stay):
    token, stay_id = stay
    browser = _browser(token, stay_id, party_size=3)
    assert _save(browser, token, stay_id, 0).status_code == 303
    assert _save(browser, token, stay_id, 1).status_code == 303
    response = _party(browser, token, stay_id, 2)
    assert "party_error" not in response.headers["location"]
    assert _count(stay_id) == 2
    late = _save(browser, token, stay_id, 2)
    assert late.status_code == 303
    assert _live(stay_id) == 2


def test_every_writer_takes_the_reservation_key(stay, monkeypatch):
    token, stay_id = stay
    taken = []
    real = db.lock_key

    def _spy(cur, name, key):
        taken.append((name, int(key)))
        return real(cur, name, key)

    monkeypatch.setattr(db, "lock_key", _spy)
    key = ("reservation", stay_id)

    secret = _start(token, stay_id, 3)
    assert key not in taken
    assert claim.confirm(_reservation(stay_id), secret) is True
    assert key in taken, "confirm"

    browser = _browser(token, stay_id, party_size=3)
    for label, call in (
        ("save", lambda: _save(browser, token, stay_id, 0)),
        ("party", lambda: _party(browser, token, stay_id, 4)),
        ("another", lambda: browser.post(f"/l/{token}/{stay_id}/another", follow_redirects=False)),
    ):
        del taken[:]
        assert call().status_code == 303
        assert key in taken, label
    assert _count(stay_id) == 5


# --- review fixes (attempt 2) --------------------------------------------------------


def test_after_a_host_release_the_claim_form_prefills_the_stays_own_count(stay):
    token, stay_id = stay
    browser = _browser(token, stay_id, party_size=3)
    assert _save(browser, token, stay_id, 0).status_code == 303
    claim.release(stay_id)
    held = db.query_one(
        "SELECT declared_guests FROM reservation_claim WHERE reservation_id = ?", (stay_id,)
    )
    assert held["declared_guests"] is None
    db.execute("DELETE FROM audit WHERE action LIKE 'reservation_declared_guests%'")

    newcomer = TestClient(app)
    newcomer.cookies.set(guest.LANG_COOKIE, "en")
    page = newcomer.get(f"/l/{token}/{stay_id}?lang=en", follow_redirects=True)
    assert page.status_code == 200
    field = re.search(r'<input[^>]*name="party_size"[^>]*>', page.text, re.S)
    assert field, "the claim form has no party_size field"
    assert re.search(r'value="3"', field.group(0)), field.group(0)

    # Confirming that default changes nothing and files nothing early.
    secret = _start(token, stay_id, 3, email="second@example.test")
    confirmed = newcomer.post(
        f"/l/{token}/{stay_id}/claim/confirm", data={"secret": secret}, follow_redirects=False
    )
    assert confirmed.status_code == 303
    assert _count(stay_id) == 3
    assert not _audit(stay_id, "set") and not _audit(stay_id, "refused")


def test_a_first_form_whose_count_fills_the_group_still_tries_to_file(stay, monkeypatch):
    token, stay_id = stay
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    browser = TestClient(app)
    browser.cookies.set(guest.LANG_COOKIE, "en")
    assert _save(browser, token, stay_id, 0, party_size="2").status_code == 303
    db.update("reservation", stay_id, {"declared_guests": None})

    calls = []
    monkeypatch.setattr(
        reporting, "submit_stay_if_complete", lambda a, r: calls.append((a, r))
    )
    late = _save(browser, token, stay_id, 1, party_size="1")
    assert late.status_code == 303
    assert _count(stay_id) == 1
    assert _live(stay_id) == 1
    assert calls == [(_apartment(token)["id"], stay_id)]


def test_a_filing_error_after_confirm_still_gives_the_guest_the_claim_cookie(stay, monkeypatch):
    token, stay_id = stay
    secret = _start(token, stay_id, 2)

    def _boom(_apartment_id, _reservation_id):
        raise RuntimeError("ubyport down")

    monkeypatch.setattr(reporting, "submit_stay_if_complete", _boom)
    lead = TestClient(app, raise_server_exceptions=False)
    lead.cookies.set(guest.LANG_COOKIE, "en")
    response = lead.post(
        f"/l/{token}/{stay_id}/claim/confirm", data={"secret": secret}, follow_redirects=False
    )
    assert response.status_code == 303
    assert "claim_error" not in response.headers["location"]
    assert "ubyhost_claim" in response.headers.get("set-cookie", "")
    assert _count(stay_id) == 2
    assert claim.is_claimed(claim.ensure_row(stay_id))
