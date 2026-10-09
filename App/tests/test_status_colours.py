"""One colour per concept, and amber only where a host can still act.

"ID not checked" was the stay's reporting status in amber, the warning colour,
even though DESIGN.md calls the check optional and sending is enabled in that
state — so a complete stay read as a problem the host had to solve. Setup
incomplete was red on the Properties list while the same state was amber on
Guest links, and red is meant for the states with legal consequences.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import auth, db, host_i18n, reporting
from app.main import app
from tests.conftest import login_as

USERNAME = "status-colour-host"
TOKEN = "statuscolourtoken"

# <span class="pill blue" title="...">Label</span>, with the title optional.
PILL = re.compile(
    r'<span class="pill ([a-z]+)"(?: title="([^"]*)")?>([^<]*)</span>',
)

_ENTITY_ID: int | None = None


def _cleanup():
    apartment = db.query_one(
        "SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,)
    )
    if apartment:
        db.execute(
            "DELETE FROM guest WHERE reservation_id IN "
            "(SELECT id FROM reservation WHERE apartment_id = ?)",
            (apartment["id"],),
        )
        db.execute(
            "DELETE FROM reservation WHERE apartment_id = ?", (apartment["id"],)
        )
        db.execute("DELETE FROM apartment WHERE id = ?", (apartment["id"],))
    global _ENTITY_ID
    if _ENTITY_ID is not None:
        db.execute("DELETE FROM legal_entity WHERE id = ?", (_ENTITY_ID,))
        _ENTITY_ID = None
    # The account itself stays: other tables hold a foreign key to it, and the
    # empty-install canary only counts guests, stays and properties.


def _seed(*, rejected: bool = False) -> tuple[TestClient, int, int]:
    """A stay whose forms are complete but whose document is unchecked."""
    db.init_db()
    _cleanup()
    now, today = db.utcnow(), date.today()
    existing = db.query_one(
        "SELECT id FROM user_account WHERE username = ?", (USERNAME,)
    )
    user_id = (
        existing["id"]
        if existing
        else auth.create_account(f"{USERNAME}@example.test", "Status Host", username=USERNAME)
    )
    entity_id = db.insert(
        "legal_entity",
        {"name": "Status s.r.o.", "owner_user_id": user_id, "created_at": now},
    )
    global _ENTITY_ID
    _ENTITY_ID = entity_id
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": user_id,
            "internal_name": "Status 1",
            "permalink_token": TOKEN,
            "automation_mode": "manual",
            "default_purpose": "10",
            "uby_mark": "DEMO1",
            "active": 1,
            "created_at": now,
        },
    )
    reservation_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "airbnb",
            "uid": "status-stay",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=3)).isoformat(),
            "status": "active",
            "expected_guests_override": 1,
            "created_at": now,
            "updated_at": now,
        },
    )
    db.insert(
        "guest",
        {
            "reservation_id": reservation_id,
            "surname": "NGUYEN",
            "first_name": "MINH",
            "birth_date": "01011990",
            "nationality": "VNM",
            "doc_number": "P9988771",
            "res_street": "Le Loi 5",
            "res_city": "Hanoi",
            "res_country": "VNM",
            "purpose": "10",
            "is_lead": 1,
            "entered_by": "guest",
            "signature_png": "imported",
            "signed_at": now,
            "passport_photo_at": now,
            "identity_verified_at": None,
            "submit_state": reporting.ERROR if rejected else reporting.PENDING,
            "created_at": now,
            "updated_at": now,
        },
    )
    client = TestClient(app)
    login_as(client, USERNAME, follow_redirects=False)
    client.cookies.set(host_i18n.LANG_COOKIE, "en")
    return client, apartment_id, reservation_id


@pytest.fixture
def host():
    client, apartment_id, reservation_id = _seed()
    try:
        yield client, apartment_id, reservation_id
    finally:
        _cleanup()


def _pills(page_text: str) -> list[tuple[str, str, str]]:
    return PILL.findall(page_text)


def _pill(page_text: str, label: str) -> tuple[str, str]:
    """The (tone, tip) of the pill that reads exactly ``label``."""
    found = [p for p in _pills(page_text) if p[2].strip() == label]
    assert found, f"no pill reading {label!r} on the page"
    return found[0][0], found[0][1]


def _pill_containing(page_text: str, fragment: str) -> tuple[str, str]:
    """The (tone, tip) of the first pill whose label contains ``fragment``."""
    found = [p for p in _pills(page_text) if fragment in p[2]]
    assert found, f"no pill containing {fragment!r} on the page"
    return found[0][0], found[0][1]


def test_the_unverified_stay_pill_reads_ready_to_report():
    assert (
        host_i18n.STRINGS["en"]["status.awaiting_verification"] == "Ready to report"
    )
    assert (
        host_i18n.STRINGS["cs"]["status.awaiting_verification"]
        == "Připraveno k hlášení"
    )


def test_the_unverified_pill_names_the_optional_check():
    assert (
        host_i18n.STRINGS["en"]["status.awaiting_verification_tip"]
        == "ID not checked (optional)"
    )
    assert (
        host_i18n.STRINGS["cs"]["status.awaiting_verification_tip"]
        == "Doklad nezkontrolován (volitelné)"
    )


def test_the_unverified_label_matches_the_ready_label_in_both_languages():
    """A complete stay reads the same whether or not the ID was checked."""
    for lang in ("en", "cs"):
        assert (
            host_i18n.STRINGS[lang]["status.awaiting_verification"]
            == host_i18n.STRINGS[lang]["status.ready"]
        )


def test_the_stay_pill_is_blue_on_the_work_queue(host):
    client, _, _ = host
    page = client.get("/")
    assert page.status_code == 200
    tone, tip = _pill(page.text, "Ready (you send)")
    assert tone == "blue", "amber reads as a problem the host has to solve"
    assert tip == host_i18n.translate("en", "status.ready_manual_tip")
    assert "ID not checked" not in page.text
    assert "Mark ID checked" not in page.text


def test_the_stay_pill_is_blue_on_the_stays_list(host):
    client, _, _ = host
    page = client.get("/reservations")
    assert page.status_code == 200
    tone, tip = _pill(page.text, "Ready (you send)")
    assert tone == "blue"
    assert tip == host_i18n.translate("en", "status.ready_manual_tip")


def test_the_stay_pill_is_blue_on_the_stay_detail(host):
    client, _, reservation_id = host
    page = client.get(f"/reservations/{reservation_id}")
    assert page.status_code == 200
    tone, tip = _pill(page.text, "Ready (you send)")
    assert tone == "blue"
    assert tip == host_i18n.translate("en", "status.ready_manual_tip")


def test_the_stay_pill_is_czech_for_a_czech_host(host):
    client, _, _ = host
    client.cookies.set(host_i18n.LANG_COOKIE, "cs")
    page = client.get("/")
    assert page.status_code == 200
    tone, tip = _pill(page.text, "Připraveno (ručně)")
    assert tone == "blue"
    assert tip == host_i18n.translate("cs", "status.ready_manual_tip")


def test_the_guest_card_does_not_ask_for_an_id_check(host):
    """Checking a document is the host's own job, so the card does not ask."""
    client, _, reservation_id = host
    page = client.get(f"/reservations/{reservation_id}")
    assert page.status_code == 200
    assert "ID not checked" not in page.text
    assert "Mark ID checked" not in page.text


