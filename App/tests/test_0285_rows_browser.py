"""0285: Properties rows are bordered cards like Stays rows; Stays opens on
Upcoming & current; the Guest links arrow keeps a gap from the name."""
from __future__ import annotations

import secrets

from fastapi.testclient import TestClient

from app import auth, db, demo
from app.main import app
from tests.conftest import login_as, mark_security_prompt_seen
from tests.test_property_navigation_browser import base, chromium_launch_kwargs, sync_api  # noqa: F401

ROW = """sel => { const tr = document.querySelector(sel); const tds = [...tr.children];
  const first = getComputedStyle(tds[0]), last = getComputedStyle(tds[tds.length - 1]);
  return {left: first.borderLeftStyle, right: last.borderRightStyle, radius: parseFloat(first.borderTopLeftRadius),
          spacing: getComputedStyle(tr.closest('table')).borderSpacing}; }"""


def _client():
    db.init_db()
    user = f"rows-{secrets.token_hex(3)}"
    owner = mark_security_prompt_seen(auth.create_account(f"{user}@example.test", "Rows Host", role="host", username=user))
    demo.seed(owner)
    client = TestClient(app)
    login_as(client, user, url="/login?lang=en")
    return client


def test_stays_open_on_upcoming_and_current():
    client = _client()
    page = client.get("/reservations?lang=en").text
    assert 'aria-current="page">Upcoming &amp; current<' in page
    # v2 (0528): the mockup has no "All dates" chip, so no chip is current on range=all.
    page = client.get("/reservations?range=all&lang=en").text
    assert 'class="chip on"' not in page


