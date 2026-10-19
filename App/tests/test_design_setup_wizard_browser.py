"""0144-b: the setup wizard renders on host_page, inside the content lane.

The owner saw the wizard's left edge under the collapsed rail (0153). The wizard
now extends host_page.html, so the shell owns its lane; this pins that, collapsed
and expanded at 1280 and 2000 px, and no sideways scroll at 390 px."""
import os
import secrets

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth, db
from tests.browser_support import chromium_launch_kwargs
from tests.test_host_geometry import _browser_session_cookie, base  # noqa: F401
from tests.test_shell_lane_browser import GEOMETRY

STEPS = ("property", "done")
TEMPLATES = ("_layout", "automation", "calendar", "done", "door_lock", "guest_link", "police", "property", "stay_fee", "try_it")


def test_wizard_templates_have_no_legacy_control():
    for name in TEMPLATES:
        text = open(f"app/templates/setup_wizard/{name}.html", encoding="utf-8").read()
        assert 'style="' not in text and 'class="btn' not in text and 'class="pill' not in text, name
    assert open("app/templates/setup_wizard/_layout.html", encoding="utf-8").read().startswith('{% extends "host_page.html" %}')


def _property():
    username = f"wiz{secrets.token_hex(3)}"
    owner = auth.create_account(f"{username}@example.test", "Wizard", role="host", username=username)
    entity = db.insert("legal_entity", {"name": "Wizard s.r.o.", "owner_user_id": owner, "created_at": db.utcnow()})
    apartment = db.insert("apartment", {"internal_name": "Wizard flat", "owner_user_id": owner, "legal_entity_id": entity,
                                        "permalink_token": f"wz{secrets.token_hex(4)}", "active": 1, "created_at": db.utcnow()})
    return username, apartment


@pytest.mark.parametrize("width", [390, 1280, 2000])
@pytest.mark.parametrize("collapsed", [False, True])
def test_wizard_sits_in_the_lane(base, width, collapsed):
    username, apartment = _property()
    cookie = _browser_session_cookie(username)
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception as exc:
            if REQUIRE_BROWSER:
                raise
            pytest.skip(f"Chromium is not available: {exc}")
        context = browser.new_context(viewport={"width": width, "height": 900})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
        if collapsed:
            context.add_init_script("try { localStorage.setItem('ubyhost-sidebar-collapsed', '1'); } catch (e) {}")
        page = context.new_page()
        for step in STEPS:
            page.goto(f"{base}/apartments/{apartment}/setup/{step}?lang=en")
            page.wait_for_selector(".ui-page[data-body-kind='form'] .setup-wizard", timeout=30000)
            assert page.locator("main h1").count() == 1, step
            assert page.locator(".ui-ph h1").is_visible(), step
            assert page.locator(".setup-wizard-exit .ui-btn").is_visible(), step
            size = page.evaluate("({sw: document.documentElement.scrollWidth, iw: innerWidth})")
            assert size["sw"] <= size["iw"], (step, width, size)
            if width < 1024:
                continue
            rail_w = 64 if collapsed else 240
            page.wait_for_function(  # app.css animates margin-left for 0.26 s
                "w => getComputedStyle(document.querySelector('.wrap.with-sidebar')).marginLeft === w + 'px'", arg=rail_w, timeout=3000)
            g = page.evaluate(GEOMETRY)
            assert g["mainLeft"] >= g["railRight"] and g["under"] == [], (step, width, collapsed, g)
        browser.close()