def test_the_properties_list_setup_pill_is_amber_not_red(host):
    client, apartment_id, _ = host
    page = client.get("/apartments")
    assert page.status_code == 200
    rows = re.findall(r"<tr.*?</tr>", page.text, re.S)
    mine = [row for row in rows if f"/apartments/{apartment_id}" in row]
    assert mine, "the seeded property is not on the list"
    tone, _tip = _pill_containing(mine[0], "to fix")
    assert tone == "amber", "guests can still register, so it is a warning"


def test_the_guest_links_setup_pill_is_amber(host):
    client, _, _ = host
    page = client.get("/guest-links")
    assert page.status_code == 200
    tone, _tip = _pill_containing(page.text, "setup item")
    assert tone == "amber"


def test_the_automation_setup_banner_is_amber_and_not_a_red_pill(host):
    client, _, _ = host
    page = client.get("/automation")
    assert page.status_code == 200
    assert 'class="banner warning"' in page.text, "automation lost its setup warning"
    tones = {tone for tone, _tip, _label in _pills(page.text)}
    assert "red" not in tones, "setup incomplete is a warning, not a rejection"


def test_red_is_still_used_for_a_police_rejection():
    client, _, reservation_id = _seed(rejected=True)
    try:
        page = client.get(f"/reservations/{reservation_id}")
        assert page.status_code == 200
        tone, _tip = _pill(page.text, host_i18n.translate("en", "stay.detail.guests.rejected"))
        assert tone == "red"
    finally:
        _cleanup()


def test_a_duplicate_filing_is_green_because_nothing_is_left_to_do():
    """Code 150 means the register already holds every record: a success."""
    from app import templating

    html = templating.templates.env.from_string(
        "{% from '_components.html' import submission_pill %}"
        "{{ submission_pill('ok_duplicate') }}"
    ).render(t=lambda key, **kw: host_i18n.translate("en", key))
    tone, _tip, _label = PILL.search(html).groups()
    assert tone == "green"
