"""0884: the wizard pages at six widths: text inset, button gaps, overlap, text size, no sideways scroll."""
import json
import os
import secrets
from pathlib import Path

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth, db, demo
from tests.conftest import mark_security_prompt_seen
from tests.browser_support import chromium_launch_kwargs
from tests.test_host_geometry import _browser_session_cookie, base  # noqa: F401

SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0884"
WIDTHS = (320, 390, 768, 1024, 1280, 1440)
PAGES = ("property", "property-no-business", "calendar", "police", "guest_link", "done", "try_it", "try_it-open", "try_it-registered")
SHOT_PAGES = ("property", "property-no-business", "police", "done", "try_it", "try_it-open", "try_it-registered")
SUGGEST = [{"label": "Synthetická 12/3, Brno", "fields": {
    "addr_street": "Synthetická", "addr_house_no": "12", "addr_orient_no": "3", "addr_zip": "60200",
    "addr_obec": "Brno", "addr_obec_cast": "Černá Pole", "addr_okres": "Brno-město"}}]
CHECK = r"""() => {
  const root = document.querySelector('.setup-wizard');
  const CARD = '.setup-summary-card, .ui-choice-card, .setup-wizard-note-box, .setup-wizard-celebrate, .wizard-ares';
  const BTN = 'button:not(.setup-demo-message-link), a.ui-btn, input[type=submit]';
  const CTRL = 'button, a.ui-btn, input:not([type=hidden]), select, textarea';
  const shown = el => {
    for (let n = el; n && n !== document.body; n = n.parentElement) {
      const s = getComputedStyle(n);
      if (s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0') return false;
    }
    const r = el.getBoundingClientRect();
    return r.width > 1 && r.height > 1;
  };
  const texts = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode, el = node.parentElement;
    if (!node.textContent.trim() || !el || el.closest('.help-tip-body, .visually-hidden, .sr-only, script, style, noscript, option, textarea') || !shown(el)) continue;
    const range = document.createRange();
    range.selectNodeContents(node);
    for (const r of range.getClientRects()) if (r.width > 0 && r.height > 0) texts.push({el, r, text: node.textContent.trim().slice(0, 40)});
  }
  const bad = {small: [], inset: [], gap: [], overlap: [], scroll: []};
  for (const t of texts) {
    const size = parseFloat(getComputedStyle(t.el).fontSize);
    if (size < 14) bad.small.push([t.text, size]);
    const card = t.el.closest(CARD);
    if (card) {
      const c = card.getBoundingClientRect();
      const inset = Math.min(t.r.left - c.left, c.right - t.r.right, t.r.top - c.top, c.bottom - t.r.bottom);
      if (inset < 15.5) bad.inset.push([t.text, Math.round(inset)]);
    }
  }
  const buttons = [...root.querySelectorAll(BTN)].filter(b => !b.matches('.help-tip-btn') && shown(b));
  for (const b of buttons) {
    const br = b.getBoundingClientRect();
    for (const t of texts) {
      if (b.contains(t.el)) continue;
      const dx = Math.max(0, br.left - t.r.right, t.r.left - br.right);
      const dy = Math.max(0, br.top - t.r.bottom, t.r.top - br.bottom);
      if (Math.max(dx, dy) < 11.5) bad.gap.push([(b.textContent || b.value || '').trim().slice(0, 30), t.text, Math.round(Math.max(dx, dy))]);
    }
  }
  const controls = [...root.querySelectorAll(CTRL)].filter(shown);
  for (let i = 0; i < controls.length; i++) for (let j = i + 1; j < controls.length; j++) {
    if (controls[i].contains(controls[j]) || controls[j].contains(controls[i])) continue;
    const a = controls[i].getBoundingClientRect(), c = controls[j].getBoundingClientRect();
    const w = Math.min(a.right, c.right) - Math.max(a.left, c.left), h = Math.min(a.bottom, c.bottom) - Math.max(a.top, c.top);
    if (w > 1 && h > 1) bad.overlap.push([controls[i].outerHTML.slice(0, 60), controls[j].outerHTML.slice(0, 60)]);
  }
  if (document.documentElement.scrollWidth > innerWidth) bad.scroll.push(document.documentElement.scrollWidth);
  return bad;
}"""


