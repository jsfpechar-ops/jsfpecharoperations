"""0286: the property health check lives on the Overview cards."""
from __future__ import annotations

import re
import secrets

from fastapi.testclient import TestClient

from app import auth, db, demo
from app.main import app
from tests.conftest import login_as


def _client():
    db.init_db()
    user = f"hc-{secrets.token_hex(3)}"
    owner = auth.create_account(f"{user}@example.test", "Health Host", role="host", username=user)
    demo.seed(owner)
    client = TestClient(app)
    login_as(client, user, url="/login?lang=en")
    flat = db.query_one("SELECT id FROM apartment WHERE owner_user_id = ? ORDER BY id", (owner,))["id"]
    return client, flat


def _card(page, key):
    match = re.search(r'<(?:a|div) class="host-property-card[^"]*"[^>]*data-health-check="' + key + r'"[^>]*>.*?</(?:a|div)>', page, re.S)
    assert match, key
    return match.group(0)


def test_cards_carry_the_health_and_the_box_is_gone():
    client, flat = _client()
    for lang in ("en", "cs", "vi"):
        page = client.get(f"/apartments/{flat}?view=overview&lang={lang}").text
        assert 'class="panel host-checklist"' not in page and 'class="health-row"' not in page, lang
        for key in ("calendar", "guest_link", "police", "business"):
            assert "host-property-card-dot" in _card(page, key), (lang, key)


def test_a_problem_card_names_the_problem_and_opens_the_fix():
    client, flat = _client()
    db.execute("UPDATE ical_feed SET active = 0 WHERE apartment_id = ?", (flat,))
    page = client.get(f"/apartments/{flat}?view=overview&lang=en").text
    card = _card(page, "calendar")
    assert 'data-state="warn"' in card
    assert "host-property-card-problem" in card and "No calendar connected" in card
    assert f'href="/apartments/{flat}?view=bookings#calendars"' in card
