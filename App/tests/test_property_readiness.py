"""The property form opens with a checklist, not a red run-on paragraph.

The form does two jobs — getting a guest in and getting the police register
filed — and the old banner answered neither: it ran eight validation messages
together, in English even on the Czech page, with nothing to click. The
checklist has one list per job, every item a link to the field that answers it,
and it says out loud when the property is already good enough to invite a guest.

The stay-fee and invoice fields the two planned features add are optional by
design and must never be counted here, so the reporting list is pinned to the
eight fields validate_apartment() calls errors.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, db, host_i18n
from app.main import app
from tests.conftest import login_as

USERNAME = "property-readiness-host"

REPORT_FIELDS = (
    "uby_idub",
    "uby_mark",
    "uby_name",
    "addr_house_no",
    "addr_zip",
    "addr_obec",
    "uby_ws_user",
    "uby_ws_password",
)


def _cleanup():
    ids = [
        row["id"]
        for row in db.query("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    ]
    for user_id in ids:
        apartment_ids = [
            row["id"]
            for row in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (user_id,))
        ]
        for apartment_id in apartment_ids:
            db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment_id,))
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


def _owner_id():
    return db.query_one(
        "SELECT id FROM user_account WHERE username = ?", (USERNAME,)
    )["id"]


def _label(text: str, field: str) -> str:
    """The text of the <label> that belongs to one field."""
    marker = f'<label for="{field}">'
    start = text.index(marker) + len(marker)
    return text[start:text.index("</label>", start)]


def _checklist(text: str) -> str:
    """Just the readiness section, so the section nav cannot be mistaken for it."""
    start = text.index('<section class="readiness">')
    return text[start:text.index("</section>", start)]


def _complete_apartment(apartment_id: int, **overrides):
    """Everything the police register needs, so only the overrides are missing."""
    values = {
        "uby_idub": "123456789012",
        "uby_mark": "AAKLI",
        "uby_name": "Vinohrady Flat",
        "uby_ws_user": "uby-ws1a2b3c",
        "uby_ws_password_enc": db.encrypt_secret("ws-secret"),
        "addr_obec": "Praha",
        "addr_house_no": "12",
        "addr_zip": "12000",
    }
    values.update(overrides)
    db.update("apartment", apartment_id, values)


def _add_stay(apartment_id: int):
    now = db.utcnow()
    db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            "uid": "readiness-stay-1",
            "date_from": now[:10],
            "date_to": now[:10],
            "summary": "Direct booking",
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    auth.create_account(f"{USERNAME}@example.test", "Readiness Host", username=USERNAME)
    entity_id = db.insert(
        "legal_entity",
        {
            "name": "Readiness s.r.o.",
            "seat": "Praha",
            "ico": "12345678",
            "contact_email": "host@readiness.test",
            "owner_user_id": _owner_id(),
            "created_at": db.utcnow(),
        },
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": _owner_id(),
            "internal_name": "Readiness Flat",
            "addr_obec": "Praha",
            "addr_house_no": "12",
            "addr_zip": "12000",
            "permalink_token": "propertyreadiness1",
            "permalink_pin": "123456",
            "automation_mode": "manual",
            "submit_after_hours": 24,
            "active": 1,
            "created_at": db.utcnow(),
        },
    )
    client = TestClient(app)
    response = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    try:
        yield client, apartment_id
    finally:
        _cleanup()


def test_the_property_form_opens_with_two_lists(host):
    client, apartment_id = host

    page = client.get(f"/apartments/{apartment_id}?lang=en")

    assert page.status_code == 200
    assert "Ready to invite guests" in page.text
    assert "Ready to report to the police" in page.text


def test_the_run_on_red_banner_is_gone(host):
    client, apartment_id = host

    page = client.get(f"/apartments/{apartment_id}?lang=en")

    assert "cannot report to UbyPort yet" not in page.text
    assert '<div class="banner warning">' not in page.text


def test_the_invite_list_names_the_three_things_a_guest_needs(host):
    client, apartment_id = host

    page = client.get(f"/apartments/{apartment_id}?lang=en")

    assert "Name" in page.text
    assert "Operator with contact e-mail" in page.text
    assert "Stays arriving (calendar or manual)" in page.text


def test_a_property_with_no_calendar_and_no_stay_says_so_with_a_link(host):
    client, apartment_id = host

    page = client.get(f"/apartments/{apartment_id}?lang=en")

    assert "Missing: Stays arriving (calendar or manual)" in page.text
    assert 'href="#calendars"' in page.text


def test_missing_reporting_items_link_to_their_own_section(host):
    client, apartment_id = host
    _complete_apartment(apartment_id, uby_idub="", uby_mark="", uby_name="", addr_zip="")

    page = client.get(f"/apartments/{apartment_id}?lang=en")
    checklist = _checklist(page.text)

    assert "Missing: IDUB" in checklist
    assert "Missing: Facility abbreviation" in checklist
    assert "Missing: Facility name" in checklist
    assert "Missing: Postcode" in checklist
    # The three UbyPort fields sit in #ubyport; the postcode sits in #address.
    assert checklist.count('href="#ubyport"') == 3
    assert checklist.count('href="#address"') == 1


def test_a_complete_property_says_you_can_send_the_guest_link(host):
    client, apartment_id = host
    _complete_apartment(apartment_id)
    _add_stay(apartment_id)

    page = client.get(f"/apartments/{apartment_id}?lang=en")

    assert "You can send the guest link now." in page.text
    assert "Copy guest link" in page.text
    assert "Missing:" not in page.text


def test_an_incomplete_property_does_not_offer_the_guest_link(host):
    client, apartment_id = host

    page = client.get(f"/apartments/{apartment_id}?lang=en")

    assert "You can send the guest link now." not in page.text
    assert "Copy guest link" not in page.text


def test_the_validation_reason_survives_from_the_old_banner(host):
    client, apartment_id = host
    _complete_apartment(apartment_id, uby_idub="123")

    page = client.get(f"/apartments/{apartment_id}?lang=en")
    checklist = _checklist(page.text)

    assert "Missing: IDUB" in checklist
    assert "IDUB must be 12-14 letters or digits." in checklist


def test_the_validation_reason_is_translated_on_the_czech_page(host):
    client, apartment_id = host
    _complete_apartment(apartment_id, uby_idub="123")

    page = client.get(f"/apartments/{apartment_id}?lang=cs")

    assert "IDUB má 12–14 písmen nebo číslic." in _checklist(page.text)


def test_the_czech_page_carries_the_czech_copy(host):
    client, apartment_id = host

    page = client.get(f"/apartments/{apartment_id}?lang=cs")

    assert "Připraveno pro hosty" in page.text
    assert "Připraveno k hlášení policii" in page.text
    assert "Chybí:" in page.text


def test_the_eight_reporting_fields_keep_localized_labels_and_controls_without_badges(host):
    client, apartment_id = host

    fields = (
        ("uby_idub", None, "text"),
        ("uby_mark", "apartment.form.ubyport.mark_label", "text"),
        ("uby_name", "automation.facility_name", "text"),
        ("addr_house_no", "apartment.form.addr.house_no", "text"),
        ("addr_zip", "apartment.form.addr.zip", "text"),
        ("addr_obec", "apartment.form.addr.obec", "text"),
        ("uby_ws_user", "automation.login", "text"),
        ("uby_ws_password", "automation.password", "password"),
    )

    for lang in ("en", "cs"):
        page = client.get(f"/apartments/{apartment_id}?lang={lang}")
        badge = host_i18n.STRINGS[lang]["apartment.form.needed_to_report"]
        assert badge not in page.text
        for field, label_key, input_type in fields:
            expected_label = "IDUB" if label_key is None else host_i18n.STRINGS[lang][label_key]
            label = _label(page.text, field)
            assert expected_label in label, (lang, field, expected_label)
            assert badge not in label, (lang, field)
            assert (
                f'type="{input_type}" id="{field}" name="{field}"' in page.text
            ), (lang, field, input_type)


def test_the_optional_address_fields_are_not_tagged(host):
    client, apartment_id = host

    page = client.get(f"/apartments/{apartment_id}?lang=en")

    for field in ("addr_street", "addr_obec_cast", "addr_orient_no", "city_en", "uby_contact"):
        assert "needed to report" not in _label(page.text, field), field


def test_the_reporting_list_is_exactly_eight_items(host):
    client, apartment_id = host

    page = client.get(f"/apartments/{apartment_id}?lang=en")

    # Four for the guest (name, operator, controller, stays) and eight for the
    # police: the stay-fee and invoice fields the two planned features add are
    # optional and must never be counted here.
    assert page.text.count('<li class="readiness-item') == 12
