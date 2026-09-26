"""Regression tests for the UX/legal overhaul: stays sorting, one guest link, GDPR."""
from datetime import date, timedelta
from pathlib import Path
import re

from fastapi.testclient import TestClient

from app import auth, claim, db
from app import alerts
from app import demo
from app import housebook
from app import i18n
from app.main import app
from app.routes import guest as guest_routes
from tests.conftest import complete_guest_claim

TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"
TOKEN = "overhaultoken"
PASSWORD = "Overhaul-Test-Password-123"
ADMIN_USERNAME = "overhaul-admin"


def _ensure_admin() -> int:
    db.init_db()
    account = db.query_one(
        "SELECT * FROM user_account WHERE username = ?", (ADMIN_USERNAME,)
    )
    if not account:
        return auth.create_account(
            ADMIN_USERNAME,
            PASSWORD,
            "Overhaul admin",
            role="admin",
            must_change_password=False,
        )
    return account["id"]


def _browser() -> TestClient:
    """Sign in as an English host; the assertions below read the English UI."""
    _ensure_admin()
    client = TestClient(app)
    response = client.post(
        "/login?lang=en",
        data={"username": ADMIN_USERNAME, "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client


def _cleanup():
    apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
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
        ("Overhaul Test s.r.o.",),
    )


def _seed_stays():
    db.init_db()
    _cleanup()
    owner_id = _ensure_admin()
    now = db.utcnow()
    today = claim.prague_today()
    entity_id = db.insert(
        "legal_entity",
        {
            "name": "Overhaul Test s.r.o.",
            "seat": "Praha 2",
            "ico": "87654321",
            "contact_email": "privacy@overhaul.test",
            "owner_user_id": owner_id,
            "created_at": now,
        },
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": owner_id,
            "internal_name": "Overhaul flat",
            "city_en": "Prague",
            "uby_name": "Overhaul Studio",
            "permalink_token": TOKEN,
            "permalink_window_days": 30,
            "default_purpose": "10",
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    stays = []
    # All future-only so the "Past" chip never picks them up (today counts as past).
    for offset in (10, 5, 15):
        stays.append(
            db.insert(
                "reservation",
                {
                    "apartment_id": apartment_id,
                    "source": "airbnb",
                    "uid": f"overhaul-{offset}",
                    "date_from": (today + timedelta(days=offset)).isoformat(),
                    "date_to": (today + timedelta(days=offset + 2)).isoformat(),
                    "summary": "Airbnb reservation",
                    "status": "active",
                    "created_at": now,
                    "updated_at": now,
                },
            )
        )
    past = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "booking",
            "uid": "overhaul-past",
            "date_from": (today - timedelta(days=30)).isoformat(),
            "date_to": (today - timedelta(days=27)).isoformat(),
            "summary": "Booking.com reservation",
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    return apartment_id, stays, past


def _stay_sources(page_text: str):
    """What the Source column of a stays table actually renders, one per row."""
    return [
        value.strip()
        for value in re.findall(r'data-label="Source">\s*([^<]+)', page_text)
    ]


def _seed_receipt_for(stay_id: int) -> int:
    """A finished submission with a stored receipt, attached to a stay guest."""
    now = db.utcnow()
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (stay_id,))
    guest_id = db.insert(
        "guest",
        {
            "reservation_id": stay_id,
            "surname": "Smith",
            "first_name": "John",
            "nationality": "GBR",
            "purpose": "10",
            "is_lead": 1,
            "entered_by": "host",
            "created_at": now,
            "updated_at": now,
        },
    )
    submission_id = db.insert(
        "submission",
        {
            "apartment_id": reservation["apartment_id"],
            "created_at": now,
            "finished_at": now,
            "mode": "manual",
            "state": "ok",
            "guest_ids": "[]",
            "pseudo_stamp": "20260101120000-abc",
            "receipt_pdf": "JVBERi0xLjQ=",
        },
    )
    db.update("guest", guest_id, {"submission_id": submission_id})
    return submission_id


def _stay_dates(html: str) -> list[str]:
    return re.findall(
        r'class="row-primary-link"[^>]*>\s*(\d{2}\.\d{2}\.\d{4}) &ndash;',
        html,
    )


def test_reservations_sorted_earliest_first():
    apartment_id, _stays, _past = _seed_stays()
    try:
        page = _browser().get(f"/reservations?range=all&apartment={apartment_id}")
        assert page.status_code == 200
        dates = _stay_dates(page.text)
        assert len(dates) == 4
        parsed = [
            (int(year), int(month), int(day))
            for day, month, year in (d.split(".") for d in dates)
        ]
        assert parsed == sorted(parsed)
    finally:
        _cleanup()


def test_reservations_past_filter_hides_future():
    apartment_id, _stays, _past = _seed_stays()
    try:
        page = _browser().get(f"/reservations?range=past&apartment={apartment_id}")
        assert page.status_code == 200
        sources = _stay_sources(page.text)
        assert "Booking.com" in sources
        assert "Airbnb" not in sources
    finally:
        _cleanup()


def test_reservations_bad_query_params_do_not_500():
    _seed_stays()
    try:
        page = _browser().get(
            "/reservations?apartment=not-a-number&status=bogus&from=nonsense&to=also-bad"
        )
        assert page.status_code == 200
    finally:
        _cleanup()


def test_reservations_paginate_and_preserve_filters():
    apartment_id, _stays, _past = _seed_stays()
    try:
        now = db.utcnow()
        today = date.today()
        for offset in range(40, 88):
            db.insert(
                "reservation",
                {
                    "apartment_id": apartment_id,
                    "source": "manual",
                    "uid": f"page-{offset}",
                    "date_from": (today + timedelta(days=offset)).isoformat(),
                    "date_to": (today + timedelta(days=offset + 1)).isoformat(),
                    "summary": f"Page stay {offset}",
                    "status": "active",
                    "created_at": now,
                    "updated_at": now,
                },
            )

        first = _browser().get(f"/reservations?range=all&apartment={apartment_id}")
        assert "Showing 1–50 of 52 stays." in " ".join(first.text.split())
        assert f"/reservations?range=all&amp;apartment={apartment_id}&amp;page=2" in first.text

        second = _browser().get(
            f"/reservations?range=all&apartment={apartment_id}&page=2"
        )
        assert "Showing 51–52 of 52 stays." in " ".join(second.text.split())
        assert "Page 2 of 2" in second.text
    finally:
        _cleanup()


def test_manual_dates_override_the_selected_preset_without_javascript():
    apartment_id, _stays, past = _seed_stays()
    try:
        old_from = (date.today() - timedelta(days=31)).isoformat()
        old_to = (date.today() - timedelta(days=26)).isoformat()
        page = _browser().get(
            f"/reservations?range=upcoming&apartment={apartment_id}"
            f"&from={old_from}&to={old_to}&range=custom"
        )
        assert page.status_code == 200
        assert f'data-href="/reservations/{past}' in page.text
        assert "Airbnb" not in _stay_sources(page.text)
    finally:
        _cleanup()


def test_alert_dismiss_is_instant_but_a_new_failure_realerts():
    db.init_db()
    key = "overhaul-test-alert"
    db.execute("DELETE FROM alert WHERE dedupe_key = ?", (key,))
    try:
        owner_id = _ensure_admin()
        alerts.raise_alert(
            "warning", "test", "A test alert", dedupe_key=key, owner_user_id=owner_id
        )
        alert = db.query_one("SELECT id FROM alert WHERE dedupe_key = ?", (key,))
        response = _browser().post(
            f"/alerts/{alert['id']}/dismiss",
            headers={"X-Requested-With": "fetch"},
            follow_redirects=False,
        )
        assert response.status_code == 204
        row = db.query_one("SELECT resolved_at, user_dismissed FROM alert WHERE id = ?", (alert["id"],))
        assert row["resolved_at"]
        assert row["user_dismissed"] == 1
        alerts.raise_alert(
            "warning", "test", "A later failure", dedupe_key=key, owner_user_id=owner_id
        )
        reopened = db.query_one(
            "SELECT * FROM alert WHERE dedupe_key = ? AND resolved_at IS NULL", (key,)
        )
        assert reopened
        assert reopened["id"] != alert["id"]
    finally:
        db.execute("DELETE FROM alert WHERE dedupe_key = ?", (key,))


def test_reservation_rows_are_full_click_targets():
    apartment_id, stays, _past = _seed_stays()
    try:
        page = _browser().get(f"/reservations?range=all&apartment={apartment_id}")
        assert page.status_code == 200
        assert f'data-href="/reservations/{stays[0]}?return_to=' in page.text
        assert 'class="clickable-row"' in page.text
        assert ">Open</a>" not in page.text
    finally:
        _cleanup()


def test_reservation_detail_shows_direct_guest_link():
    apartment_id, stays, _past = _seed_stays()
    try:
        page = _browser().get(f"/reservations/{stays[0]}")
        assert page.status_code == 200
        assert f"/l/{TOKEN}/{stays[0]}" in page.text
        assert "Copy guest link for this stay" in page.text
        assert "Next step" in page.text
        assert "Edit stay details" in page.text
        assert 'class="panel stay-command-panel"' in page.text
        assert page.text.count('name="expected_guests_override"') == 1
        assert 'href="/guest-links"' in page.text
    finally:
        _cleanup()


COPY_LINK_PRIMARY = 'class="btn primary" type="button" data-copy="stay-link"'


def test_a_cancelled_stay_says_so_at_the_top_and_stops_asking_for_the_link():
    """A cancelled stay looked exactly like a live one.

    The only trace was the pre-opened Stay-settings panel at the bottom of the
    page, so a host could chase a guest who had already cancelled.
    """
    _apartment_id, stays, _past = _seed_stays()
    try:
        db.update("reservation", stays[0], {"status": "cancelled"})
        page = _browser().get(f"/reservations/{stays[0]}")
        assert page.status_code == 200
        assert "This stay is cancelled" in page.text
        assert COPY_LINK_PRIMARY not in page.text
        assert "Reporting deadline" not in page.text
        # The rest of the page is still there to work with.
        assert "Guest forms" in page.text
    finally:
        _cleanup()


def test_an_ignored_stay_says_what_ignored_means():
    _apartment_id, stays, _past = _seed_stays()
    try:
        db.update("reservation", stays[0], {"status": "ignored"})
        page = _browser().get(f"/reservations/{stays[0]}")
        assert "Marked as not a guest stay" in page.text
        assert COPY_LINK_PRIMARY not in page.text
    finally:
        _cleanup()


def test_an_archived_stay_says_so():
    _apartment_id, stays, _past = _seed_stays()
    try:
        db.update("reservation", stays[0], {"archived_at": db.utcnow()})
        page = _browser().get(f"/reservations/{stays[0]}")
        assert "Archived — hidden from your daily work." in page.text
        assert COPY_LINK_PRIMARY not in page.text
        assert "Reporting deadline" not in page.text
    finally:
        _cleanup()


def test_a_live_stay_keeps_its_deadline_and_copy_link():
    _apartment_id, stays, _past = _seed_stays()
    try:
        page = _browser().get(f"/reservations/{stays[0]}")
        assert "This stay is cancelled" not in page.text
        assert "Marked as not a guest stay" not in page.text
        assert "Archived — hidden from your daily work." not in page.text
        assert COPY_LINK_PRIMARY in page.text
        assert "Reporting deadline" in page.text
        assert 'class="stay-metrics detail-hero inactive"' not in page.text
    finally:
        _cleanup()


def test_the_stay_page_reads_as_one_ordered_grammar():
    """The panels join named groups instead of being appended bare.

    UX_AUDIT C-16 [UX-81]: Now -> Guests -> Payments -> Police reporting ->
    Stay settings.
    """
    _apartment_id, stays, _past = _seed_stays()
    try:
        page = _browser().get(f"/reservations/{stays[0]}")
        assert page.status_code == 200
        body = page.text
        positions = [body.index(marker) for marker in ('id="now"', 'id="guests"', 'id="stay-quick-edit"')]
        assert positions == sorted(positions)
        # The facts strip lives inside Now, not in a second card below it.
        assert 'class="panel stay-command-panel" id="now"' in body
        assert 'class="stay-metrics detail-hero' in body
        assert 'class="panel tight detail-hero' not in body
        # The guest-assignment line moved into the Guests group.
        assert 'id="stay-claim"' not in body
        assert body.index('id="guests"') < body.index('class="stay-claim-line"')
    finally:
        _cleanup()


def test_the_payments_group_renders_with_a_panel_between_guests_and_reports():
    """#money carries the stay-fee and invoice panels (PLAN_POPLATEK, PLAN_GUEST_INVOICE).

    Both plans insert their panel here, between the guest cards and the reports
    table. The heading is guarded, so it arrives with the first child panel.
    """
    _apartment_id, stays, _past = _seed_stays()
    try:
        body = _browser().get(f"/reservations/{stays[0]}").text
        assert 'id="money"' in body
        # The invoice panel always offers "Issue invoice", so the group ships.
        assert 'id="invoice"' in body
        source = (TEMPLATES / "reservation_detail.html").read_text(encoding="utf-8")
        assert "{% if money_panels %}" in source
        assert source.index('id="guests"') < source.index('id="money"')
        assert source.index('id="money"') < source.index('id="reports"')
    finally:
        _cleanup()


def test_stay_settings_and_the_quick_edit_share_one_panel():
    """Editing the stay used to be split across the top and the bottom."""
    _apartment_id, stays, _past = _seed_stays()
    try:
        body = _browser().get(f"/reservations/{stays[0]}").text
        assert 'class="panel stay-settings" id="stay-quick-edit"' in body
        panel = body.split('id="stay-quick-edit"', 1)[1].split("</details>", 1)[0]
        assert "data-inline-edit" in panel
        assert 'name="expected_guests_override"' in panel
        assert 'name="guest_email"' in panel
        assert 'name="host_note"' in panel
    finally:
        _cleanup()


def test_the_receipt_download_moves_into_the_report_row_menu():
    """One coral button per row was against DESIGN.md's row-action rule."""
    _apartment_id, stays, _past = _seed_stays()
    try:
        submission_id = _seed_receipt_for(stays[0])
        body = _browser().get(f"/reservations/{stays[0]}").text
        assert '<section id="reports">' in body
        assert f'class="row-menu-item" href="/submissions/{submission_id}/receipt.pdf"' in body
        assert ">Receipt (Doručenka)</a>" in body
        assert f'class="btn small primary" href="/submissions/{submission_id}/receipt.pdf"' not in body
    finally:
        _cleanup()


def test_stay_settings_preserve_expected_guests_edited_above():
    _apartment_id, stays, _past = _seed_stays()
    try:
        db.update("reservation", stays[0], {"expected_guests_override": 4})
        response = _browser().post(
            f"/reservations/{stays[0]}",
            data={"guest_email": "guest@example.com", "host_note": "Late arrival", "status": "active"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (stays[0],))
        assert reservation["expected_guests_override"] == 4
    finally:
        _cleanup()


def test_filtered_stays_return_path_and_guest_links_workspace():
    apartment_id, stays, _past = _seed_stays()
    try:
        browser = _browser()
        listing = browser.get(f"/reservations?range=all&apartment={apartment_id}")
        assert listing.status_code == 200
        assert "Setup readiness" not in listing.text
        assert "%2Freservations%3Frange%3Dall" in listing.text

        detail = browser.get(
            f"/reservations/{stays[0]}?return_to=%2Freservations%3Frange%3Dall%26apartment%3D{apartment_id}"
        )
        assert detail.status_code == 200
        assert "Back to stays" in detail.text
        assert f"/reservations?range=all&amp;apartment={apartment_id}" in detail.text

        links = browser.get("/guest-links")
        assert links.status_code == 200
        assert f"/l/{TOKEN}" in links.text
        assert f"/l/{TOKEN}/{stays[0]}" not in links.text
        assert "Suggested portal message" in links.text
    finally:
        _cleanup()


def test_host_shell_is_workflow_grouped():
    _seed_stays()
    try:
        page = _browser().get("/")
        assert page.status_code == 200
        assert "Operations" in page.text
        assert "Records" in page.text
        assert "Setup" in page.text
        assert 'id="app-sidebar"' in page.text
        assert "Overview" in page.text
    finally:
        _cleanup()


def test_demo_reset_removes_only_named_mock_data():
    apartment_id, _stays, _past = _seed_stays()
    demo_entity_id = db.insert(
        "legal_entity",
        {"name": demo.DEMO_ENTITY, "created_at": db.utcnow()},
    )
    demo_apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": demo_entity_id,
            "internal_name": "Vinohrady Studio (demo)",
            "permalink_token": "demo-reset-token",
            "active": 1,
            "created_at": db.utcnow(),
        },
    )
    try:
        assert demo.clear()
        assert not db.query_one("SELECT 1 AS x FROM apartment WHERE id = ?", (demo_apartment_id,))
        assert db.query_one("SELECT 1 AS x FROM apartment WHERE id = ?", (apartment_id,))
    finally:
        db.execute("DELETE FROM apartment WHERE id = ?", (demo_apartment_id,))
        db.execute("DELETE FROM legal_entity WHERE id = ?", (demo_entity_id,))
        _cleanup()


