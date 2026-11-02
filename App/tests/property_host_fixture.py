"""Shared non-browser 'host' fixture: one synthetic host with a fully set-up property (moved out of test_property_navigation_browser so plain tests do not need Playwright)."""
from __future__ import annotations

import json
import secrets

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db, property_setup
from app.main import app
from tests.conftest import login_as


LOCK = {"lock_id": "70940001", "alias": "Synthetic Door", "battery": 90, "tz_offset_ms": 3600000}


@pytest.fixture
def host(monkeypatch):
    db.init_db()
    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", True)
    monkeypatch.setattr(config, "TTLOCK_CLIENT_ID", "cid")
    monkeypatch.setattr(config, "TTLOCK_CLIENT_SECRET", "csecret")
    username = f"nav-{secrets.token_hex(4)}"
    owner = auth.create_account(f"{username}@example.test", "Nav Host", role="host", username=username)
    now = db.utcnow()
    entities = [
        db.insert("legal_entity", {"name": name, "seat": "Praha", "ico": "12345678",
                                   "contact_email": "nav@example.test", "owner_user_id": owner, "created_at": now})
        for name in ("Synthetic Operator s.r.o.", "Synthetic Controller s.r.o.")
    ]
    apartment = db.insert("apartment", {
        "internal_name": "Synthetic Garden Flat", "city_en": "Brno", "owner_user_id": owner,
        "legal_entity_id": entities[0], "data_controller_entity_id": entities[1],
        "addr_obec": "Brno", "addr_house_no": "12", "addr_zip": "60200", "addr_street": "Synthetic",
        "uby_idub": "123456789012", "uby_mark": "SYNTH", "uby_name": "Synthetic Garden",
        "uby_ws_user": "UBY-WSsynth", "uby_contact": "host@example.test", "uby_ws_password_enc": db.encrypt_secret("synthetic-secret"),
        "automation_mode": "scheduled", "submit_after_hours": 6, "default_purpose": "10",
        "permalink_token": f"navtok{secrets.token_hex(4)}", "permalink_pin": "246810",
        "permalink_window_days": 3, "permalink_reachback_days": 90, "passport_photo_policy": "required_foreign",
        "guest_message": "Synthetic welcome.", "notes": "Synthetic note.",
        "stay_fee_rate_czk": 30, "stay_fee_cadence": "quarterly", "stay_fee_authority_name": "Synthetic Council",
        "lock_provider": "ttlock", "lock_id": LOCK["lock_id"], "checkin_hour": 15, "checkout_hour": 10,
        "active": 1, "created_at": now,
    })
    property_setup.start(apartment)
    property_setup.finish(apartment)
    db.insert("lock_account", {"owner_user_id": owner, "provider": "ttlock", "username": "synthetic_nav",
                               "status": "ok", "locks_json": json.dumps([LOCK]), "created_at": now, "updated_at": now})
    client = TestClient(app)
    assert login_as(client, username, url="/login?lang=en", follow_redirects=False).status_code == 303
    yield {"client": client, "owner": owner, "apartment": apartment, "entities": entities, "username": username}
    db.execute("DELETE FROM ical_feed WHERE apartment_id IN (SELECT id FROM apartment WHERE owner_user_id = ?)", (owner,))
    db.execute("DELETE FROM lock_account WHERE owner_user_id = ?", (owner,))

