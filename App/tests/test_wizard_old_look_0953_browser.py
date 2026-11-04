"""0953: old look on the dashboard checklist, the banner, the wizard and the operator form at 390, 768 and 1280 px."""
import os
import secrets
from pathlib import Path

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth, db, property_setup
from tests.browser_support import chromium_launch_kwargs
from tests.test_host_geometry import _browser_session_cookie, base  # noqa: F401

SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0953"
WIDTHS = (390, 768, 1280)
PAGES = ("checklist", "apartments", "property", "police", "entities")

CHECK = r"""(page) => {
  const bad = [];
  const shown = el => { const r = el.getBoundingClientRect(); return r.width > 1 && r.height > 1; };
  if (document.documentElement.scrollWidth > innerWidth) bad.push(['scroll', document.documentElement.scrollWidth]);
  if (page === 'checklist') {
    const steps = [...document.querySelectorAll('.onboarding-welcome:not([data-layout=v2]) .onboarding-step')];
    if (!steps.length) bad.push(['no steps']);
    for (const s of steps) if (parseFloat(getComputedStyle(s).borderTopWidth) <= 0) bad.push(['step border', s.className]);
    for (const i of document.querySelectorAll('.onboarding-welcome:not([data-layout=v2]) .onboarding-step-index')) {
      if (i.getBoundingClientRect().width < 28) bad.push(['index width', i.getBoundingClientRect().width]);
      if (parseFloat(getComputedStyle(i).borderRadius) <= 0) bad.push(['index radius']);
    }
    for (const fill of document.querySelectorAll('.onboarding-welcome:not([data-layout=v2]) .onboarding-meter > div i')) {
      if (parseFloat(fill.style.width) > 0 && fill.getBoundingClientRect().width <= 0) bad.push(['meter fill', fill.style.width]);
    }
  }
  if (page === 'checklist') {
    const card = document.querySelector('.onboarding-demo');
    if (card) {
      const text = card.firstElementChild.getBoundingClientRect(), btn = card.querySelector('form button').getBoundingClientRect(), box = card.getBoundingClientRect(), cs = getComputedStyle(card), inner = box.width - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
      if (innerWidth >= 640 && text.width < 0.6 * inner) bad.push(['demo text width', Math.round(text.width), Math.round(inner)]);
      const overlap = Math.min(text.right, btn.right) - Math.max(text.left, btn.left) > 1 && Math.min(text.bottom, btn.bottom) - Math.max(text.top, btn.top) > 1;
      if (overlap) bad.push(['demo button overlaps text']);
      if (innerWidth < 640 && btn.width < 0.9 * inner) bad.push(['demo button not full width', Math.round(btn.width)]);
    }
  }
  for (const k of document.querySelectorAll('.onboarding-skip-link')) {
    if (!shown(k)) continue;
    const cs = getComputedStyle(k);
    if (!cs.textDecorationLine.includes('underline')) bad.push(['skip underline', cs.textDecorationLine]);
    if (k.getBoundingClientRect().height >= 60) bad.push(['skip height', k.getBoundingClientRect().height]);
    if (cs.backgroundColor !== 'rgba(0, 0, 0, 0)') bad.push(['skip fill', cs.backgroundColor]);
  }
  const primary = document.querySelector('.onboarding-banner-setup-link');
  if (primary && shown(primary) && innerWidth <= 768 && primary.getBoundingClientRect().height < 44) bad.push(['primary height', primary.getBoundingClientRect().height]);
  if (page === 'property' || page === 'police') {
    const bars = [...document.querySelectorAll('.setup-wizard-progress li')];
    if (!bars.length) bad.push(['no progress strip']);
    for (const li of bars) if (li.getBoundingClientRect().height !== 8) bad.push(['progress height', li.getBoundingClientRect().height]);
    const body = document.querySelector('.setup-wizard-body');
    if (body && parseFloat(getComputedStyle(body).borderTopWidth) <= 0) bad.push(['wizard card border']);
  }
  const skip = ['wizard-ares-ico', 'uby_ws_password'];
  for (const c of document.querySelectorAll('input[required]:not([type=hidden]), select[required]')) {
    if (!c.id || skip.includes(c.id) || c.id.startsWith('csv_export')) continue;
    const star = document.querySelector('label[for="' + c.id + '"] .req-star');
    if (!star) { bad.push(['no star', c.id]); continue; }
    const col = getComputedStyle(star).color;
    if (col !== 'rgb(180, 35, 24)') bad.push(['star colour', c.id, col]);
  }
  return bad;
}"""


def _owner(with_apartment: bool):
    username = f"o953{secrets.token_hex(3)}"
    owner = auth.create_account(f"{username}@example.test", "Old look", role="host", username=username)
    if not with_apartment:
        return username, None
    entity = db.insert("legal_entity", {"name": "Old look s.r.o.", "owner_user_id": owner, "created_at": db.utcnow()})
    apartment = db.insert("apartment", {
        "internal_name": "Old look flat", "owner_user_id": owner, "legal_entity_id": entity,
        "permalink_token": f"o9{secrets.token_hex(4)}", "active": 1, "created_at": db.utcnow(),
        "addr_obec": "Brno", "addr_house_no": "9", "addr_street": "Masarykova"})
    property_setup.start(apartment)
    return username, apartment


@pytest.mark.parametrize("width", WIDTHS)
def test_old_look_pages_at_each_width(base, width):  # noqa: F811
    failures = {}
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception as exc:
            if REQUIRE_BROWSER:
                raise
            pytest.skip(f"Chromium is not available: {exc}")
        empty_user, _ = _owner(False)       # no Stays or Properties yet: the dashboard shows the checklist card
        username, apartment = _owner(True)  # a Property with setup open: banner, wizard and operator pages
        for name in PAGES:
            user = empty_user if name == "checklist" else username
            context = browser.new_context(viewport={"width": width, "height": 900})
            context.add_cookies([{"name": auth.SESSION_COOKIE, "value": _browser_session_cookie(user), "url": base + "/"}])
            page = context.new_page()
            if name == "police":
                property_setup.mark(apartment, "property", "done")
                property_setup.mark(apartment, "calendar", "skipped")
            urls = {"checklist": "/", "apartments": "/apartments", "property": f"/apartments/{apartment}/setup/property",
                    "police": f"/apartments/{apartment}/setup/police", "entities": "/entities"}
            page.goto(f"{base}{urls[name]}?lang=en")
            page.wait_for_load_state("domcontentloaded")
            bad = page.evaluate(CHECK, name)
            if bad:
                failures[name] = bad
            SHOTS.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(SHOTS / f"{name}-{width}.png"), full_page=True)
            context.close()
        browser.close()
    assert not failures, failures