def test_guest_pick_explains_law_without_portal_branding():
    _seed_stays()
    try:
        page = TestClient(app).get(f"/l/{TOKEN}?lang=en")
        assert page.status_code == 200
        assert "Czech law" in page.text
        assert "Why you are filling this in" in page.text
        assert "What happens with what you enter" in page.text
        assert '<details class="g-details">' not in page.text
        assert i18n.STRINGS["en"]["stay_not_started"] in page.text
        assert "0 of 2 people completed" not in page.text
        assert "Booking.com" not in page.text
        assert "Airbnb" not in page.text
        # The guest sees the host's own name for the flat, not the police registration.
        assert "Overhaul flat" in page.text
        assert "Overhaul Studio" not in page.text
    finally:
        _cleanup()


def test_guest_assigned_screen_does_not_leak_police_name():
    _apartment_id, stays, _past = _seed_stays()
    try:
        browser = TestClient(app)
        complete_guest_claim(browser, TOKEN, stays[0], party_size=1)
        # A fresh browser without the claim cookie sees the "already assigned" screen.
        stranger = TestClient(app)
        page = stranger.get(f"/l/{TOKEN}/{stays[0]}", follow_redirects=True)
        assert page.status_code == 200
        assert "already assigned" in page.text.lower() or "přiřazena" in page.text.lower()
        assert "Overhaul flat" in page.text
        assert "Overhaul Studio" not in page.text
    finally:
        _cleanup()


