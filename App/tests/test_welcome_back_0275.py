"""0275: the welcome-back line after 14 days away (dates only)."""
from __future__ import annotations

import re
from datetime import date, timedelta

from app import db, welcome_back
from tests.test_onboarding_wizard_survival import _full_apartment, host  # noqa: F401

TODAY = date(2026, 10, 22)


def _set_seen(owner: int, value: str) -> None:
    db.set_setting(f"last_seen_{owner}", value)
    db.set_setting(f"welcome_back_{owner}", "")


def test_first_visit_no_line(host):
    owner = host["owner"]
    db.execute("DELETE FROM settings WHERE key IN (?, ?)", (f"last_seen_{owner}", f"welcome_back_{owner}"))
    assert welcome_back.check(owner, owner, TODAY) is None
    assert db.get_setting(f"last_seen_{owner}") == TODAY.isoformat()


def test_after_14_days_line_then_7_days_gone(host):
    owner = host["owner"]
    _set_seen(owner, "2026-10-01")
    got = welcome_back.check(owner, owner, TODAY)
    assert got is not None and got["since"] == "2026-10-01"
    assert welcome_back.check(owner, owner, date(2026, 10, 25)) is not None
    assert welcome_back.check(owner, owner, date(2026, 10, 30)) is None


def test_13_days_no_line(host):
    owner = host["owner"]
    _set_seen(owner, "2026-10-09")
    assert welcome_back.check(owner, owner, TODAY) is None


def test_dashboard_shows_and_dismiss_clears(host):
    client, owner = host["client"], host["owner"]
    _full_apartment(host)  # the dashboard body needs at least one apartment
    _set_seen(owner, (date.today() - timedelta(days=20)).isoformat())
    page = client.get("/?lang=en")
    assert page.status_code == 200
    assert "data-welcome-back" in page.text and "Welcome back!" in page.text
    token = re.search(r'name="_csrf" value="([^"]+)"', page.text).group(1)
    resp = client.post("/welcome-back/dismiss", data={"_csrf": token}, follow_redirects=False)
    assert resp.status_code == 303
    assert "data-welcome-back" not in client.get("/?lang=en").text


def test_counts_skip_demo(host):
    owner = host["owner"]
    flat = _full_apartment(host)
    _set_seen(owner, (date.today() - timedelta(days=20)).isoformat())
    base = welcome_back.check(owner, owner, date.today())["stays"]
    now = db.utcnow()
    for source, uid in (("ical", "w0275-real"), ("demo", "w0275-demo")):
        db.insert(
            "reservation",
            {
                "apartment_id": flat["id"],
                "source": source,
                "uid": uid,
                "date_from": TODAY.isoformat(),
                "date_to": TODAY.isoformat(),
                "created_at": now,
                "updated_at": now,
            },
        )
    assert welcome_back.check(owner, owner, date.today())["stays"] == base + 1


def test_check_uses_preloaded_settings(host):
    owner = host["owner"]
    _set_seen(owner, (TODAY - timedelta(days=20)).isoformat())
    settings = db.get_settings(welcome_back.keys_for(owner))
    assert welcome_back.check(owner, owner, TODAY, settings) is not None
