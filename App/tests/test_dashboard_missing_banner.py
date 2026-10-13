"""The Overview names what blocks reporting before the host opens each property."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import auth, db, host_i18n
from app.main import app
from tests.conftest import login_as

USERNAME = "dashboard-missing-banner-host"

REPORT_FIELD_KEYS = (
    "idub",
    "mark",
    "facility_name",
    "house_no",
    "zip",
    "obec",
    "ws_user",
    "password",
)

COMPLETE_VALUES = {
    "uby_idub": "123456789012",
    "uby_mark": "AAKLI",
    "uby_name": "Banner Flat",
    "uby_ws_user": "uby-ws1a2b3c",
    "uby_ws_password_enc": db.encrypt_secret("ws-secret"),
    "addr_obec": "Praha",
    "addr_house_no": "12",
    "addr_zip": "12000",
}


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
    return db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))["id"]


def _insert_apartment(internal_name: str, **overrides) -> int:
    entity_id = db.insert(
        "legal_entity",
        {
            "name": f"{internal_name} s.r.o.",
            "seat": "Praha",
            "ico": "12345678",
            "contact_email": "host@banner.test",
            "owner_user_id": _owner_id(),
            "created_at": db.utcnow(),
        },
    )
    payload = {
        "legal_entity_id": entity_id,
        "owner_user_id": _owner_id(),
        "internal_name": internal_name,
        "addr_obec": "Praha",
        "addr_house_no": "12",
        "addr_zip": "12000",
        "permalink_token": f"banner{internal_name.lower().replace(' ', '')}",
        "permalink_pin": "123456",
        "automation_mode": "manual",
        "submit_after_hours": 24,
        "active": 1,
        "created_at": db.utcnow(),
    }
    payload.update(overrides)
    return db.insert("apartment", payload)


def _labels(lang: str) -> list[str]:
    return [
        host_i18n.STRINGS[lang][f"apartment.form.readiness.item.{key}"]
        for key in REPORT_FIELD_KEYS
    ]


def _banner_block(text: str) -> str:
    start = text.index('class="notification-bubble warning"')
    return text[start : text.index("</article>", start)]


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    auth.create_account(f"{USERNAME}@example.test", "Banner Host", username=USERNAME)
    client = TestClient(app)
    response = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    client.post("/onboarding/dismiss", data={"return_to": "/"}, follow_redirects=False)
    try:
        yield client
    finally:
        _cleanup()


def test_the_banner_lists_missing_report_fields_in_readiness_order(host):
    apartment_id = _insert_apartment("Order Flat")

    page = host.get("/?lang=en")

    banner = _banner_block(page.text)
    labels = _labels("en")
    present = [label for label in labels if label in banner]
    assert present == [
        label
        for label in labels
        if label
        in {
            "IDUB",
            "Facility abbreviation",
            "Facility name",
            "Web-service login",
            "Password",
        }
    ]
    assert present.index("IDUB") < present.index("Facility abbreviation") < present.index("Password")
    assert f'href="/apartments/{apartment_id}?view=settings&amp;section=reporting#ubyport"' in banner


def test_the_banner_is_absent_when_reporting_is_ready(host):
    apartment_id = _insert_apartment("Ready Flat", **COMPLETE_VALUES)
    db.update("apartment", apartment_id, COMPLETE_VALUES)

    page = host.get("/?lang=en")

    assert 'class="notification-bubble warning"' not in page.text


def test_the_sixth_incomplete_property_collapses_into_and_more(host):
    names = [f"Banner Flat {index}" for index in range(1, 7)]
    for name in names:
        _insert_apartment(name)

    page = host.get("/?lang=en")

    banner = _banner_block(page.text)
    assert banner.count('class="dashboard-missing-line"') == 5
    assert "and 1 more" in page.text
    assert 'href="/apartments"' in banner
    assert "Banner Flat 6" not in banner


def test_inactive_properties_are_omitted(host):
    _insert_apartment("Inactive Flat", active=0)

    page = host.get("/?lang=en")

    assert 'class="notification-bubble warning"' not in page.text


@pytest.mark.skipif(os.environ.get("UBYHOST_CAPTURE_0047") != "1", reason="evidence capture")
def test_capture_banner_screenshots(host):
    from playwright.sync_api import sync_playwright

    out = Path(__file__).resolve().parents[2] / "generated_images" / "0047-evidence"
    out.mkdir(parents=True, exist_ok=True)
    widths = (360, 390, 1280)

    def save(label):
        html = host.get("/?lang=en").text
        assert 'class="notification-bubble warning"' in html
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            for width in widths:
                page = browser.new_page(viewport={"width": width, "height": 900})
                page.set_content(html, wait_until="load")
                page.screenshot(path=str(out / f"{label}-{width}.png"), full_page=True)
            browser.close()

    _insert_apartment("Demo Property 1")
    save("one-incomplete")
    for index in range(2, 7):
        _insert_apartment(f"Banner Flat {index}")
    save("six-incomplete")
