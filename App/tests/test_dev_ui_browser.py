"""Screenshots and the coral budget on /dev/ui (MASTER 4.1, 11.2).

Runs in the browser CI job (UBYHOST_REQUIRE_BROWSER=1) and is skipped only
where Chromium is missing. Shots land in UBYHOST_SHOTS_DIR when set.
"""
import io
import os
import secrets
from pathlib import Path

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from PIL import Image

from app import auth
from tests.browser_support import chromium_launch_kwargs
from tests.test_host_geometry import _browser_session_cookie, base  # noqa: F401  (fixture reuse)

CORAL = ((173, 73, 66), (200, 90, 82))
EMPTY = ((247, 247, 245), (255, 255, 255))
BUDGET = {390: (6.0, 50.0), 1280: (3.0, 55.0)}


def _near(p, c, d):
    return (p[0] - c[0]) ** 2 + (p[1] - c[1]) ** 2 + (p[2] - c[2]) ** 2 <= d * d


def _shares(png_bytes):
    im = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    px = list(im.getdata())
    coral = sum(1 for p in px if any(_near(p, c, 40) for c in CORAL))
    empty = sum(1 for p in px if any(_near(p, c, 8) for c in EMPTY))
    return 100.0 * coral / len(px), 100.0 * empty / len(px)


@pytest.mark.parametrize("width", [390, 1280])
def test_catalog_page_fits_the_viewport_and_the_coral_budget(base, width):
    username = f"devuiadmin{secrets.token_hex(3)}"
    auth.create_account(f"{username}@example.test", "Catalog", role="admin", username=username)
    session = _browser_session_cookie(username)
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception as exc:
            if REQUIRE_BROWSER:
                raise
            pytest.skip(f"Chromium is not available: {exc}")
        context = browser.new_context(viewport={"width": width, "height": 900 if width == 1280 else 844})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": session, "url": base + "/"}])
        page = context.new_page()
        page.goto(base + "/dev/ui?lang=en")
        page.wait_for_selector("#skeletons", timeout=30000)
        assert page.evaluate("document.documentElement.scrollWidth") <= width, "horizontal overflow"
        if width == 390:
            short = page.evaluate("""() => [...document.querySelectorAll('.ui-btn, .ui-chip, .ui-tab')]
                .filter(el => el.offsetParent !== null)
                .map(el => el.getBoundingClientRect().height).filter(h => h < 43.5)""")
            assert short == [], f"targets under 44 px at 390: {short}"
        lane = page.evaluate("document.querySelector('.ui-page').getBoundingClientRect().width")
        skel = page.evaluate("document.querySelector('[data-skeleton-kind=\"list\"]').getBoundingClientRect().width")
        assert abs(lane - skel) <= 8, "the skeleton must span the lane"
        shot = page.screenshot(full_page=False)
        shots = os.environ.get("UBYHOST_SHOTS_DIR")
        if shots:
            Path(shots).mkdir(parents=True, exist_ok=True)
            (Path(shots) / f"dev-ui-{width}.png").write_bytes(shot)
        coral, empty = _shares(shot)
        max_coral, min_empty = BUDGET[width]
        assert coral <= max_coral, f"coral {coral:.2f}% over {max_coral}% at {width}"
        assert empty >= min_empty, f"empty surface {empty:.1f}% under {min_empty}% at {width}"
        context.close()
        browser.close()
