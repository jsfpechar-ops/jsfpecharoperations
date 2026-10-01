"""The Overview work queue says what happened, how much is left, and when.

C-22 in the UX audit. The completed bucket already knew a stay was finished,
but every row in it fell through to "Open the stay and check what is missing."
The "Needs action now" heading never said how many stays sat under it, and the
column labelled "Deadline" mostly shows an arrival time.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import auth, db, host_i18n, reporting
from app.main import app

TOKEN = "dashboardqueuecopytoken"
PASSWORD = "Dashboard-Queue-Password-123"
USERNAME = "dashboard-queue-admin"

REPORTED_KEY = "action.reported"
NOT_REQUIRED_KEY = "action.not_required"


def _ensure_admin() -> int:
    db.init_db()
    account = db.query_one(
        "SELECT * FROM user_account WHERE username = ?", (USERNAME,)
    )
    if not account:
        return auth.create_account(
            USERNAME,
            PASSWORD,
            "Dashboard queue admin",
            role="admin",
            must_change_password=False,
        )
    return account["id"]


def _cleanup():
    apartment = db.query_one(
        "SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,)
    )
    if not apartment:
        return
    db.execute(
        "DELETE FROM guest WHERE reservation_id IN "
        "(SELECT id FROM reservation WHERE apartment_id = ?)",
        (apartment["id"],),
    )
    db.execute("DELETE FROM submission WHERE apartment_id = ?", (apartment["id"],))
    db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment["id"],))
    db.execute("DELETE FROM apartment WHERE id = ?", (apartment["id"],))
    db.execute(
        "DELETE FROM legal_entity WHERE name = ? AND id NOT IN "
        "(SELECT legal_entity_id FROM apartment WHERE legal_entity_id IS NOT NULL)",
        ("Dashboard Queue s.r.o.",),
    )


def _stay(apartment_id: int, uid: str, nationality: str, submit_state: str, days: int) -> int:
    """One stay with exactly one complete guest, so its status is unambiguous."""
    now = db.utcnow()
    today = date.today()
    reservation_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "airbnb",
            "uid": uid,
            "date_from": (today + timedelta(days=days)).isoformat(),
            "date_to": (today + timedelta(days=days + 3)).isoformat(),
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
            "surname": "TESTER",
            "first_name": "TINA",
            "birth_date": "01011990",
            "nationality": nationality,
            "doc_number": "P1234567",
            "res_street": "Street 1",
            "res_city": "London",
            "res_country": nationality,
            "purpose": "10",
            "is_lead": 1,
            "entered_by": "host",
            "signature_png": "imported",
            "signed_at": now,
            "identity_verified_at": now,
            "submit_state": submit_state,
            "created_at": now,
            "updated_at": now,
        },
    )
    return reservation_id


def _seed() -> dict:
    """Three stays: one reported, one outside the duty, one ready to send."""
    db.init_db()
    _cleanup()
    owner_id = _ensure_admin()
    now = db.utcnow()
    entity_id = db.insert(
        "legal_entity",
        {
            "name": "Dashboard Queue s.r.o.",
            "seat": "Praha 2",
            "ico": "11223344",
            "owner_user_id": owner_id,
            "created_at": now,
        },
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": owner_id,
            "internal_name": "Queue flat",
            "city_en": "Prague",
            "permalink_token": TOKEN,
            "default_purpose": "10",
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    ids = {
        "reported": _stay(apartment_id, "queue-reported", "GBR", reporting.SENT, 6),
        "not_required": _stay(
            apartment_id, "queue-not-required", "CZE", reporting.PENDING, 7
        ),
        "ready": _stay(apartment_id, "queue-ready", "GBR", reporting.PENDING, 8),
    }
    return ids


def _browser(lang: str) -> TestClient:
    _ensure_admin()
    client = TestClient(app)
    response = client.post(
        "/login",
        data={"username": USERNAME, "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303
    client.cookies.set(host_i18n.LANG_COOKIE, lang)
    return client


@pytest.fixture
def seeded():
    """Seed the three stays and leave the shared database as it was found.

    The suite shares one database, and modules that assert on an empty install
    run after this one, so the rows have to go.
    """
    ids = _seed()
    try:
        yield ids
    finally:
        _cleanup()


def _page(lang: str) -> str:
    page = _browser(lang).get("/")
    assert page.status_code == 200
    return page.text


def _next_action_for(page_text: str, stay_id: int) -> str:
    """The next-action line of one queue row, keyed by its own detail link."""
    row = re.search(
        rf'<article data-stay-id="{stay_id}"[^>]*>(.*?)</article>', page_text, re.S,
    )
    assert row, f"stay {stay_id} has no row on the work queue"
    action = re.search(r'<div class="host-task-state next-action">(.*?)</div>', row.group(1), re.S)
    assert action, f"stay {stay_id} has no next-action line"
    return " ".join(action.group(1).split())


def _needs_action_section(page_text: str) -> str:
    section = re.search(r'<section id="needs-action">(.*?)</section>', page_text, re.S)
    assert section, "the needs-action section is missing"
    return section.group(1)


def _needs_action_heading(page_text: str) -> str:
    heading = re.search(r"<h2>(.*?)</h2>", _needs_action_section(page_text), re.S)
    assert heading, "the needs-action heading is missing"
    return " ".join(heading.group(1).split())


def _queue_table_labels(page_text: str) -> list:
    header = re.search(r"<thead><tr>(.*?)</tr></thead>", page_text, re.S)
    assert header, "no queue table header on the page"
    cells = re.findall(r"<th[^>]*>(.*?)</th>", header.group(1), re.S)
    return [" ".join(cell.split()) for cell in cells]


# --- the copy itself ------------------------------------------------------


def test_the_new_next_actions_ship_the_audited_wording():
    assert host_i18n.STRINGS["en"][REPORTED_KEY] == "All guests reported. Nothing to do."
    assert host_i18n.STRINGS["en"][NOT_REQUIRED_KEY] == (
        "Only Czech guests — nothing to report."
    )
    assert host_i18n.STRINGS["cs"][REPORTED_KEY] == (
        "Všichni hosté jsou nahlášení. Není třeba nic dělat."
    )
    assert host_i18n.STRINGS["cs"][NOT_REQUIRED_KEY] == (
        "Jen čeští hosté — policii se nic nehlásí."
    )


def test_the_completed_heading_is_renamed_in_both_languages():
    assert host_i18n.STRINGS["en"]["dashboard.section.completed"] == (
        "Done — nothing to do"
    )
    assert host_i18n.STRINGS["cs"]["dashboard.section.completed"] == (
        "Hotovo — není třeba nic dělat"
    )


def test_the_when_column_is_renamed_in_both_languages():
    assert host_i18n.STRINGS["en"]["dashboard.table.deadline"] == "When"
    assert host_i18n.STRINGS["cs"]["dashboard.table.deadline"] == "Kdy"


def test_the_action_heading_carries_a_count_in_both_languages():
    for lang, expected in (("en", "Needs action now (3)"), ("cs", "Vyžaduje akci (3)")):
        raw = host_i18n.STRINGS[lang]["dashboard.section.needs_action"]
        assert "%(count)s" in raw, f"the {lang} heading has no count placeholder"
        resolved = host_i18n.translate(
            lang, "dashboard.section.needs_action", count=3
        )
        assert resolved == expected


def test_the_new_action_keys_are_at_parity():
    english = {k for k in host_i18n.STRINGS["en"] if k.startswith("action.")}
    czech = {k for k in host_i18n.STRINGS["cs"] if k.startswith("action.")}
    assert english == czech
    for key in (REPORTED_KEY, NOT_REQUIRED_KEY):
        assert key in host_i18n.STRINGS["en"]
        assert key in host_i18n.STRINGS["cs"]


# --- what the rows render -------------------------------------------------


def test_a_reported_stay_says_nothing_is_left_to_do(seeded):
    page = _page("en")
    assert _next_action_for(page, seeded["reported"]) == (
        host_i18n.translate("en", REPORTED_KEY)
    )


def test_a_stay_of_only_czech_guests_says_nothing_goes_to_the_police(seeded):
    page = _page("en")
    assert _next_action_for(page, seeded["not_required"]) == (
        host_i18n.translate("en", NOT_REQUIRED_KEY)
    )


def test_a_finished_stay_never_falls_back_to_check_what_is_missing(seeded):
    page = _page("en")
    fallback = host_i18n.translate("en", "action.check_missing")
    for key in ("reported", "not_required"):
        assert _next_action_for(page, seeded[key]) != fallback


def test_a_czech_host_reads_the_new_next_actions_in_czech(seeded):
    page = _page("cs")
    english = host_i18n.translate("en", REPORTED_KEY)
    for stay, key in (
        ("reported", REPORTED_KEY),
        ("not_required", NOT_REQUIRED_KEY),
    ):
        line = _next_action_for(page, seeded[stay])
        assert line == host_i18n.translate("cs", key)
        assert line != english


# --- what the headings and column labels render ---------------------------


def test_the_action_heading_counts_the_rows_beneath_it(seeded):
    page = _page("en")
    rows = len(re.findall(r'<article data-stay-id=', _needs_action_section(page)))
    assert rows >= 1, "the seeded ready stay should need action"
    assert _needs_action_heading(page) == f"Needs action now ({rows})"


def test_the_action_heading_never_leaks_its_placeholder(seeded):
    for lang in ("en", "cs"):
        heading = _needs_action_heading(_page(lang))
        assert "%(count)s" not in heading
        assert re.search(r"\(\d+\)$", heading), heading


def test_the_completed_section_is_labelled_done_nothing_to_do(seeded):
    page = _page("en")
    assert host_i18n.translate("en", "dashboard.section.completed") in page
    assert "Recently completed" not in page


def test_task_cards_keep_dates_and_deadline_context(seeded):
    page = _page("en")
    assert 'class="host-task-context"' in page
    assert 'class="deadline ' in page
    assert 'data-stay-id=' in page


def test_task_cards_translate_time_context(seeded):
    page = _page("cs")
    assert 'class="host-task-context"' in page
    assert 'arrives in' not in page
