"""0282: the stay-fee signature is locked until Edit; Edit opens a dialog to draw or type it."""
from __future__ import annotations

import os
import secrets

from fastapi.testclient import TestClient

from app import auth, db, demo
from app.main import app
from tests.conftest import login_as
from tests.test_property_navigation_browser import base, chromium_launch_kwargs, sync_api  # noqa: F401

PHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
SIZES = [("390", 390, 844, PHONE, True), ("1280", 1280, 900, None, False)]
TYPED_NAME = "Nguyễn Thu Phương"
FONT_CHECK = "() => document.fonts.check('48px \"UbyHost Signature\"')"


def _owner_session():
    db.init_db()
    user = f"sig0282-{secrets.token_hex(3)}"
    owner = auth.create_account(f"{user}@example.test", "Signature Host", role="host", username=user)
    demo.seed(owner)
    flat = db.query("SELECT id FROM apartment WHERE owner_user_id = ? ORDER BY id", (owner,))[0]["id"]
    client = TestClient(app)
    login_as(client, user, url="/login?lang=en")
    return flat, client.cookies.get(auth.SESSION_COOKIE)


def test_signature_stays_locked_until_edit_and_saves_draw_or_type(base):
    shots = os.environ.get("UBYHOST_0282_SHOTS")
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        for tag, width, height, agent, touch in SIZES:
            flat, session = _owner_session()
            path = f"/apartments/{flat}?view=settings&section=reporting&lang=en"
            options = {"viewport": {"width": width, "height": height}, "has_touch": touch, "is_mobile": touch}
            if agent:
                options["user_agent"] = agent
            context = browser.new_context(**options)
            context.add_cookies([{"name": auth.SESSION_COOKIE, "value": session, "url": base + "/"}])
            page = context.new_page()
            page.goto(base + path)
            block = page.locator("[data-host-signature]")
            dialog = page.locator("[data-signature-dialog]")
            hidden = block.locator('input[name="signature_drawn"]')
            open_button = block.locator("[data-signature-open]")
            # Locked: no canvas is visible, and the Edit button is.
            assert block.locator("canvas:visible").count() == 0, tag
            assert open_button.is_visible(), tag
            open_button.click()
            page.wait_for_timeout(200)
            assert dialog.get_attribute("open") is not None, tag
            canvas_box = dialog.locator('[data-signature-panel="draw"] canvas').bounding_box()
            assert canvas_box["width"] >= (340 if touch else 600), (tag, canvas_box)
            if touch:
                assert canvas_box["height"] >= 160, (tag, canvas_box)
            dialog.locator('[data-signature-mode="type"]').click()
            type_border = dialog.locator('[data-signature-mode="type"]').evaluate("e => getComputedStyle(e).borderBottomColor")
            draw_border = dialog.locator('[data-signature-mode="draw"]').evaluate("e => getComputedStyle(e).borderBottomColor")
            assert type_border != draw_border, (tag, type_border, draw_border)
            dialog.locator("[data-signature-typed]").fill(TYPED_NAME)
            page.wait_for_timeout(200)
            if shots:
                os.makedirs(shots, exist_ok=True)
                page.screenshot(path=os.path.join(shots, f"dialog-type-{tag}.png"))
            dialog.locator("[data-signature-use]").click()
            page.wait_for_timeout(200)
            assert dialog.get_attribute("open") is None, tag
            assert hidden.input_value().startswith("data:image/png;base64,"), tag
            assert block.locator("[data-signature-preview]").is_visible(), tag
            assert page.evaluate(FONT_CHECK), tag
            typed_value = hidden.input_value()

            open_button.click()
            page.wait_for_timeout(200)
            dialog.locator('[data-signature-mode="draw"]').click()
            box = dialog.locator('[data-signature-panel="draw"] canvas').bounding_box()
            x, y = box["x"] + box["width"] * 0.2, box["y"] + box["height"] * 0.5
            page.mouse.move(x, y)
            page.mouse.down()
            for step in range(1, 6):
                page.mouse.move(x + step * box["width"] * 0.12, y - step * 4)
            page.mouse.up()
            dialog.locator("[data-signature-use]").click()
            page.wait_for_timeout(200)
            assert hidden.input_value() != typed_value, tag
            assert hidden.input_value().startswith("data:image/png;base64,"), tag

            with page.expect_navigation():
                block.evaluate("b => b.closest('form').requestSubmit()")
            page.goto(base + path)
            src = page.locator("[data-signature-preview]").get_attribute("src")
            assert src and src.startswith("data:image/"), tag
            context.close()
        browser.close()
