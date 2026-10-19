"""0107: small primary buttons keep their own readable text colour (Stay fee list)."""
from __future__ import annotations

import os
import re
import socket
import threading
import time
from pathlib import Path

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

import uvicorn
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as

USERNAME = "button-contrast-host"
WIDTHS = (1280, 360)
MIN_RATIO = 4.5
SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "0107-screenshots"
CAPTURE = os.environ.get("UBYHOST_CAPTURE_0107") == "1"

BUTTONS = """() => [...document.querySelectorAll('a.ui-btn.ui-btn-compact')].map(el => {
  const cs = getComputedStyle(el);
  return {text: el.textContent.trim(), color: cs.color, background: cs.backgroundColor};
})"""

RGB = re.compile(r"rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:[,/\s]+([\d.]+%?))?\s*\)")


def parse_rgb(value: str) -> tuple[list[float], float]:
    match = RGB.fullmatch(value.strip())
    assert match, f"unparsed colour {value!r}"
    channels = [float(match.group(index)) for index in (1, 2, 3)]
    alpha = match.group(4)
    if alpha is None:
        return channels, 1.0
    if alpha.endswith("%"):
        return channels, float(alpha[:-1]) / 100
    return channels, float(alpha)


def relative_luminance(channels: list[float]) -> float:
    def linear(value: float) -> float:
        srgb = value / 255
        return srgb / 12.92 if srgb <= 0.03928 else ((srgb + 0.055) / 1.055) ** 2.4

    red, green, blue = (linear(value) for value in channels)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(foreground: list[float], background: list[float]) -> float:
    lighter, darker = sorted(
        (relative_luminance(foreground), relative_luminance(background)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)


def _cleanup() -> None:
    user = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    if not user:
        return
    owner_id = user["id"]
    db.execute("DELETE FROM settings WHERE key = ?", (f"onboarding_dismissed_{owner_id}",))
    db.execute("DELETE FROM alert WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


@pytest.fixture(scope="module")
def fee_host():
    """A host with two properties that have no stay fee rate yet ("Not set up")."""
    db.init_db()
    _cleanup()
    owner_id = auth.create_account(
        f"{USERNAME}@example.test", "Button Contrast QA", role="host", username=USERNAME
    )
    entity_id = db.insert("legal_entity", {
        "name": "Button Contrast QA s.r.o.", "owner_user_id": owner_id, "created_at": db.utcnow(),
    })
    for name in ("Contrast Flat A", "Contrast Flat B"):
        db.insert("apartment", {
            "internal_name": name, "owner_user_id": owner_id, "legal_entity_id": entity_id,
            "active": 1, "created_at": db.utcnow(),
        })
    client = TestClient(app)
    login = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert login.status_code == 303, login.text
    try:
        yield {"client": client, "owner_id": owner_id}
    finally:
        _cleanup()


@pytest.fixture(scope="module")
def base(fee_host):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        pytest.fail("the button contrast test server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def _launch(playwright):
    try:
        return playwright.chromium.launch(**chromium_launch_kwargs())
    except Exception:
        if REQUIRE_BROWSER:
            raise
        pytest.skip("Chromium is required for button contrast coverage")


def test_small_primary_buttons_on_stay_fees_meet_contrast(fee_host, base):
    cookie = fee_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    if CAPTURE:
        SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        try:
            for width in WIDTHS:
                label = f"stay-fees/{width}"
                context = browser.new_context(viewport={"width": width, "height": 900})
                context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
                page = context.new_page()
                page.goto(f"{base}/stay-fees?lang=en")
                page.wait_for_load_state("networkidle")
                later = page.locator("#security-prompt [data-security-prompt-later]")
                if later.is_visible():
                    later.click()
                buttons = page.evaluate(BUTTONS)
                assert len(buttons) >= 2, (label, buttons)
                for button in buttons:
                    foreground, _ = parse_rgb(button["color"])
                    background, alpha = parse_rgb(button["background"])
                    assert alpha == 1, (label, button)
                    ratio = contrast_ratio(foreground, background)
                    assert ratio >= MIN_RATIO, (label, button, round(ratio, 2))
                if CAPTURE:
                    page.evaluate("window.scrollTo(0, 0)")
                    page.screenshot(path=str(SHOTS / f"stay-fees-{width}.png"), full_page=True)
                context.close()
        finally:
            browser.close()