def test_guest_privacy_notice_names_controller():
    _seed_stays()
    try:
        page = TestClient(app).get(f"/l/{TOKEN}/privacy?lang=en")
        assert page.status_code == 200
        assert "Overhaul Test s.r.o." in page.text
        assert "privacy@overhaul.test" in page.text
        assert "6(1)(c)" in page.text
    finally:
        _cleanup()


def test_property_can_use_separate_pm_and_data_controller():
    apartment_id, _stays, _past = _seed_stays()
    controller_id = db.insert(
        "legal_entity",
        {
            "name": "Separate Controller a.s.",
            "seat": "Praha 1",
            "ico": "11223344",
            "contact_email": "privacy@controller.test",
            "owner_user_id": _ensure_admin(),
            "created_at": db.utcnow(),
        },
    )
    try:
        saved = _browser().post(
            f"/apartments/{apartment_id}",
            data={
                "internal_name": "Overhaul flat",
                "legal_entity_id": str(
                    db.query_one(
                        "SELECT legal_entity_id FROM apartment WHERE id = ?",
                        (apartment_id,),
                    )["legal_entity_id"]
                ),
                "data_controller_entity_id": str(controller_id),
                "active": "1",
            },
            follow_redirects=False,
        )
        assert saved.status_code == 303
        assert db.query_one(
            "SELECT data_controller_entity_id FROM apartment WHERE id = ?",
            (apartment_id,),
        )["data_controller_entity_id"] == controller_id
        privacy = TestClient(app).get(f"/l/{TOKEN}/privacy?lang=en")
        assert "Separate Controller a.s." in privacy.text
        assert "privacy@controller.test" in privacy.text
        assert "Overhaul Test s.r.o." in privacy.text
        assert "Your data controller" in privacy.text
        assert "Questions about your stay" in privacy.text
        assert privacy.text.index("Separate Controller a.s.") < privacy.text.index(
            "Overhaul Test s.r.o."
        )
        assert "different name for the stay contact below does not change" in privacy.text

        picker = TestClient(app).get(f"/l/{TOKEN}?lang=en")
        assert "privacy@overhaul.test" in picker.text
        assert "privacy@controller.test" not in picker.text

        settings = _browser().get(f"/apartments/{apartment_id}")
        assert 'id="controller_is_operator"' in settings.text
        assert re.search(
            rf'<option value="{controller_id}"\s+selected', settings.text
        )
    finally:
        db.update(
            "apartment",
            apartment_id,
            {"data_controller_entity_id": None},
        )
        db.execute("DELETE FROM legal_entity WHERE id = ?", (controller_id,))
        _cleanup()


