"""0995: Booking site sidebar item and the /booking-sites list."""
import secrets

import pytest
from fastapi.testclient import TestClient

from app import auth, billing, config, db, property_page
from app.main import app
from tests.test_stay_fee_detail import login_as

_BSL_OWNERS: list[str] = []


def _cleanup_owner(username: str) -> None:
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (username,))
    if not row:
        return
    oid = row["id"]
    for a in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (oid,)):
        aid = a["id"]
        db.execute("DELETE FROM property_slug_history WHERE apartment_id = ?", (aid,))
        db.execute("DELETE FROM property_slug WHERE apartment_id = ?", (aid,))
        db.execute("DELETE FROM property_page WHERE apartment_id = ?", (aid,))
    db.execute("DELETE FROM billing_account WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM login_token WHERE user_account_id = ?", (oid,))
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


@pytest.fixture(scope="module", autouse=True)
def _booking_site_db():
    db.init_db()
    _BSL_OWNERS.clear()
    yield
    for username in list(_BSL_OWNERS):
        try:
            _cleanup_owner(username)
        except Exception:
            pass
    for row in db.query("SELECT id FROM apartment WHERE internal_name LIKE 'Flat %'"):
        aid = row["id"]
        db.execute("DELETE FROM property_slug_history WHERE apartment_id = ?", (aid,))
        db.execute("DELETE FROM property_slug WHERE apartment_id = ?", (aid,))
        db.execute("DELETE FROM property_page WHERE apartment_id = ?", (aid,))
        db.execute("DELETE FROM apartment WHERE id = ?", (aid,))
    _BSL_OWNERS.clear()


def _host(apartments):
    username = f"bsl-{secrets.token_hex(4)}"
    auth.create_account(f"{username}@example.test", "Site List", username=username)
    _BSL_OWNERS.append(username)
    oid = int(db.query_one("SELECT id FROM user_account WHERE username = ?", (username,))["id"])
    ids = [
        int(db.insert("apartment", {
            "owner_user_id": oid, "internal_name": f"Flat {name}-{secrets.token_hex(2)}",
            "created_at": db.utcnow(),
        }))
        for name in apartments
    ]
    client = TestClient(app)
    assert login_as(client, username, url="/login?lang=en", follow_redirects=False).status_code == 303
    return client, oid, ids


def _row(html, href):
    start = html.index(f'href="{href}"')
    return html[html.rfind("<a ", 0, start):html.index("</a>", start)]


def test_list_shows_properties_and_active_sidebar_row():
    client, _, ids = _host("AB")
    response = client.get("/booking-sites?lang=en")
    assert response.status_code == 200
    for aid in ids:
        assert f"/apartments/{aid}/booking-site" in response.text
    assert 'aria-current="page"' in _row(response.text, "/booking-sites")


def test_single_property_redirects_to_setup():
    client, _, ids = _host("A")
    response = client.get("/booking-sites?lang=en", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == f"/apartments/{ids[0]}/booking-site"


def test_non_max_owner_sees_upgrade_banner(monkeypatch):
    monkeypatch.setattr(config, "BILLING_ENABLED", True)
    monkeypatch.setattr(billing, "entitlements",
                        lambda oid: billing.Entitlements(status="active", plan="standard"))
    client, _, _ = _host("AB")
    response = client.get("/booking-sites?lang=en")
    assert response.status_code == 200
    assert "The booking site is part of the Max plan." in response.text
    assert 'href="/predplatne"' in response.text


def test_published_and_unpublished_badges():
    client, _, ids = _host("AB")
    property_page.ensure_slug(ids[0])
    property_page.page_for(ids[0])
    property_page.publish_page(ids[0], published=True)
    html = client.get("/booking-sites?lang=en").text
    assert "Live" in html
    assert "Not published" in html


def test_logged_out_redirects_to_login():
    response = TestClient(app).get("/booking-sites?lang=en", follow_redirects=False)
    assert response.status_code in (302, 303, 307)
    assert "/login" in response.headers["location"]


def test_setup_page_highlights_booking_site_row():
    client, _, ids = _host("A")
    response = client.get(f"/apartments/{ids[0]}/booking-site?lang=en")
    assert response.status_code == 200
    assert 'aria-current="page"' in _row(response.text, "/booking-sites")
    assert 'aria-current="page"' not in _row(response.text, "/apartments")


def test_phone_more_menu_links_booking_sites():
    client, _, _ = _host("A")
    html = client.get("/?lang=en").text
    assert 'class="ui-menu-item" href="/booking-sites"' in html
