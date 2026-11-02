"""0286: the property health check lives on the Overview cards."""
from __future__ import annotations

import re
import secrets

import pytest

from fastapi.testclient import TestClient

from app import auth, config, db, demo
from app.main import app
from tests.conftest import login_as


@pytest.fixture(autouse=True)
def _own_database(tmp_path):
    """Seed into a private database so later tests see the shared one untouched."""
    patcher = pytest.MonkeyPatch()
    db.close_connections()
    patcher.setattr(config, "DB_PATH", tmp_path / "health.sqlite3")
    patcher.setattr(demo.icalsync, "fetch_feed", lambda *_a, **_k: None)
    try:
        yield
    finally:
        db.close_connections()
        patcher.undo()


def _client():
    db.init_db()
    user = f"hc-{secrets.token_hex(3)}"
    owner = auth.create_account(f"{user}@example.test", "Health Host", role="host", username=user)
    demo.seed(owner)
    client = TestClient(app)
    login_as(client, user, url="/login?lang=en")
    flat = db.query_one("SELECT id FROM apartment WHERE owner_user_id = ? ORDER BY id", (owner,))["id"]
    return client, flat


def _row(page, href):
    match = re.search(r'<a class="r" href="' + re.escape(href) + r'"[^>]*>.*?</a>', page, re.S)
    assert match, href
    return match.group(0)


def test_cards_carry_the_health_and_the_box_is_gone():
    client, flat = _client()
    for lang in ("en", "cs", "vi"):
        page = client.get(f"/apartments/{flat}?view=overview&lang={lang}").text
        assert 'class="panel host-checklist"' not in page and 'class="health-row"' not in page, lang
        assert 'class="pv"' in page, lang
        for href in ("#sec-calendars", "#sec-police"):
            assert f'href="{href}"' in page, (lang, href)
        assert 'data-state=' in _row(page, "#sec-police"), lang


def test_a_problem_row_opens_the_fix_section():
    client, flat = _client()
    db.execute("UPDATE ical_feed SET last_status = 'error' WHERE apartment_id = ?", (flat,))
    page = client.get(f"/apartments/{flat}?view=overview&lang=en").text
    row = _row(page, "#sec-calendars")
    assert 'class="is-bad"' in row
