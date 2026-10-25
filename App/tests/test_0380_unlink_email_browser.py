"""0380: the stay's "Unlink this e-mail" button is visible, explained by a "?" tip, and frees the stay."""
from __future__ import annotations

import os
from pathlib import Path

from app import auth, claim, db, host_i18n
from tests.test_host_stay_actions_browser import (  # noqa: F401 (fixtures)
    REQUIRE_BROWSER,
    _browser,
    stay_actions_base,
    stay_actions_host,
    sync_api,
)

EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0380"
FLASH_EN = "E-mail unlinked. The next person who opens the guest form can take this stay."


def _claim_ready_stay(stay_actions_host):
    rid = stay_actions_host["ids"]["ready"]
    claim.ensure_row(rid)
    db.execute(
        "UPDATE reservation_claim SET state = ?, email = ?, email_masked = ?, claimed_at = ? WHERE reservation_id = ?",
        (claim.CLAIMED, "guest@example.test", "g***@example.test", db.utcnow(), rid),
    )
    return rid


def _overlaps(a, b):
    return not (a["x"] + a["width"] <= b["x"] or b["x"] + b["width"] <= a["x"]
                or a["y"] + a["height"] <= b["y"] or b["y"] + b["height"] <= a["y"])


def test_unlink_button_is_visible_and_explained(stay_actions_host, stay_actions_base):
    cookie = stay_actions_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    rid = _claim_ready_stay(stay_actions_host)
    capture = os.environ.get("UBYHOST_CAPTURE_0380") == "1"
    if capture:
        EVIDENCE.mkdir(parents=True, exist_ok=True)
    with sync_api.sync_playwright() as playwright:
        browser = _browser(playwright)
        for lang in ("en", "cs", "vi"):
            for width, collapsed in ((390, False), (1280, False), (1280, True), (2000, False), (2000, True)):
                context = browser.new_context(viewport={"width": width, "height": 900})
                context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": stay_actions_base + "/"}])
                context.add_init_script(
                    "try { localStorage.setItem('ubyhost-sidebar-collapsed', '%s'); } catch (e) {}"
                    % ("1" if collapsed else "0")
                )
                page = context.new_page()
                page.goto(f"{stay_actions_base}/reservations/{rid}?lang={lang}")
                page.wait_for_load_state("networkidle")
                label = f"{lang} {width} {collapsed}"
                button = page.locator("[data-stay-claim] [data-release-claim]")
                assert button.is_visible(), label
                assert button.inner_text().strip() == host_i18n.translate(lang, "stay.claim.release"), label
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), label
                assert not _overlaps(button.bounding_box(), page.locator("[data-stay-claim] p").bounding_box()), label
                menus = page.locator("[role=menu]").evaluate_all("els => els.map(e => e.innerHTML)")
                assert not any("release-claim" in html for html in menus), label
                tip_btn = page.locator("[data-stay-claim] .help-tip-btn")
                tip_btn.click()
                assert tip_btn.get_attribute("aria-expanded") == "true", label
                tip = page.locator("#release-claim-help")
                tip.wait_for(state="visible")
                box = tip.bounding_box()
                inner = page.evaluate("window.innerWidth")
                assert box["x"] >= 0 and box["x"] + box["width"] <= inner, (label, box)
                if capture:
                    page.screenshot(
                        path=str(EVIDENCE / f"{lang}-{width}{'c' if collapsed else ''}.png"), full_page=True
                    )
                context.close()


def test_unlink_asks_then_frees_the_stay(stay_actions_host, stay_actions_base):
    cookie = stay_actions_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    rid = _claim_ready_stay(stay_actions_host)
    with sync_api.sync_playwright() as playwright:
        browser = _browser(playwright)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": stay_actions_base + "/"}])
        page = context.new_page()
        page.goto(f"{stay_actions_base}/reservations/{rid}?lang=en")
        page.wait_for_load_state("networkidle")
        page.locator("[data-stay-claim] [data-release-claim]").click()
        proceed = page.locator("[data-confirm-proceed]")
        proceed.wait_for(state="visible")
        proceed.click()
        page.wait_for_load_state("networkidle")
        assert FLASH_EN in page.locator("body").inner_text()
        assert page.locator("[data-release-claim]").count() == 0
        row = db.query_one("SELECT state FROM reservation_claim WHERE reservation_id = ?", (rid,))
        assert row is not None and row["state"] == claim.UNCLAIMED
        context.close()
