"""0285: Properties rows are bordered cards like Stays rows; Stays opens on
Upcoming & current; the Guest links arrow keeps a gap from the name."""
from __future__ import annotations

import secrets

from fastapi.testclient import TestClient

from app import auth, db, demo
from app.main import app
from tests.conftest import login_as
from tests.test_property_navigation_browser import base, chromium_launch_kwargs, sync_api  # noqa: F401

ROW = """sel => { const tr = document.querySelector(sel); const tds = [...tr.children];
  const first = getComputedStyle(tds[0]), last = getComputedStyle(tds[tds.length - 1]);
  return {left: first.borderLeftStyle, right: last.borderRightStyle, radius: parseFloat(first.borderTopLeftRadius),
          spacing: getComputedStyle(tr.closest('table')).borderSpacing}; }"""


def _client():
    db.init_db()
    user = f"rows-{secrets.token_hex(3)}"
    owner = auth.create_account(f"{user}@example.test", "Rows Host", role="host", username=user)
    demo.seed(owner)
    client = TestClient(app)
    login_as(client, user, url="/login?lang=en")
    return client


def test_stays_open_on_upcoming_and_current():
    client = _client()
    page = client.get("/reservations?lang=en").text
    assert 'aria-current="true">Upcoming &amp; current<' in page or 'aria-current="true">Upcoming & current<' in page
    page = client.get("/reservations?range=all&lang=en").text
    assert 'aria-current="true">All dates<' in page


