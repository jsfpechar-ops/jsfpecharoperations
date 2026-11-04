"""0912: stay detail header and sections: one action row, one Save, one all-reported line, first-name-first guests."""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from tests.browser_support import chromium_launch_kwargs
from tests.test_host_stay_actions_browser import stay_actions_base, stay_actions_host  # noqa: F401
from tests.test_status_colours import host  # noqa: F401

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

LINT = (Path(__file__).parent / "layout_lint.js").read_text()
WIDTHS = (390, 768, 1280)
# Header states from the stay-actions fixture: a reported stay, a failed (overdue) stay, a stay with no guests.
STATES = {"reported": "reported", "overdue": "failed", "no-guests": "waiting"}


def _csrf(page: str) -> dict:
    match = re.search(r'name="_csrf" value="([^"]+)"', page)
    return {"_csrf": match.group(1)} if match else {}


def _settings(page: str) -> str:
    start = page.index('id="stay-quick-edit"')
    return page[start:page.index("</details>", start)]


def test_the_one_save_stores_summary_and_expected_guests(host):  # noqa: F811
    client, _, reservation_id = host
    page = client.get(f"/reservations/{reservation_id}?lang=en").text
    data = {"status": "active", "host_note": "", "guest_email": "",
            "summary": "Balcony stay", "expected_guests_override": "2", **_csrf(page)}
    response = client.post(f"/reservations/{reservation_id}", data=data, follow_redirects=False)
    assert response.status_code in (302, 303), response.text
    after = client.get(f"/reservations/{reservation_id}?lang=en").text
    assert 'value="Balcony stay"' in after
    assert 'value="2"' in after


def test_the_stay_page_has_one_save_in_the_settings_panel(host):  # noqa: F811
    client, _, reservation_id = host
    page = client.get(f"/reservations/{reservation_id}?lang=en").text
    assert f'action="/reservations/{reservation_id}/quick-edit"' not in page
    settings = _settings(page)
    assert settings.count('type="submit"') == 1, settings[:400]
    assert f'action="/reservations/{reservation_id}"' in settings
    assert 'name="summary"' in settings and 'name="expected_guests_override"' in settings


def test_all_reported_sentence_shows_once_on_a_reported_stay(stay_actions_host):
    client = stay_actions_host["client"]
    page = client.get(f"/reservations/{stay_actions_host['ids']['reported']}?lang=en").text
    assert page.count("All guests are reported") == 1


def test_guest_rows_read_first_name_first(stay_actions_host):
    client = stay_actions_host["client"]
    page = client.get(f"/reservations/{stay_actions_host['ids']['reported']}?lang=en").text
    assert "REPORTED SAMPLE" in page
    assert "SAMPLE REPORTED" not in page


def test_the_resend_menu_item_carries_the_resend_hook(stay_actions_host):
    client = stay_actions_host["client"]
    page = client.get(f"/reservations/{stay_actions_host['ids']['reported']}?lang=en").text
    if "/resend-claim" in page:
        assert "data-resend-claim" in page


@pytest.mark.parametrize("state", list(STATES))
def test_stay_header_has_one_action_row_at_every_width(stay_actions_host, stay_actions_base, state, tmp_path):  # noqa: F811
    client = stay_actions_host["client"]
    stay_id = stay_actions_host["ids"][STATES[state]]
    shots = Path(os.environ.get("UBYHOST_SHOTS_DIR", tmp_path)) / "0912"
    shots.mkdir(parents=True, exist_ok=True)
    cookies = [{"name": k, "value": v, "url": stay_actions_base} for k, v in client.cookies.items()]
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception:
            if REQUIRE_BROWSER:
                raise
            pytest.skip("Chromium is required for the stay header check")
        context = browser.new_context()
        context.add_cookies(cookies)
        for width in WIDTHS:
            page = context.new_page()
            page.set_viewport_size({"width": width, "height": 900})
            page.goto(f"{stay_actions_base}/reservations/{stay_id}?lang=en")
            page.wait_for_load_state("networkidle")
            found = [item for item in page.evaluate(LINT) if item[0] == "action-row-orphan"]
            page.screenshot(path=str(shots / f"{state}-{width}.png"))
            page.close()
            assert not found, f"{state} at {width}px: {found}"
        browser.close()
