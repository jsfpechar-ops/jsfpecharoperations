"""Brief 1029: the "applies from" date next to the stay-fee rate (property editor only)."""
from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path

from app import claim, db, stay_fee_rate
from tests import test_property_form_save as form_save
from tests.test_property_form_save import host  # noqa: F401  (pytest fixture)
from tests.browser_support import chromium_launch_kwargs, settle_motion
from tests.test_0710_v2_mockup_match_browser import _placeholders, base, dashboard_host, dashboard_rich_host  # noqa: F401
from tests.test_0830_airbnb_pages_browser import seeded  # noqa: F401
from tests.test_stay_fee_rate_dates_1028 import _rates, _save_rate

SHOTS_1029 = os.environ.get("UBYHOST_SHOTS_1029")
WIDTHS_1029 = (390, 768, 1280)
DATE_INPUT = r'<input type="date" id="stay_fee_rate_from"[^>]*>'


def _editor_html(client, apartment_id: int) -> str:
    response = client.get(f"/apartments/{apartment_id}")
    assert response.status_code == 200, response.text[:300]
    return response.text


def test_editor_shows_the_date_for_a_rate_above_zero(host, monkeypatch):  # noqa: F811
    monkeypatch.setattr(claim, "prague_today", lambda: date(2026, 3, 12))
    apartment_id = form_save._apartment()["id"]
    _save_rate(host, apartment_id, 30)
    html = _editor_html(host, apartment_id)
    match = re.search(DATE_INPUT, html)
    assert match, "no stay_fee_rate_from date input in the editor"
    assert 'min="2026-03-12"' in match.group(0)
    assert 'value="2026-03-12"' in match.group(0)
    assert 'name="stay_fee_rate_from"' in match.group(0)


def test_editor_hides_the_date_for_rate_zero(host, monkeypatch):  # noqa: F811
    monkeypatch.setattr(claim, "prague_today", lambda: date(2026, 3, 12))
    apartment_id = form_save._apartment()["id"]
    _save_rate(host, apartment_id, 0)
    assert 'id="stay_fee_rate_from"' not in _editor_html(host, apartment_id)


def test_wizard_has_no_date_field(host, monkeypatch):  # noqa: F811
    monkeypatch.setattr(claim, "prague_today", lambda: date(2026, 3, 12))
    apartment_id = form_save._apartment()["id"]
    _save_rate(host, apartment_id, 30)
    response = host.get(f"/apartments/{apartment_id}/setup/stay_fee")
    assert response.status_code == 200, response.text[:300]
    assert 'id="stay_fee_rate_from"' not in response.text


def test_future_date_stores_the_row_and_older_nights_keep_the_old_rate(host, monkeypatch):  # noqa: F811
    monkeypatch.setattr(claim, "prague_today", lambda: date(2026, 3, 12))
    apartment_id = form_save._apartment()["id"]
    _save_rate(host, apartment_id, 30)
    changed = _save_rate(host, apartment_id, 45, stay_fee_rate_from="2026-03-20")
    assert _rates(apartment_id) == [("2000-01-01", 30), ("2026-03-20", 45)]
    schedule = stay_fee_rate.schedule_for(changed)
    assert stay_fee_rate.rate_on(schedule, date(2026, 3, 19)) == 30
    assert stay_fee_rate.rate_on(schedule, date(2026, 3, 20)) == 45


def test_1029_date_field_shows_at_each_width(base, dashboard_rich_host, seeded):  # noqa: F811
    from playwright import sync_api

    from app import auth

    cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    apartment_id = _placeholders(dashboard_rich_host)["first_property"]
    db.execute("UPDATE apartment SET stay_fee_rate_czk = ? WHERE id = ?", (30, apartment_id))
    problems = []
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        for width in WIDTHS_1029:
            context = browser.new_context(viewport={"width": width, "height": 1000}, reduced_motion="reduce")
            context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
            page = context.new_page()
            page.goto(f"{base}/apartments/{apartment_id}?view=settings&lang=en")
            page.wait_for_load_state("networkidle")
            settle_motion(page)
            page.evaluate("() => { const d = document.getElementById('sec-fee'); if (d) d.open = true; }")
            field = page.locator("#stay_fee_rate_from")
            if field.count() == 0:
                problems.append(f"{width}: no date field in the property editor")
            else:
                try:
                    # The fee section opens with a height transition; wait for it instead of checking at once.
                    field.first.wait_for(state="visible", timeout=5000)
                except sync_api.TimeoutError:
                    problems.append(f"{width}: date field not visible")
                if page.evaluate("document.documentElement.scrollWidth > window.innerWidth"):
                    problems.append(f"{width}: horizontal scroll")
                if SHOTS_1029:
                    section = page.locator("#sec-fee")
                    Path(SHOTS_1029).mkdir(parents=True, exist_ok=True)
                    section.first.screenshot(path=str(Path(SHOTS_1029) / f"stay-fee-rate-from-{width}.png"))
            context.close()
        browser.close()
    assert not problems, problems
