"""0355: Quick answers chips in a real browser at 390 px (tap size, width, checked state, focus).

Skipped when Chromium is missing, unless UBYHOST_REQUIRE_BROWSER=1.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

from fastapi.testclient import TestClient

from app import auth, db, guest_guide
from app.main import app
from tests.conftest import login_as
from tests.test_property_navigation_browser import base, chromium_launch_kwargs, sync_api  # noqa: F401

SHOTS = Path(os.environ.get("UBYHOST_SHOTS_DIR") or Path(__file__).resolve().parents[1] / ".screenshots")
PROBE = r"""() => {
  const form = document.querySelector('form[action$="/quick/rules"]').getBoundingClientRect();
  const chips = [...document.querySelectorAll('[data-quick-fact="pets"] .quick-choice-option > span')].map(s => s.getBoundingClientRect());
  return {formWidth: form.width, chips: chips.map(c => [c.left, c.right, c.height]),
          scroll: document.documentElement.scrollWidth <= window.innerWidth};
}"""


def test_the_chips_are_big_full_width_and_show_their_state(base):  # noqa: F811
    db.init_db()
    user = f"quick-{secrets.token_hex(3)}"
    owner = auth.create_account(f"{user}@example.test", "Quick Host", role="host", username=user)
    apt_id = db.insert("apartment", {
        "owner_user_id": owner, "internal_name": "Quick flat", "active": 1, "created_at": db.utcnow(),
        "automation_mode": "manual",
    })
    guest_guide.ensure_defaults(db.query_one("SELECT * FROM apartment WHERE id = ?", (apt_id,)))
    client = TestClient(app)
    login_as(client, user, url="/login?lang=en")
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": client.cookies.get(auth.SESSION_COOKIE), "url": base + "/"}])
        page = context.new_page()
        page.goto(f"{base}/apartments/{apt_id}/guide/quick/rules?lang=en")
        box = page.evaluate(PROBE)
        assert box["scroll"], "the page scrolls sideways at 390 px"
        assert len(box["chips"]) == 3
        assert all(height >= 44 for _left, _right, height in box["chips"]), box
        assert box["chips"][2][1] - box["chips"][0][0] >= box["formWidth"] - 2, box  # the row spans the form
        unsure = page.locator('[data-quick-fact="pets"] input[value=""]')
        assert unsure.is_checked()
        page.locator('[data-quick-fact="pets"] label:has(input[value="no"])').click()  # a tap on the chip
        assert page.locator('[data-quick-fact="pets"] input[value="no"]').is_checked()
        page.wait_for_function(
            """() => {
                const bg = (v) => getComputedStyle(document.querySelector(`[data-quick-fact="pets"] input[value="${v}"] + span`)).backgroundColor;
                return bg("no") !== bg("yes");
            }""",
            timeout=3000,
        )  # the chip fills after its short colour transition
        page.keyboard.press("Tab")
        page.focus('[data-quick-fact="smoking"] input[value="yes"]')
        page.keyboard.press("ArrowRight")
        ring = page.evaluate("""() => getComputedStyle(document.activeElement.nextElementSibling).boxShadow""")
        assert ring and ring != "none", ring
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / "0355-quick-rules-390.png"), full_page=True)
        page.locator("button[type=submit]", has_text="Save and continue").click()
        page.wait_for_url("**/quick/access**")
        context.close()
        browser.close()
    assert db.query_one("SELECT value FROM guide_fact WHERE apartment_id = ? AND fact = 'pets'", (apt_id,))["value"] == "no"
