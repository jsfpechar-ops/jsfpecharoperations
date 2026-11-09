"""Cleaning calendar (768 px and up): a stay pill never touches or covers a Cleaning chip, for 1, 2 and 3 stacked stays."""

import os
import secrets

import pytest

from app import auth, db
from tests.browser_support import chromium_launch_kwargs
from tests.test_0705_v2_shell_browser import _sync_playwright
from tests.test_host_geometry import _browser_session_cookie, base  # noqa: F401

# (flat, from, to): week 9-15 Nov gets three stacked stays, week 16-22 one stay, week 23-29 two.
STAYS = [("A", "2026-11-09", "2026-11-14"), ("B", "2026-11-12", "2026-11-17"), ("C", "2026-11-13", "2026-11-15"),
         ("A", "2026-11-17", "2026-11-20"), ("B", "2026-11-24", "2026-11-27"), ("C", "2026-11-25", "2026-11-29")]
CLEANINGS = [("A", "2026-11-14"), ("B", "2026-11-17"), ("C", "2026-11-15"), ("A", "2026-11-20"),
             ("B", "2026-11-27"), ("C", "2026-11-29"), ("A", "2026-11-26"), ("B", "2026-11-26")]


def _seed():
    username = f"pg{secrets.token_hex(3)}"
    owner = auth.create_account(f"{username}@example.test", "Pg", role="host", username=username)
    entity = db.insert("legal_entity", {"name": "Pg s.r.o.", "owner_user_id": owner, "created_at": db.utcnow()})
    now = db.utcnow()
    flats = {}
    for name in "ABC":
        flats[name] = db.insert("apartment", {"internal_name": f"Flat {name}", "owner_user_id": owner, "legal_entity_id": entity,
                                              "permalink_token": f"pg{secrets.token_hex(4)}", "active": 1,
                                              "created_at": now, "automation_mode": "manual"})
    for name, start, end in STAYS:
        db.insert("reservation", {"apartment_id": flats[name], "uid": secrets.token_hex(16), "source": "manual",
                                  "date_from": start, "date_to": end, "status": "active", "created_at": now, "updated_at": now})
    for name, day in CLEANINGS:
        db.insert("cleaning_event", {"apartment_id": flats[name], "scheduled_date": day, "state": "scheduled",
                                     "created_at": now, "updated_at": now})
    return username


MEASURE = """() => {
  const out = [];
  document.querySelectorAll('#calendar .cal-week').forEach(week => {
    const pills = [...week.querySelectorAll('.cal-pill')].map(n => n.getBoundingClientRect());
    week.querySelectorAll('.cal-day').forEach(day => {
      const d = day.getBoundingClientRect();
      day.querySelectorAll('.cal-clean-chip').forEach(chip => {
        const c = chip.getBoundingClientRect();
        let gap = 999;
        pills.forEach(p => { if (p.left < c.right && p.right > c.left) gap = Math.min(gap, c.top - p.bottom); });
        out.push({date: day.dataset.date || '', gap, inside: c.bottom <= d.bottom + 0.5, pills: pills.length});
      });
    });
  });
  return out;
}"""


@pytest.mark.parametrize("width", [768, 1024, 1280, 1440])
def test_pill_never_touches_cleaning_chip(base, width):
    username = _seed()
    with _sync_playwright().sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception as exc:
            if os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1":
                raise
            pytest.skip(f"Chromium is not available: {exc}")
        context = browser.new_context(viewport={"width": width, "height": 1000})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": _browser_session_cookie(username), "url": base + "/"}])
        page = context.new_page()
        page.goto(base + "/cleaning?lang=en&cal_view=calendar&cal_date=2026-11-03")
        page.wait_for_selector(".cal-week")
        page.wait_for_timeout(500)
        rows = page.evaluate(MEASURE)
        if os.environ.get("UBYHOST_TASK_SHOTS") == "1":
            out = os.environ.get("UBYHOST_SHOT_DIR", "/tmp")
            page.locator("#calendar").screenshot(path=f"{out}/{width}.png")
        browser.close()
    assert len(rows) >= 6, rows
    assert any(r["gap"] != 999 for r in rows), rows
    for r in rows:
        assert r["inside"], r
        assert r["gap"] >= 12, r
