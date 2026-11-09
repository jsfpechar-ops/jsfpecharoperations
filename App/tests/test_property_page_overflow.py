from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import db, property_page
from app.main import app

OWNER = "overflowhost"


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
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


@pytest.fixture
def owner():
    db.init_db()
    _cleanup()
    oid = db.insert("user_account", {"username": OWNER, "password_hash": "x",
                                     "created_at": db.utcnow()})
    aid = db.insert("apartment", {"owner_user_id": oid, "internal_name": "Overflow Flat",
                                    "created_at": db.utcnow()})
    property_page.page_for(aid)
    try:
        yield int(aid)
    finally:
        _cleanup()


def test_long_unbroken_words_cannot_widen_the_public_page(owner):
    aid = owner
    property_page.save_page(
        aid,
        description="B" * 3000,
        amenities=["C" * 3000],
        house_rules="A" * 3000,
    )
    property_page.publish_page(aid, published=True)
    slug = property_page.ensure_slug(aid)["slug"]
    response = TestClient(app).get(f"/p/{slug}")
    assert response.status_code == 200
    body = response.text
    assert "overflow-wrap: anywhere" in body
    assert "A" * 3000 in body
    # The template shows the first 400 characters of the description, then the rest inside <details>,
    # so the 3000 characters are present as two runs, not one.
    assert "B" * 400 in body and "B" * 2600 in body
    assert "<li>" + "C" * 3000 + "</li>" in body
