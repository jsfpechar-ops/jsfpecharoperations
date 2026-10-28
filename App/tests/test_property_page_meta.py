"""Brief 0433: sitemap, noindex default-on, OG tags, guest preview."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db, property_page
from app.main import app

OWNER = "metahost"


def _cleanup():
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))
    if not row:
        return
    oid = row["id"]
    for a in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (oid,)):
        db.execute("DELETE FROM property_slug WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_slug_history WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_page WHERE apartment_id = ?", (a["id"],))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM rate_limit_event", ())
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


@pytest.fixture
def owner():
    db.init_db()
    _cleanup()
    auth.create_account(f"{OWNER}@example.test", "Meta Host", username=OWNER)
    oid = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))["id"]
    aid = db.insert("apartment", {"owner_user_id": oid, "internal_name": "Meta Flat",
                                  "created_at": db.utcnow()})
    property_page.page_for(aid)
    property_page.publish_page(aid, published=True)
    try:
        yield int(aid)
    finally:
        _cleanup()


def _slug(aid: int) -> str:
    return property_page.account_row(aid)["slug"]


def test_sitemap_lists_only_published_search_visible(owner):
    client = TestClient(app)
    # default: hide_from_search = 1 → not in the sitemap
    response = client.get("/sitemap.xml")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/xml"
    assert _slug(owner) not in response.text
    # opt in to search → in the sitemap
    db.execute("UPDATE property_page SET hide_from_search = 0 WHERE apartment_id = ?", (owner,))
    response = client.get("/sitemap.xml")
    assert f"/p/{_slug(owner)}" in response.text


def test_sitemap_excludes_unpublished(owner):
    property_page.publish_page(owner, published=False)
    db.execute("UPDATE property_page SET hide_from_search = 0 WHERE apartment_id = ?", (owner,))
    client = TestClient(app)
    response = client.get("/sitemap.xml")
    assert _slug(owner) not in response.text


def test_noindex_default_on_and_switchable(owner):
    client = TestClient(app)
    client.cookies.set("ubyhost_lang", "cs")
    response = client.get(f"/p/{_slug(owner)}")
    assert response.status_code == 200
    assert '<meta name="robots" content="noindex">' in response.text
    db.execute("UPDATE property_page SET hide_from_search = 0 WHERE apartment_id = ?", (owner,))
    response = client.get(f"/p/{_slug(owner)}")
    assert 'name="robots"' not in response.text


def test_og_tags_render_with_photo(owner, monkeypatch):
    content = property_page.store_photo(_jpeg_bytes())
    db.execute(
        "UPDATE property_page SET photos_json = ?, description = 'A nice place by the park with everything you need.'"
        " WHERE apartment_id = ?",
        (json.dumps([content]), owner),
    )
    client = TestClient(app)
    response = client.get(f"/p/{_slug(owner)}")
    assert response.status_code == 200
    assert 'property="og:title"' in response.text
    assert 'property="og:image"' in response.text
    assert 'name="twitter:card"' in response.text
    assert config.PUBLIC_BASE_URL.rstrip("/") in response.text


def _jpeg_bytes() -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (10, 20, 30)).save(buf, "JPEG")
    return buf.getvalue()


def test_listing_page_is_english_only(owner):
    """Owner decision (28 Oct): the listing page renders English even for a
    Czech visitor; OTA listing copy is never translated per listing."""
    client = TestClient(app)
    client.cookies.set("ubyhost_lang", "cs")
    response = client.get(f"/p/{_slug(owner)}")
    assert response.status_code == 200
    assert '<html lang="en">' in response.text
