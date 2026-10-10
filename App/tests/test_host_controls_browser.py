"""Browser checks for shared host interaction and control geometry."""
from __future__ import annotations

import os
import secrets
import socket
import threading
import time
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

import uvicorn
from fastapi.testclient import TestClient

from app import auth, claim, db
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def host():
    db.init_db()
    suffix = secrets.token_hex(4)
    username = f"host-controls-{suffix}"
    empty_username = f"host-controls-empty-{suffix}"
    owner_id = auth.create_account(
        f"{username}@example.test", "Controls Test", role="host", username=username
    )
    empty_owner_id = auth.create_account(
        f"{empty_username}@example.test", "Empty Controls Test", role="host", username=empty_username
    )
    entity_id = db.insert("legal_entity", {
        "name": "Controls Example s.r.o.", "seat": "Praha", "ico": "13572468",
        "contact_email": "controls@example.test", "owner_user_id": owner_id,
        "created_at": db.utcnow(),
    })
    apartment_id = db.insert("apartment", {
        "legal_entity_id": entity_id, "owner_user_id": owner_id,
        "internal_name": "Synthetic Controls Flat", "addr_obec": "Praha",
        "addr_house_no": "18", "addr_zip": "11000", "permalink_token": f"ctrl{suffix}",
        "permalink_pin": "123456", "automation_mode": "manual", "submit_after_hours": 24,
        "active": 1, "created_at": db.utcnow(),
    })
    today = claim.prague_today()
    reservation_id = db.insert("reservation", {
        "apartment_id": apartment_id, "source": "manual", "uid": f"controls-{suffix}",
        "date_from": today.isoformat(), "date_to": (today + timedelta(days=2)).isoformat(),
        "status": "active", "declared_guests": 1, "created_at": db.utcnow(),
        "updated_at": db.utcnow(),
    })
    db.insert("guest", {
        "reservation_id": reservation_id, "surname": "SYNTHETIC", "first_name": "Guest",
        "birth_date": "1990-01-01", "nationality": "USA", "doc_number": "TEST-0001",
        "res_street": "Synthetic Street 1", "res_city": "Praha", "res_country": "USA",
        "purpose": "Tourism", "stay_from": today.isoformat(),
        "stay_to": (today + timedelta(days=2)).isoformat(), "is_lead": 1,
        "entered_by": "host", "submit_state": "pending", "created_at": db.utcnow(),
        "updated_at": db.utcnow(),
    })
    client = TestClient(app)
    login = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert login.status_code == 303, login.text
    empty_client = TestClient(app)
    empty_login = login_as(empty_client, empty_username, url="/login?lang=en", follow_redirects=False)
    assert empty_login.status_code == 303, empty_login.text
    yield {
        "client": client, "empty_client": empty_client,
        "owner": owner_id, "empty_owner": empty_owner_id,
        "username": username, "empty_username": empty_username,
        "entity": entity_id, "apartment": apartment_id, "reservation": reservation_id,
    }
    for user_id in (owner_id, empty_owner_id):
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM reservation WHERE apartment_id IN (SELECT id FROM apartment WHERE owner_user_id = ?)", (user_id,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


@pytest.fixture(scope="module")
def base(host):
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        pytest.fail("the test server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def _cookie(client):
    value = client.cookies.get(auth.SESSION_COOKIE)
    assert value
    return value


def _screenshot(page, name):
    if os.environ.get("UBYHOST_CAPTURE_CONTROLS") == "1":
        folder = Path("/workspace/generated_images/host-design-application/controls")
        folder.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(folder / f"{name}.png"), full_page=True)


