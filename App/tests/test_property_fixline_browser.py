"""1030: after a failed save the wide editor's fix line names every field to fix, by its clean label."""
from __future__ import annotations

from tests.property_host_fixture import host  # noqa: F401
from tests.test_property_navigation_browser import _context, base, chromium_launch_kwargs, sync_api  # noqa: F401


def test_a_failed_save_names_every_blank_required_field(host, base):  # noqa: F811
    url = f"{base}/apartments/{host['apartment']}?view=settings&lang=en"
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        page = _context(browser, base, host).new_page()
        page.goto(url)
        page.evaluate("""() => {
          for (const n of ['addr_house_no', 'addr_zip']) document.querySelector('[name=' + n + ']').value = '';
          const f = document.getElementById('property-settings-form'); f.noValidate = true; f.requestSubmit();
        }""")
        page.wait_for_selector("[data-save-summary][data-first-error]", state="attached")
        page.wait_for_function("() => !document.querySelector('[data-prop-fixline]').hidden")
        line = page.locator("[data-prop-fixline]")
        links = line.locator("a")
        names = links.all_inner_texts()
        hrefs = [links.nth(i).get_attribute("href") for i in range(links.count())]
        assert any(n.startswith("House number") for n in names), names
        assert any(n.startswith("Postcode") for n in names), names
        assert "#addr_house_no" in hrefs and "#addr_zip" in hrefs, hrefs
        assert not any("*" in n or "?" in n for n in names), names
        assert line.inner_text().startswith(f"Fix {len(names)} fields:"), line.inner_text()
        links.nth(hrefs.index("#addr_zip")).click()
        assert page.evaluate("document.activeElement.id") == "addr_zip"
        browser.close()


def test_a_native_invalid_save_shows_the_fix_line_at_390(host, base):  # noqa: F811
    url = f"{base}/apartments/{host['apartment']}?view=settings&lang=en"
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        page = _context(browser, base, host).new_page()
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(url)
        page.evaluate("""() => {
          for (const n of ['addr_house_no', 'addr_zip']) document.querySelector('[name=' + n + ']').value = '';
        }""")
        page.locator("#property-settings-form button[type=submit]:visible").first.click()
        page.wait_for_function("() => !document.querySelector('[data-prop-fixline]').hidden")
        line = page.locator("[data-prop-fixline]")
        links = line.locator("a")
        names = links.all_inner_texts()
        assert any(n.startswith("House number") for n in names), names
        assert any(n.startswith("Postcode") for n in names), names
        browser.close()
