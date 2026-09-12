"""Regression tests for the UX/legal overhaul: stays sorting, one guest link, GDPR."""
from datetime import date, timedelta
import re

from fastapi.testclient import TestClient

from app import auth, db
from app import alerts
from app import demo
from app import housebook
from app.main import app

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
    _ensure_admin()
    client = TestClient(app)
    response = client.post(
        "/login",
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
    today = date.today()
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
        parsed = [tuple(int(x) for x in d.split(".")) for d in dates]
        assert parsed == sorted(parsed)
    finally:
        _cleanup()


def test_reservations_past_filter_hides_future():
    apartment_id, _stays, _past = _seed_stays()
    try:
        page = _browser().get(f"/reservations?range=past&apartment={apartment_id}")
        assert page.status_code == 200
        assert "Booking.com reservation" in page.text
        assert "Airbnb reservation" not in page.text
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
        assert "Airbnb reservation" not in page.text
    finally:
        _cleanup()


def test_alert_dismiss_fetch_is_instant_and_permanent():
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
        assert 'href="/guest-links"' in page.text
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
        page = TestClient(app).get(f"/l/{TOKEN}")
        assert page.status_code == 200
        assert "Czech law" in page.text
        assert "Why you are filling this in" in page.text
        assert "What happens with what you enter" in page.text
        assert '<details class="g-details">' not in page.text
        assert "Select these dates" in page.text
        assert "0 of 2 people completed" not in page.text
        assert "Booking.com" not in page.text
        assert "Airbnb" not in page.text
        assert "Overhaul Studio" in page.text
    finally:
        _cleanup()


def test_guest_privacy_notice_names_controller():
    _seed_stays()
    try:
        page = TestClient(app).get(f"/l/{TOKEN}/privacy")
        assert page.status_code == 200
        assert "Overhaul Test s.r.o." in page.text
        assert "privacy@overhaul.test" in page.text
        assert "6(1)(c)" in page.text
    finally:
        _cleanup()


def test_guest_unavailable_states_are_distinct():
    _seed_stays()
    try:
        browser = TestClient(app)
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
