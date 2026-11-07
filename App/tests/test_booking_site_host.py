"""0995: Booking site sidebar item and the /booking-sites list."""
import secrets

from fastapi.testclient import TestClient

from app import auth, billing, config, db, property_page
from app.main import app
from tests.test_stay_fee_detail import login_as


def _host(apartments):
    db.init_db()
    username = f"bsl-{secrets.token_hex(4)}"
    auth.create_account(f"{username}@example.test", "Site List", username=username)
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
