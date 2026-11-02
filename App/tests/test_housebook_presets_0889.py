"""0889: one-tap stay-date presets above the housebook filter."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import auth, claim, db, housebook
from app.main import app
from tests.conftest import login_as


def test_presets_cover_whole_months():
    assert housebook.period_presets(date(2026, 3, 15)) == [
        ("housebook.preset.this_month", date(2026, 3, 1), date(2026, 3, 31)),
        ("housebook.preset.last_month", date(2026, 2, 1), date(2026, 2, 28)),
        ("housebook.preset.this_year", date(2026, 1, 1), date(2026, 12, 31)),
    ]
    last = housebook.period_presets(date(2026, 1, 10))[1]
    assert last == ("housebook.preset.last_month", date(2025, 12, 1), date(2025, 12, 31))


def _cleanup():
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", ("housebook-presets",))
    if row:
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (row["id"],))
        db.execute("DELETE FROM user_account WHERE id = ?", (row["id"],))


@pytest.fixture
def host(monkeypatch):
    db.init_db()
    _cleanup()
    monkeypatch.setattr(claim, "prague_today", lambda: date(2026, 3, 15))
    auth.create_account("housebook-presets@example.test", "Presets", role="host", username="housebook-presets")
    client = TestClient(app)
    assert login_as(client, "housebook-presets", url="/login?lang=en", follow_redirects=False).status_code == 303
    try:
        yield client
    finally:
        _cleanup()


def test_page_shows_presets_and_marks_the_current_one(host):
    page = host.get("/housebook?lang=en")
    assert page.status_code == 200
    assert "from=2026-02-01&amp;to=2026-02-28" in page.text
    assert "Last month" in page.text

    active = host.get("/housebook?from=2026-02-01&to=2026-02-28&lang=en")
    assert active.status_code == 200
    nav = active.text.split('class="housebook-presets"', 1)[1].split("</nav>", 1)[0]
    assert nav.count('aria-current="true"') == 1
    assert "from=2026-02-01&amp;to=2026-02-28" in nav