def test_guest_unavailable_states_are_distinct():
    _seed_stays()
    try:
        browser = TestClient(app)
        browser.cookies.set(guest_routes.LANG_COOKIE, "en")
        bad_stay = browser.get(f"/l/{TOKEN}/999999")
        assert bad_stay.status_code == 404
        assert "no longer open" in bad_stay.text

        bad_token = browser.get("/l/invalidtoken123")
        assert bad_token.status_code == 404
        assert "guest link is not valid" in bad_token.text.lower()
    finally:
        _cleanup()


def test_retention_purge_deletes_old_guests():
    db.init_db()
    _cleanup()
    now = db.utcnow()
    old_end = (date.today() - timedelta(days=365 * 6 + 30)).isoformat()
    entity_id = db.insert(
        "legal_entity",
        {"name": "Overhaul Test s.r.o.", "created_at": now},
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "Old stay flat",
            "permalink_token": TOKEN,
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    reservation_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            "uid": "old-one",
            "date_from": old_end,
            "date_to": old_end,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    guest_id = db.insert(
        "guest",
        {
            "reservation_id": reservation_id,
            "surname": "ANCIENT",
            "first_name": "GUEST",
            "entered_by": "host",
            "submit_state": "sent",
            "created_at": now,
            "updated_at": now,
        },
    )
    try:
        assert guest_id in housebook.expired_guest_ids()
        deleted = housebook.purge_expired()
        assert deleted == 1
        assert not db.query_one("SELECT 1 AS x FROM guest WHERE id = ?", (guest_id,))
    finally:
        _cleanup()