def test_host_interactions_geometry_copy_and_archive_controls(host, base):
    client = host["client"]
    reservation_url = f"/reservations/{host['reservation']}"
    detail = client.get(reservation_url + "?lang=en").text
    assert detail.count("Copy guest form link") >= 2
    assert "Copy guest link for this stay" not in detail
    assert 'data-confirm-message="This item will move to Archived."' in detail
    assert "stay.detail.menu.archive" not in detail
    assert 'role="menuitem">Open guest form</a>' in detail
    detail_cs = client.get(reservation_url + "?lang=cs").text
    assert "Kopírovat odkaz na formulář hosta" in detail_cs
    assert 'data-confirm-message="Tato položka se přesune do archivu."' in detail_cs
    assert ">Smazat</button>" in detail_cs

    empty_page = host["empty_client"].get("/?lang=en")
    assert empty_page.status_code == 200

    pages = [
        ("dashboard", "/"),
        ("stays", "/reservations"),
        ("stay-detail", reservation_url),
        ("properties", "/apartments"),
        ("property-detail", f"/apartments/{host['apartment']}"),
        ("operators", "/entities"),
        ("invoices", "/invoices"),
        ("stay-fees", "/stay-fees"),
        ("guest-register", "/housebook"),
        ("guest-links", "/guest-links"),
        ("automation", "/automation"),
        ("archive", "/settings/archived"),
        ("settings", "/settings"),
    ]
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        context.add_cookies([{
            "name": auth.SESSION_COOKIE, "value": _cookie(client), "url": base + "/",
        }])
        page = context.new_page()
        for width in (360, 390, 1280):
            page.set_viewport_size({"width": width, "height": 900})
            for lang in ("en", "cs"):
                for name, path in pages:
                    response = page.goto(f"{base}{path}?lang={lang}")
                    assert response and response.status == 200, f"{path} ({lang}) failed"
                    assert page.locator('link[href*="host-controls.css"]').count() == 1
                    size = page.evaluate("""() => ({
                      width: innerWidth,
                      scrollWidth: document.documentElement.scrollWidth,
                      offenders: [...document.querySelectorAll('body *')]
                        .map(el => ({el, rect: el.getBoundingClientRect()}))
                        .filter(({el, rect}) => rect.width > 0 && rect.right > innerWidth + 1 && getComputedStyle(el).position !== 'fixed')
                        .slice(0, 8)
                        .map(({el, rect}) => ({tag: el.tagName, className: String(el.className).slice(0, 100), text: (el.innerText || '').slice(0, 60), left: rect.left, right: rect.right})),
                      ancestors: (() => { let el = document.querySelector('.filter-fields'); const out = []; while (el && out.length < 7) { const r = el.getBoundingClientRect(); out.push({tag: el.tagName, className: String(el.className).slice(0, 100), left: r.left, right: r.right, width: r.width, minWidth: getComputedStyle(el).minWidth, grid: getComputedStyle(el).gridTemplateColumns}); el = el.parentElement; } return out; })(),
                    })""")
                    assert size["scrollWidth"] <= size["width"], f"{path} ({lang}, {width}px): {size}"
                    if name in ("dashboard", "stay-detail", "properties", "archive"):
                        _screenshot(page, f"{name}-{width}-{lang}")

        # The empty dashboard contains the wider onboarding welcome and its
        # progress/skip controls, the original source of the 360px overflow.
        empty_context = browser.new_context(viewport={"width": 360, "height": 900})
        empty_context.add_cookies([{
            "name": auth.SESSION_COOKIE, "value": _cookie(host["empty_client"]), "url": base + "/",
        }])
        empty_page = empty_context.new_page()
        for lang in ("en", "cs"):
            empty_page.goto(f"{base}/?lang={lang}")
            empty_size = empty_page.evaluate("""() => ({width: innerWidth, scrollWidth: document.documentElement.scrollWidth})""")
            assert empty_size["scrollWidth"] <= empty_size["width"], f"empty dashboard {lang}: {empty_size}"
            _screenshot(empty_page, f"empty-dashboard-360-{lang}")
        empty_context.close()

        # Real interactive rows/cards show the quiet hover tint and keyboard
        # focus context; static panels do not acquire a pointer cursor.
        for width, expected_height in ((360, 44), (390, 44), (1280, 42)):
            page.set_viewport_size({"width": width, "height": 900})
            page.goto(f"{base}/?lang=en")
            heights = page.locator(".action-group .btn").evaluate_all(
                "els => els.map(el => el.getBoundingClientRect().height)"
            )
            assert heights and all(height == expected_height for height in heights), (width, heights)

        page.set_viewport_size({"width": 1280, "height": 900})
        page.goto(f"{base}/apartments?lang=en")
        row = page.locator(".clickable-row").first
        before = row.locator("td").first.evaluate("el => getComputedStyle(el).backgroundColor")
        row.hover()
        after = row.locator("td").first.evaluate("el => getComputedStyle(el).backgroundColor")
        assert before != after
        row.focus()
        assert row.evaluate("el => getComputedStyle(el).outlineStyle") != "none"
        static_panel = page.locator(".panel").first
        assert static_panel.evaluate("el => getComputedStyle(el).cursor") != "pointer"

        touch_context = browser.new_context(viewport={"width": 360, "height": 800}, has_touch=True)
        touch_context.add_cookies([{
            "name": auth.SESSION_COOKIE, "value": _cookie(client), "url": base + "/",
        }])
        touch_page = touch_context.new_page()
        touch_page.goto(f"{base}/apartments?lang=en")
        touch_actions = touch_page.locator(".row-actions").first
        assert touch_actions.evaluate("el => getComputedStyle(el).opacity") == "1"
        touch_context.close()

        page.goto(f"{base}/reservations?lang=en")
        page.keyboard.press("Tab")
        focus = page.evaluate("""() => {
          const el = document.activeElement, style = getComputedStyle(el);
          return {tag: el.tagName, className: String(el.className), visible: el.matches(':focus-visible'), style: style.outlineStyle, width: style.outlineWidth};
        }""")
        assert focus["visible"] and focus["style"] == "solid" and focus["width"] == "2px", focus

        page.goto(f"{base}/settings/archived?lang=en")
        assert page.locator(".archive-type-filters").count() == 1
        assert page.locator('.archive-type-filters[role="group"]').count() == 1
        assert page.locator(".archive-type-filters .chip").count() == 5

        audit_labels = {
            "en": ("All activity", "Support sessions"),
            "cs": ("Veškerá aktivita", "Relace podpory"),
        }
        for width in (360, 390, 1280):
            page.set_viewport_size({"width": width, "height": 900})
            for lang in ("en", "cs"):
                page.goto(f"{base}/settings?lang={lang}")
                choices = page.locator(".host-audit-filter")
                assert choices.count() == 2
                assert [choices.nth(i).inner_text().strip() for i in range(2)] == list(audit_labels[lang])
                assert choices.nth(0).get_attribute("aria-current") == "page"
                assert choices.nth(1).get_attribute("aria-current") is None
                assert choices.nth(0).get_attribute("href") == "/settings#settings-audit"
                assert choices.nth(1).get_attribute("href") == "/settings?audit=support#settings-audit"
                size = page.evaluate("() => ({width:innerWidth, scrollWidth:document.documentElement.scrollWidth})")
                assert size["scrollWidth"] <= size["width"], f"Settings audit ({lang}, {width}px): {size}"
                bounds = choices.evaluate_all("els => els.map(el => el.getBoundingClientRect().toJSON())")
                assert all(0 <= item["left"] < item["right"] <= width for item in bounds), bounds
                _screenshot(page, f"settings-audit-{width}-{lang}")

                page.goto(f"{base}/settings?audit=support&lang={lang}#settings-audit")
                active = page.locator('.host-audit-filter[aria-current="page"]')
                assert active.count() == 1 and active.inner_text().strip() == audit_labels[lang][1]

        scope_label = {
            "en": "Synthetic Controls Flat",
            "cs": "Synthetic Controls Flat",
        }
        today = claim.prague_today().isoformat()
        through = (claim.prague_today() + timedelta(days=2)).isoformat()
        for width in (360, 390, 1280):
            page.set_viewport_size({"width": width, "height": 900})
            for lang in ("en", "cs"):
                # CSV has required From/Until fields and preserves the current
                # property scope in its existing query parameters.
                page.goto(f"{base}/reservations?apartment={host['apartment']}&lang={lang}")
                csv_trigger = page.locator('[data-csv-export="/reservations.csv"]')
                assert csv_trigger.get_attribute("data-csv-params") == f"apartment={host['apartment']}"
                assert csv_trigger.get_attribute("data-csv-scope-label") == scope_label[lang]
                csv_trigger.evaluate("el => el.click()")
                csv_dialog = page.locator("#csv-export-dialog")
                assert csv_dialog.evaluate("el => el.open")
                assert csv_dialog.locator("[data-csv-scope-label]").inner_text() == scope_label[lang]
                for field_id in ("csv_export_from", "csv_export_to"):
                    field = csv_dialog.locator(f"#{field_id}")
                    assert field.get_attribute("type") == "date" and field.get_attribute("required") is not None
                    assert field.evaluate("el => el.labels.length === 1 && getComputedStyle(el).width !== 'auto'")
                csv_geometry = csv_dialog.evaluate("""el => {
                  const r = el.getBoundingClientRect(), form = el.querySelector('form'), fr = form.getBoundingClientRect();
                  const buttons = [...el.querySelectorAll('.actions .btn')].map(b => b.getBoundingClientRect());
                  const fields = [...el.querySelectorAll('.grid.two .field')].map(f => f.getBoundingClientRect());
                  return {left:r.left,right:r.right,innerRight:fr.right,scrollWidth:el.scrollWidth,clientWidth:el.clientWidth,
                    buttonWidths:buttons.map(b=>b.width),buttonHeights:buttons.map(b=>b.height),fieldBounds:fields.map(f=>({left:f.left,right:f.right,top:f.top,bottom:f.bottom}))};
                }""")
                assert csv_geometry["left"] >= 0 and csv_geometry["right"] <= width, csv_geometry
                assert csv_geometry["scrollWidth"] <= csv_geometry["clientWidth"], csv_geometry
                assert len(csv_geometry["buttonWidths"]) == 2 and abs(csv_geometry["buttonWidths"][0] - csv_geometry["buttonWidths"][1]) < 1
                assert csv_geometry["buttonHeights"] == [44, 44]
                assert len(csv_geometry["fieldBounds"]) == 2
                assert all(bound["left"] >= csv_geometry["left"] and bound["right"] <= csv_geometry["right"] for bound in csv_geometry["fieldBounds"]), csv_geometry
                if width == 1280:
                    assert csv_geometry["fieldBounds"][0]["top"] == csv_geometry["fieldBounds"][1]["top"], csv_geometry
                _screenshot(page, f"csv-export-{width}-{lang}")
                if width == 1280 and lang == "en":
                    requested_urls = []

                    def intercept_csv(route):
                        requested_urls.append(route.request.url)
                        route.abort()

                    page.route("**/reservations.csv*", intercept_csv)
                    csv_dialog.locator("#csv_export_from").fill(today)
                    csv_dialog.locator("#csv_export_to").fill(through)
                    with page.expect_request(lambda request: "/reservations.csv?" in request.url) as csv_request:
                        csv_dialog.locator("button[type=submit]").click()
                    csv_url = urlparse(csv_request.value.url)
                    assert csv_url.path == "/reservations.csv"
                    assert parse_qs(csv_url.query) == {
                        "from": [today], "to": [through], "apartment": [str(host["apartment"])],
                    }
                    assert requested_urls == [csv_request.value.url]
                    page.unroute("**/reservations.csv*", intercept_csv)
                else:
                    csv_dialog.locator("[data-csv-cancel]").click()

                page.goto(f"{base}/reservations?lang={lang}")
                all_scope_trigger = page.locator('[data-csv-export="/reservations.csv"]')
                all_scope_trigger.evaluate("el => el.click()")
                all_scope_label = "All properties" if lang == "en" else "Všechna ubytování"
                assert page.locator("#csv-export-dialog [data-csv-scope-label]").inner_text() == all_scope_label
                page.locator("#csv-export-dialog [data-csv-cancel]").click()

                # The inspection bundle keeps its native, optional dates and
                # its current property/date scope in the dialog.
                page.goto(f"{base}/housebook?apartment={host['apartment']}&from={today}&to={through}&lang={lang}")
                pdf_trigger = page.locator("[data-housebook-pdf-export]").first
                pdf_trigger.evaluate("el => el.click()")
                pdf_dialog = page.locator("#housebook-pdf-dialog")
                assert pdf_dialog.evaluate("el => el.open")
                apartment = pdf_dialog.locator("#pdf_export_apartment")
                assert apartment.input_value() == str(host["apartment"])
                assert pdf_dialog.locator("#pdf_export_from").input_value() == today
                assert pdf_dialog.locator("#pdf_export_to").input_value() == through
                assert pdf_dialog.locator("#pdf_export_from").get_attribute("type") == "date"
                assert pdf_dialog.locator("#pdf_export_from").get_attribute("required") is None
                assert pdf_dialog.locator("#pdf_export_to").get_attribute("required") is None
                assert "100" in pdf_dialog.locator(".housebook-pdf-warn").inner_text()
                pdf_geometry = pdf_dialog.evaluate("""el => {
                  const r = el.getBoundingClientRect(), form = el.querySelector('form').getBoundingClientRect();
                  const controls = [...el.querySelectorAll('select,input[type=date]')].map(c=>c.getBoundingClientRect());
                  const buttons = [...el.querySelectorAll('.actions .btn')].map(b=>b.getBoundingClientRect());
                  return {left:r.left,right:r.right,formLeft:form.left,formRight:form.right,scrollWidth:el.scrollWidth,clientWidth:el.clientWidth,
                    controls:controls.map(c=>({left:c.left,right:c.right,top:c.top,bottom:c.bottom})),buttonWidths:buttons.map(b=>b.width),buttonHeights:buttons.map(b=>b.height)};
                }""")
                assert pdf_geometry["left"] >= 0 and pdf_geometry["right"] <= width, pdf_geometry
                assert pdf_geometry["scrollWidth"] <= pdf_geometry["clientWidth"], pdf_geometry
                assert len(pdf_geometry["controls"]) == 3
                assert all(control["left"] >= pdf_geometry["left"] and control["right"] <= pdf_geometry["right"] for control in pdf_geometry["controls"]), pdf_geometry
                assert pdf_geometry["buttonWidths"][0] == pdf_geometry["buttonWidths"][1]
                assert pdf_geometry["buttonHeights"] == [44, 44]
                if width == 1280:
                    pdf_field_tops = pdf_dialog.locator(".grid.two .field").evaluate_all(
                        "els => els.map(el => el.getBoundingClientRect().top)"
                    )
                    assert pdf_field_tops[0] == pdf_field_tops[1], pdf_field_tops
                _screenshot(page, f"inspection-export-{width}-{lang}")
                pdf_dialog.locator("[data-housebook-pdf-cancel]").click()

        archive_copy = {
            "en": ("This item will move to Archived.", "Delete", "Generate a new guest link and PIN? The current link and PIN stop working.", "Confirm"),
            "cs": ("Tato položka se přesune do archivu.", "Smazat", "Vygenerovat nový odkaz a PIN? Stávající odkaz a PIN přestanou fungovat.", "Potvrdit"),
        }
        page.set_viewport_size({"width": 1280, "height": 900})
        for lang, expected in archive_copy.items():
            page.goto(f"{base}{reservation_url}?lang={lang}")
            archive_button = page.locator('form[data-confirm][action$="/archive"] button[type="submit"]').first
            archive_button.evaluate("el => el.click()")
            confirmation = page.locator("#confirm-dialog")
            assert confirmation.evaluate("el => el.open")
            assert confirmation.locator("#confirm-body").inner_text() == expected[0]
            assert confirmation.locator("[data-confirm-proceed]").inner_text() == expected[1]
            confirmation.locator("[data-confirm-cancel]").click()

            page.goto(f"{base}/apartments/{host['apartment']}?lang={lang}")
            regular_button = page.locator('button[data-confirm][formaction$="/regenerate-link"]')
            regular_button.evaluate("el => el.click()")
            assert confirmation.evaluate("el => el.open")
            assert confirmation.locator("#confirm-body").inner_text() == expected[2]
            assert confirmation.locator("[data-confirm-proceed]").inner_text() == expected[3]
            confirmation.locator("[data-confirm-cancel]").click()
        browser.close()
