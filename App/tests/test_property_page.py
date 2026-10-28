"""Brief 0431: page prefill from imports, review screen, public template."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import auth, db, property_page
from app.main import app
from tests.conftest import login_as

OWNER = "pagehost"


def _cleanup():
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))
    if not row:
        return
    oid = row["id"]
    for a in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (oid,)):
        db.execute("DELETE FROM property_slug WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_slug_history WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_page WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM guide_import WHERE apartment_id = ?", (a["id"],))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM alert WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM rate_limit_event", ())
    db.execute("DELETE FROM login_token", ())
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


@pytest.fixture
def owner():
    db.init_db()
    _cleanup()
    auth.create_account(f"{OWNER}@example.test", "Page Host", username=OWNER)
    oid = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))["id"]
    try:
        yield int(oid)
    finally:
        _cleanup()


@pytest.fixture
def client(owner):
    client = TestClient(app)
    response = login_as(client, OWNER, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303
    return client


def _apartment(oid: int, name="Page Flat") -> int:
    return int(db.insert("apartment", {
        "owner_user_id": oid, "internal_name": name, "created_at": db.utcnow(),
    }))


def _import_row(aid: int, data: dict) -> dict:
    import_id = db.insert("guide_import", {
        "apartment_id": aid, "source": "airbnb",
        "url": "https://www.airbnb.com/rooms/1", "status": "done",
        "raw_json": json.dumps(data), "created_at": db.utcnow(),
    })
    return dict(db.query_one("SELECT * FROM guide_import WHERE id = ?", (import_id,)))


# --- prefill (deterministic, no AI) ---------------------------------------


def test_prefill_maps_fields_verbatim(owner):
    aid = _apartment(owner)
    row = _import_row(aid, {
        "description": "Cosy flat near the park.",
        "checkIn": "From 3:00 PM", "checkOut": "Until 10:00 AM",
        "amenities": ["Wifi", "Kitchen"],
    })
    property_page.prefill_from_import(aid, row)
    page = property_page.page_for(aid)
    assert page["description"] == "Cosy flat near the park."
    assert page["checkin_text"] == "From 3:00 PM"
    assert page["checkout_text"] == "Until 10:00 AM"
    assert json.loads(page["amenities_json"]) == ["Wifi", "Kitchen"]


def test_prefill_never_overwrites_host_edits(owner):
    aid = _apartment(owner)
    property_page.save_page(aid, description="Host's own words", amenities=[])
    row = _import_row(aid, {"description": "Scraper text"})
    property_page.prefill_from_import(aid, row)
    assert property_page.page_for(aid)["description"] == "Host's own words"


# --- review screen + publish ----------------------------------------------


def test_review_screen_and_publish(owner, client):
    aid = _apartment(owner)
    response = client.get(f"/apartments/{aid}/page")
    assert response.status_code == 200
    assert "Not published" in response.text
    client.post(f"/apartments/{aid}/page", data={"publish": "1"}, follow_redirects=False)
    response = client.get(f"/apartments/{aid}/page")
    assert "Published" in response.text
    slug = property_page.account_row(aid)["slug"]
    public = TestClient(app)
    assert public.get(f"/p/{slug}").status_code == 200


def test_review_save(owner, client):
    aid = _apartment(owner)
    client.post(f"/apartments/{aid}/page",
                data={"description": "Edited", "amenities": "Wifi\nParking"},
                follow_redirects=False)
    page = property_page.page_for(aid)
    assert page["description"] == "Edited"
    assert json.loads(page["amenities_json"]) == ["Wifi", "Parking"]


def test_foreign_apartment_404(owner, client):
    _apartment(owner)
    other = int(db.insert("user_account", {"username": "otherpp",
                                            "password_hash": "x",
                                            "created_at": db.utcnow()}))
    foreign = int(db.insert("apartment", {
        "owner_user_id": other, "internal_name": "Not Yours", "created_at": db.utcnow()}))
    assert client.get(f"/apartments/{foreign}/page").status_code == 404
    db.execute("DELETE FROM apartment WHERE id = ?", (foreign,))
    db.execute("DELETE FROM user_account WHERE id = ?", (other,))


# --- public template -----------------------------------------------------------


def test_public_page_renders_sections(owner):
    aid = _apartment(owner)
    db.execute("UPDATE apartment SET addr_obec = 'Praha', addr_obec_cast = 'Vinohrady'"
               " WHERE id = ?", (aid,))
    property_page.save_page(aid, description="A lovely stay." * 200,
                            amenities=["Wifi"])
    db.execute("UPDATE property_page SET checkin_text = '3 PM' WHERE apartment_id = ?", (aid,))
    db.insert("guide_item", {
        "apartment_id": aid, "topic": "arrival", "kind": "custom",
        "title": "Keys in the box", "steps": "The box code is on your stay link.",
        "location": "", "watch_out": "", "video_url": "",
        "visibility": "everyone", "state": "done", "source": "host",
        "sort_order": 0, "created_at": db.utcnow(), "updated_at": db.utcnow(),
    })
    property_page.publish_page(aid, published=True)
    slug = property_page.account_row(aid)["slug"]
    public = TestClient(app)
    response = public.get(f"/p/{slug}")
    assert response.status_code == 200
    assert "Page Flat" in response.text
    assert "Praha" in response.text and "Vinohrady" in response.text
    assert "A lovely stay." in response.text
    assert "3 PM" in response.text
    assert "Keys in the box" in response.text
    assert "<details" in response.text  # long description collapses, no JS
    # draft and non-everyone guide items never publish
    db.execute("UPDATE guide_item SET state = 'missing' WHERE apartment_id = ?", (aid,))
    response = public.get(f"/p/{slug}")
    assert "Keys in the box" not in response.text


def test_unpublished_page_404_even_with_content(owner):
    aid = _apartment(owner)
    property_page.save_page(aid, description="Hidden text", amenities=[])
    property_page.ensure_slug(aid)
    slug = property_page.account_row(aid)["slug"]
    public = TestClient(app)
    assert public.get(f"/p/{slug}").status_code == 404