def _flat(with_business: bool):
    username = f"g884{secrets.token_hex(3)}"
    owner = mark_security_prompt_seen(auth.create_account(f"{username}@example.test", "Geometry", role="host", username=username))
    entity = None
    if with_business:
        entity = db.insert("legal_entity", {"name": "Geometry s.r.o.", "owner_user_id": owner, "created_at": db.utcnow()})
    apartment = db.insert("apartment", {"internal_name": "Geometry flat", "owner_user_id": owner, "legal_entity_id": entity,
                                        "permalink_token": f"g8{secrets.token_hex(4)}", "active": 1, "created_at": db.utcnow()})
    return username, apartment


@pytest.mark.parametrize("lang", ["en", "cs"])
@pytest.mark.parametrize("width", WIDTHS)
def test_wizard_pages_keep_their_geometry(base, width, lang):
    failures = {}
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception as exc:
            if REQUIRE_BROWSER:
                raise
            pytest.skip(f"Chromium is not available: {exc}")
        for with_business in (True, False):
            username, apartment = _flat(with_business)
            context = browser.new_context(viewport={"width": width, "height": 900})
            context.add_cookies([{"name": auth.SESSION_COOKIE, "value": _browser_session_cookie(username), "url": base + "/"}])
            page = context.new_page()
            for name in PAGES:
                if (name == "property-no-business") == with_business:
                    continue
                step = "property" if name == "property-no-business" else name.split("-")[0] if name.startswith("try_it") else name
                if name in ("try_it-open", "try_it-registered") and not demo.demo_stay_for(apartment):
                    demo.create_demo_stay(apartment)
                if name == "try_it-registered":
                    demo._guest(demo.demo_stay_for(apartment)["id"], True, surname="Smith", first_name="John Paul",
                                birth_date="01011990", nationality="GBR", doc_number="P1234567",
                                res_street="Baker Street 221B", res_city="London", res_country="GBR", purpose="10")
                page.goto(f"{base}/apartments/{apartment}/setup/{step}?lang={lang}")
                page.wait_for_selector(".setup-wizard", timeout=30000)
                bad = {key: value for key, value in page.evaluate(CHECK).items() if value}
                if bad:
                    failures[name] = bad
                if lang == "en" and width in (390, 1280) and name in SHOT_PAGES:
                    SHOTS.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(SHOTS / f"{name}-{width}.png"), full_page=True)
                if name == "property" and lang == "en" and width == 390 and page.locator("input[data-ruian-suggest]").count():
                    page.route("**/apartments/ruian-suggest*", lambda route: route.fulfill(
                        status=200, content_type="application/json", body=json.dumps(SUGGEST)))
                    page.fill("input[data-ruian-suggest]", "Synt")
                    page.wait_for_selector(".ruian-suggest li", timeout=5000)
                    page.screenshot(path=str(SHOTS / "property-suggest-390.png"), full_page=True)
            context.close()
        browser.close()
    assert not failures, failures


def test_try_it_can_be_skipped_or_left_by_click(base):
    username, apartment = _flat(True)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = browser.new_context(viewport={"width": 390, "height": 900})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": _browser_session_cookie(username), "url": base + "/"}])
        page = context.new_page()
        setup = f"{base}/apartments/{apartment}/setup"
        page.goto(f"{setup}/done?lang=en")
        page.locator("[data-setup-next-step=try_it] a").click()
        page.wait_for_url("**/setup/try_it**")
        page.get_by_role("link", name="Leave the demo").click()
        page.wait_for_url("**/setup/done**")
        demo.create_demo_stay(apartment)
        page.goto(f"{setup}/try_it?lang=en")
        page.get_by_role("link", name="Leave the demo").click()
        page.wait_for_url("**/setup/done**")
        assert demo.demo_stay_for(apartment)
        page.goto(f"{setup}/try_it?lang=en")
        page.locator(".setup-wizard-skip button").click()
        page.wait_for_url("**/setup/done**")
        assert demo.demo_stay_for(apartment) is None
        context.close()
        browser.close()
