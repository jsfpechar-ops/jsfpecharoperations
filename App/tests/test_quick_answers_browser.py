"""0355: Quick answers chips in a real browser at 390 px (tap size, width, checked state, focus).

Skipped when Chromium is missing, unless UBYHOST_REQUIRE_BROWSER=1.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

from fastapi.testclient import TestClient

from app import auth, db, guest_guide, guide_facts
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


# ---- 0966: the completion message tells the truth about saved answers and guest availability ----
STATE_TEXT = {
    "none": ("No answers were added", "Nebyly přidány žádné odpovědi"),
    "saved": ("Guests cannot see them yet", "Hosté je zatím nevidí"),
    "partial": ("Some cards still need your words", "Některé karty ještě potřebují"),
    "live": ("guests can see them inside the right cards", "hosté je vidí ve správných kartách"),
}
OVERFLOW = r"""() => {
  const clipped = [...document.querySelectorAll('.ui-banner, .ui-banner *, [data-empty-state], [data-empty-state] *')]
    .filter(e => e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).overflow !== 'visible');
  return {sideways: document.documentElement.scrollWidth > window.innerWidth, clipped: clipped.length};
}"""


def _host(prefix):
    db.init_db()
    user = f"{prefix}-{secrets.token_hex(3)}"
    owner = auth.create_account(f"{user}@example.test", "Truth Host", role="host", username=user)
    apt_id = db.insert("apartment", {
        "owner_user_id": owner, "internal_name": "Truth flat", "active": 1, "created_at": db.utcnow(),
        "automation_mode": "manual",
    })
    guest_guide.ensure_defaults(db.query_one("SELECT * FROM apartment WHERE id = ?", (apt_id,)))
    client = TestClient(app)
    login_as(client, user, url="/login?lang=en")
    return apt_id, client


def _fixture(apt_id, state):
    """none: every step skipped. saved: answers, guide not live. partial: live, cards open. live: no card open."""
    if state == "none":
        for step in guide_facts.STEPS:
            guide_facts.mark_seen(apt_id, step)
        return
    guide_facts.save_step(apt_id, "rules", {"pets": "no", "smoking": "no", "parties": "", "quiet_hours_from": "22:00", "quiet_hours_to": "07:00"})
    if state == "saved":
        return
    for row in guest_guide.items(apt_id):
        if state == "live" or row["kind"] in guest_guide.MUST_HAVE:
            guest_guide.save(apt_id, row["id"], {"steps": f"How to {row['kind']}"})


def test_completion_message_matches_each_state_without_http_browser(base):  # noqa: F811
    for state, (en, cs) in STATE_TEXT.items():
        apt_id, client = _host(f"truth-{state}")
        _fixture(apt_id, state)
        english = client.get(f"/apartments/{apt_id}/guide/quick/done?lang=en").text
        czech = client.get(f"/apartments/{apt_id}/guide/quick/done?lang=cs").text
        assert en in english and cs in czech, state
        assert "guest_guide." not in english and "guest_guide." not in czech
        for other, (other_en, _cs) in STATE_TEXT.items():
            if other != state:
                assert other_en not in english, (state, other)
    # all-skipped: an honest empty page, a way back, no promise, no "write the next card" push
    apt_id, client = _host("truth-skip")
    _fixture(apt_id, "none")
    page = client.get(f"/apartments/{apt_id}/guide/quick/done?lang=en").text
    assert "Back to the guide" in page and "Change answers" in page
    assert "Write the next card" not in page and 'id="quick-answers"' not in page
    assert "Guests now see" not in page and "can see them" not in page
    # the page only reads: nothing was published or changed by opening it
    before = guest_guide.progress(apt_id)
    client.get(f"/apartments/{apt_id}/guide/quick/done?lang=en")
    assert guest_guide.progress(apt_id) == before and not before["live"]


def test_completion_and_empty_questions_in_chromium(base):  # noqa: F811
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        for state, texts in STATE_TEXT.items():
            apt_id, client = _host(f"truthb-{state}")
            _fixture(apt_id, state)
            for lang, expected in zip(("en", "cs"), texts):
                for width in (390, 768, 1280):
                    context = browser.new_context(viewport={"width": width, "height": 900})
                    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": client.cookies.get(auth.SESSION_COOKIE), "url": base + "/"}])
                    page = context.new_page()
                    page.goto(f"{base}/apartments/{apt_id}/guide/quick/done?lang={lang}")
                    assert expected in page.locator(".ui-banner").inner_text(), (state, lang, width)
                    assert page.locator(".ui-banner").count() == 1
                    probe = page.evaluate(OVERFLOW)
                    assert not probe["sideways"] and probe["clipped"] == 0, (state, lang, width, probe)
                    page.screenshot(path=str(SHOTS / f"0966-done-{state}-{lang}-{width}.png"), full_page=True)
                    if state == "none":
                        assert page.get_by_role("link", name="Back to the guide" if lang == "en" else "Zpět na průvodce").count() >= 1
                    context.close()
        apt_id, client = _host("truthb-questions")
        for lang, title in (("en", "No questions yet"), ("cs", "Zatím žádné dotazy")):
            for width in (390, 768, 1280):
                context = browser.new_context(viewport={"width": width, "height": 900})
                context.add_cookies([{"name": auth.SESSION_COOKIE, "value": client.cookies.get(auth.SESSION_COOKIE), "url": base + "/"}])
                page = context.new_page()
                page.goto(f"{base}/apartments/{apt_id}/guide/questions?lang={lang}")
                assert page.locator("[data-empty-state]").count() == 1, (lang, width)
                assert page.locator(".settings-value-card").count() == 0, (lang, width)
                assert page.get_by_text(title).count() == 1, (lang, width)
                assert page.locator("[data-empty-state] a.ui-btn").count() == 1, (lang, width)  # one next step
                probe = page.evaluate(OVERFLOW)
                assert not probe["sideways"] and probe["clipped"] == 0, (lang, width, probe)
                page.screenshot(path=str(SHOTS / f"0966-questions-empty-{lang}-{width}.png"), full_page=True)
                context.close()
        browser.close()
