"""0252: every host page, on phone, three iPad sizes (touch) and desktop.

Checks the owner's sweep rules: nothing important sits off-screen, every
clickable row or card shows an Open cue, and a tap in its middle lands on
something clickable. Set UBYHOST_SHOTS_DIR to keep a screenshot per page.
"""
from __future__ import annotations

import os
import secrets

from fastapi.testclient import TestClient

from app import auth, db, demo
from app.main import app
from tests.conftest import login_as
from tests.test_property_navigation_browser import base, chromium_launch_kwargs, sync_api  # noqa: F401

IPAD = "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
PHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
SIZES = [
    ("phone390", 390, 844, PHONE, True),
    ("ipad820", 820, 1180, IPAD, True),
    ("ipad1024", 1024, 1366, IPAD, True),
    ("ipad1180", 1180, 820, IPAD, True),
    ("desk1280", 1280, 900, None, False),
    ("desk2000", 2000, 1100, None, False),
]
PROBE = r"""() => {
  const vw = document.documentElement.clientWidth;
  const out = {overflow: document.documentElement.scrollWidth > vw + 1, outside: [], noCue: [], deadMiddle: []};
  const shown = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden'; };
  const main = document.querySelector('main') || document.body;
  const name = e => (e.querySelector('strong, .row-primary-link, td') || e).textContent.trim().replace(/\s+/g, ' ').slice(0, 40);
  for (const e of main.querySelectorAll('a, button, input, select, textarea, h1, h2, h3')) {
    if (!shown(e) || e.closest('.cal-scroll, [data-dashboard-calendar], .notification-stack')) continue;
    const r = e.getBoundingClientRect();
    if (r.right > vw + 1 || r.left < -1) {
      if (e.closest('.scroll-x')) continue;
      out.outside.push((e.textContent || e.name || e.tagName).trim().slice(0, 30));
    }
  }
  for (const e of main.querySelectorAll('tr.clickable-row:not(.dashboard-row), a.host-property-card')) {
    if (!shown(e)) continue;
    if (!e.querySelector('.row-open, .host-property-card-open, .ui-btn-open')) out.noCue.push(name(e));
    const r = e.getBoundingClientRect();
    const x = r.left + Math.min(r.width / 2, 120), y = r.top + Math.min(r.height / 2, 24);
    if (y > 0 && y < innerHeight && x < vw) {
      const hit = document.elementFromPoint(x, y);
      if (hit && !hit.closest('a, [data-href], button, label, input, summary')) out.deadMiddle.push(name(e));
    }
  }
  return out;
}"""


def test_every_host_page_on_phone_ipad_and_desktop(base):
    db.init_db()
    user = f"sweep-{secrets.token_hex(3)}"
    owner = auth.create_account(f"{user}@example.test", "Sweep Host", role="host", username=user)
    demo.seed(owner)
    client = TestClient(app)
    login_as(client, user, url="/login?lang=en")
    flats = db.query("SELECT id FROM apartment WHERE owner_user_id = ? ORDER BY id", (owner,))
    stay = db.query_one(
        "SELECT r.id FROM reservation r JOIN apartment a ON a.id = r.apartment_id WHERE a.owner_user_id = ? ORDER BY r.id",
        (owner,),
    )
    flat = flats[0]["id"]
    pages = [
        "/", "/reservations", f"/reservations/{stay['id']}", "/apartments",
        f"/apartments/{flat}?view=overview", f"/apartments/{flat}?view=bookings",
        f"/apartments/{flat}?view=settings&section=reporting", "/entities", "/submissions",
        "/housebook", "/invoices", "/invoices/new", "/stay-fees", "/cleaning", "/settings",
        "/settings/archived", "/guide", "/privacy-requests",
    ]
    shots = os.environ.get("UBYHOST_SHOTS_DIR")
    problems = []
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        for tag, width, height, agent, touch in SIZES:
            options = {"viewport": {"width": width, "height": height}, "has_touch": touch, "is_mobile": touch}
            if agent:
                options["user_agent"] = agent
            context = browser.new_context(**options)
            context.add_cookies([{"name": auth.SESSION_COOKIE, "value": client.cookies.get(auth.SESSION_COOKIE), "url": base + "/"}])
            page = context.new_page()
            for path in pages:
                response = page.goto(base + path + ("&" if "?" in path else "?") + "lang=en")
                assert response and response.status == 200, (tag, path, response and response.status)
                page.wait_for_timeout(200)
                found = {key: value for key, value in page.evaluate(PROBE).items() if value}
                if found:
                    problems.append((tag, path, found))
                if shots:
                    os.makedirs(shots, exist_ok=True)
                    slug = path.strip("/").replace("/", "-").replace("?", "-").replace("&", "-").replace("=", "-") or "dashboard"
                    page.screenshot(path=os.path.join(shots, f"{slug}-{tag}.png"), full_page=True)
            context.close()
        browser.close()
    assert not problems, problems
