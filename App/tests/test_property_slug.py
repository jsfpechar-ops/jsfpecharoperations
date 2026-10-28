"""Brief 0430: property slug mapper, rename 301s, publication model."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import db, property_page
from app.main import app

OWNER = "slughost"


def _cleanup():
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))
    if not row:
        return
    oid = row["id"]
    for a in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (oid,)):
        db.execute("DELETE FROM property_slug WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_slug_history WHERE apartment_id = ?", (a["id"],))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


def _apartment(name: str, oid: int) -> int:
    return int(db.insert("apartment", {
        "owner_user_id": oid, "internal_name": name, "created_at": db.utcnow(),
    }))


@pytest.fixture
def owner():
    db.init_db()
    _cleanup()
    oid = db.insert("user_account", {"username": OWNER, "password_hash": "x",
                                     "created_at": db.utcnow()})
    try:
        yield int(oid)
    finally:
        _cleanup()


# --- mapper ---------------------------------------------------------------------


def test_slug_deterministic(owner):
    aid = _apartment("Vinohradská 11", owner)
    s1 = property_page.slug_for(aid, "Vinohradská 11")
    s2 = property_page.slug_for(aid, "Vinohradská 11")
    assert s1 == s2
    assert s1.startswith("vinohradska-11-")
    assert len(s1.rsplit("-", 1)[1]) == 4


def test_slug_folds_diacritics(owner):
    aid = _apartment("Chalupa u Brodu", owner)
    slug = property_page.slug_for(aid, "Chalupa u Brodu")
    assert slug.startswith("chalupa-u-brodu-")


def test_same_name_different_property(owner):
    a1 = _apartment("Apartmán u parku", owner)
    a2 = _apartment("Apartmán u parku", owner)
    assert property_page.slug_for(a1, "Apartmán u parku") != \
           property_page.slug_for(a2, "Apartmán u parku")


def test_ensure_slug_creates_once(owner):
    aid = _apartment("Test Flat", owner)
    property_page.ensure_slug(aid)
    row = property_page.ensure_slug(aid)
    assert row["slug"] == property_page.slug_for(aid, "Test Flat")
    assert db.query_one("SELECT COUNT(*) AS n FROM property_slug")["n"] == 1


def test_rename_keeps_redirect(owner):
    aid = _apartment("Old Name", owner)
    property_page.ensure_slug(aid)
    old = property_page.account_row(aid)["slug"]
    db.execute("UPDATE apartment SET internal_name = 'New Name' WHERE id = ?", (aid,))
    property_page.ensure_slug(aid)
    new = property_page.account_row(aid)["slug"]
    assert old != new
    resolved = property_page.resolve(old)
    assert resolved == {"redirect": new}
    assert property_page.resolve(new)["apartment_id"] == aid


# --- publication + routes ----------------------------------------------------


def test_unpublished_404_published_serves(owner):
    aid = _apartment("Pub Flat", owner)
    property_page.ensure_slug(aid)
    slug = property_page.account_row(aid)["slug"]
    assert property_page.resolve(slug)["missing"] is True
    property_page.publish(aid, published=True)
    resolved = property_page.resolve(slug)
    assert resolved["published"] == 1
    client = TestClient(app)
    response = client.get(f"/p/{slug}")
    assert response.status_code == 200
    client2 = TestClient(app)
    property_page.publish(aid, published=False)
    assert client2.get(f"/p/{slug}").status_code == 404


def test_unknown_slug_404(owner):
    client = TestClient(app)
    assert client.get("/p/does-not-exist-9999").status_code == 404


def test_history_redirect_via_route(owner):
    aid = _apartment("Renamed Flat", owner)
    property_page.ensure_slug(aid)
    old = property_page.account_row(aid)["slug"]
    property_page.publish(aid, published=True)
    db.execute("UPDATE apartment SET internal_name = 'Renamed Again' WHERE id = ?", (aid,))
    property_page.ensure_slug(aid)
    client = TestClient(app)
    response = client.get(f"/p/{old}", follow_redirects=False)
    assert response.status_code == 301
    assert response.headers["location"].startswith("/p/")


def test_cascade_prunes_with_apartment(owner):
    aid = _apartment("Doomed Flat", owner)
    property_page.ensure_slug(aid)
    property_page.publish(aid, published=True)
    db.execute("DELETE FROM apartment WHERE id = ?", (aid,))
    assert db.query_one("SELECT id FROM property_slug WHERE apartment_id = ?", (aid,)) is None
