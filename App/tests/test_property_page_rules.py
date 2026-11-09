"""Brief 0999: house rules on public property page and map link."""
from __future__ import annotations

import re
import json

import pytest
from fastapi.testclient import TestClient

from app import db, property_page
from app.main import app

OWNER = "ruleshost"


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
    aid = db.insert("apartment", {"owner_user_id": oid, "internal_name": "Rules Flat",
                                    "created_at": db.utcnow()})
    property_page.page_for(aid)
    try:
        yield int(aid)
    finally:
        _cleanup()


def test_prefill_takes_airbnb_rules(owner):
    aid = owner
    property_page.prefill_from_import(aid, {
        "raw_json": json.dumps({"houseRules": ["No parties", "Quiet after 22:00"]}),
    })
    assert property_page.page_for(aid)["house_rules"] == "No parties\nQuiet after 22:00"


def test_prefill_never_overwrites_host_rules(owner):
    aid = owner
    property_page.save_page(aid, description="", amenities=[], house_rules="Mine")
    property_page.prefill_from_import(aid, {
        "raw_json": json.dumps({"houseRules": ["No parties", "Quiet after 22:00"]}),
    })
    assert property_page.page_for(aid)["house_rules"] == "Mine"


def test_public_page_shows_rules_and_map_not_street(owner):
    aid = owner
    db.execute(
        "UPDATE apartment SET addr_obec = ?, addr_street = ?, addr_house_no = ? WHERE id = ?",
        ("Brno", "Tajna", "42", aid),
    )
    property_page.save_page(
        aid, description="", amenities=[], house_rules="No pets\nNo smoking",
    )
    property_page.publish_page(aid, published=True)
    slug = property_page.ensure_slug(aid)["slug"]
    response = TestClient(app).get(f"/p/{slug}")
    assert response.status_code == 200
    body = response.text
    assert "No pets" in body
    assert "mapy.cz" in body
    assert "Tajna" not in body
    # Street number as its own word; a bare "42" can sit inside the random CSRF token.
    assert not re.search(r"\b42\b", body)
    assert "<iframe" not in body.lower()
    assert 'script src="http' not in body.lower()


def test_no_map_link_without_town(owner):
    aid = owner
    db.execute(
        "UPDATE apartment SET addr_obec = ?, addr_street = ?, addr_house_no = ? WHERE id = ?",
        ("", "Secret", "1", aid),
    )
    property_page.publish_page(aid, published=True)
    slug = property_page.ensure_slug(aid)["slug"]
    response = TestClient(app).get(f"/p/{slug}")
    assert response.status_code == 200
    assert "mapy.cz" not in response.text
