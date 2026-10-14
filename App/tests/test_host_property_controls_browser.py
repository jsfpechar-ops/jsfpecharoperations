"""Browser coverage for the approved property and operator controls."""
from __future__ import annotations

import os
import secrets
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth, db, property_setup
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as


@pytest.fixture(scope="module")
def host():
    db.init_db()
    username = f"property-controls-{secrets.token_hex(4)}"
    owner_id = auth.create_account(
        f"{username}@example.test", "Property Controls", role="host", username=username
    )
    linked_id = db.insert("legal_entity", {
        "name": "Linked Operator",
        "seat": "Praha",
        "ico": "12345678",
        "contact_email": "linked@example.test",
        "owner_user_id": owner_id,
        "created_at": db.utcnow(),
    })
    free_id = db.insert("legal_entity", {
        "name": "Free Operator",
        "seat": "Brno",
        "ico": "87654321",
        "contact_email": "free@example.test",
        "owner_user_id": owner_id,
        "created_at": db.utcnow(),
    })
    apartment_id = db.insert("apartment", {
        "internal_name": "Sample Property",
        "owner_user_id": owner_id,
        "legal_entity_id": linked_id,
        "addr_obec": "Praha",
        "addr_house_no": "10",
        "addr_zip": "11000",
        "permalink_token": f"controls{secrets.token_hex(4)}",
        "permalink_pin": "123456",
        "active": 1,
        "created_at": db.utcnow(),
    })
    property_setup.start(apartment_id)
    property_setup.finish(apartment_id)
    client = TestClient(app)
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    yield {"client": client, "username": username, "owner": owner_id,
           "linked": linked_id, "free": free_id, "apartment": apartment_id}
    db.execute("DELETE FROM alert WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


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


def _session_cookie(host):
    cookie = host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    return cookie


def _capture_review(page, name):
    if os.environ.get("UBYHOST_CAPTURE_PROPERTY_CONTROLS") == "1":
        target = Path("/workspace/generated_images/host-design-application/properties")
        target.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(target / f"{name}.png"), full_page=True)


def test_property_and_operator_controls_render_and_work_in_browser(host, base):
    client = host["client"]
    entities_page = client.get("/entities?lang=en").text
    assert 'action="/entities/' + str(host["linked"]) + '/archive"' not in entities_page
    assert "entity_has_properties" not in entities_page
    linked_post = client.post(f"/entities/{host['linked']}/archive", follow_redirects=False)
    assert linked_post.status_code == 303
    assert db.query_one("SELECT archived_at FROM legal_entity WHERE id = ?", (host["linked"],))["archived_at"] is None

    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = browser.new_context(viewport={"width": 1280, "height": 1000}, has_touch=True)
        context.add_cookies([{
            "name": auth.SESSION_COOKIE,
            "value": _session_cookie(host),
            "url": base + "/",
        }])
        page = context.new_page()
        requests = []
        page.on("request", lambda request: requests.append(request) if request.method == "POST" else None)

        for lang in ("en", "cs"):
            page.goto(f"{base}/apartments/new?lang={lang}")
            _capture_review(page, f"address-1280-{lang}")
            assert page.locator(".req-report").count() == 0
            assert page.locator("#addr_street").get_attribute("name") == "addr_street"
            assert page.locator("#addr_house_no").get_attribute("name") == "addr_house_no"
            assert page.locator('input[name="address_line"]').count() == 0
            assert page.locator(".property-address-police").count() == 0
            # 0092: the guest message is set on the property page; create stores the default.
            assert page.locator("#guest_message").count() == 0
            labels = page.locator("#address .property-address-grid").first.locator("label")
            assert labels.count() == 3
            first_row = page.locator("#address .property-address-grid").first
            label_input_tops = first_row.evaluate("""(row) => [...row.querySelectorAll('.field')].map((field) => {
              const input = field.querySelector('input');
              const label = field.querySelector('label');
              return { input: Math.round(input.getBoundingClientRect().top),
                       labelBottom: Math.round(label.getBoundingClientRect().bottom) };
            })""")
            assert len({item["input"] for item in label_input_tops}) == 1
            second_row = page.locator("#address .property-address-grid").nth(1)
            second_row_tops = second_row.evaluate("""(row) => [...row.querySelectorAll('input')].map((input) =>
              Math.round(input.getBoundingClientRect().top))""")
            assert len(set(second_row_tops)) == 1

            page.goto(f"{base}/entities?lang={lang}")
            _capture_review(page, f"operators-1280-{lang}")
            rows = page.locator(".entities-page tbody tr")
            assert rows.count() == 2
            for row in rows.all():
                for label in ("Edit", "Invoice settings") if lang == "en" else ("Upravit", "Nastavení faktur"):
                    assert row.get_by_role("link", name=label).count() == 1
                assert row.locator(".row-menu-trigger").is_visible()
                assert row.locator(".row-actions").evaluate(
                    "cell => [...cell.children].every(el => getComputedStyle(el).opacity === '1')"
                )

            linked_row = rows.filter(has_text="Linked Operator")
            linked_row.locator(".row-menu-trigger").click()
            menu = page.locator(".row-menu-panel.is-open")
            linked_delete = menu.get_by_role("menuitem", name="Delete" if lang == "en" else "Smazat")
            assert linked_delete.is_visible()
            assert linked_delete.get_attribute("aria-disabled") == "true"
            explanation = menu.locator(".row-menu-explanation")
            assert explanation.is_visible()
            assert explanation.inner_text().strip()
            assert explanation.get_attribute("id") in linked_delete.get_attribute("aria-describedby")
            before = len(requests)
            linked_delete.focus()
            page.keyboard.press("Enter")
            linked_delete.evaluate("element => element.click()")
            assert len(requests) == before
            page.keyboard.press("Escape")

            free_row = rows.filter(has_text="Free Operator")
            free_row.locator(".row-menu-trigger").click()
            free_delete = page.locator(".row-menu-panel.is-open").get_by_role(
                "menuitem", name="Delete" if lang == "en" else "Smazat"
            )
            assert free_delete.is_visible()
            assert free_delete.get_attribute("aria-disabled") is None

        for width in (360, 390):
            page.set_viewport_size({"width": width, "height": 900})
            for lang in ("en", "cs"):
                page.goto(f"{base}/apartments/new?lang={lang}")
                _capture_review(page, f"address-{width}-{lang}")
                fields = page.locator("#address .property-address-grid").first.locator(".field")
                input_tops = fields.evaluate_all("""(fields) => [...fields].map((field) =>
                  Math.round(field.querySelector('input').getBoundingClientRect().top))""")
                assert input_tops == sorted(input_tops)
                assert page.locator("#address").evaluate("el => el.scrollWidth <= el.clientWidth")
                page.goto(f"{base}/entities?lang={lang}")
                _capture_review(page, f"operators-{width}-{lang}")
                linked_row = page.locator(".entities-page tbody tr").filter(has_text="Linked Operator")
                trigger = linked_row.locator(".row-menu-trigger")
                assert trigger.is_visible()
                assert trigger.evaluate("el => getComputedStyle(el.parentElement).opacity") == "1"
                trigger.tap()
                mobile_menu = page.locator(".row-menu-panel.is-open")
                mobile_delete = mobile_menu.get_by_role("menuitem", name="Delete" if lang == "en" else "Smazat")
                assert mobile_menu.locator(".row-menu-explanation").is_visible()
                assert mobile_delete.get_attribute("aria-disabled") == "true"
                page.keyboard.press("Escape")

        page.set_viewport_size({"width": 1280, "height": 1000})
        page.goto(f"{base}/apartments?lang=en")
        # 0099: the list shows the Properties section tabs (one component),
        # with the list itself as the open tab; property pages show none.
        assert page.locator(".host-local-nav").count() == 1
        assert page.locator('.sub-tabs a[aria-current="page"]').inner_text() == "Properties"
        assert page.locator(".host-tools").count() == 0
        page.goto(f"{base}/apartments/{host['apartment']}?lang=en")
        assert page.locator(".host-tools").count() == 0
        assert page.locator(".host-local-nav").count() == 0
        assert page.locator('[data-copy="overview-guest-url"]').count() > 0
        browser.close()


# --- 0088: required operator, no activity switch ---------------------------

_EVIDENCE_0088 = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "0088-evidence"

_FIT_JS = """(selector) => {
  const vw = document.documentElement.clientWidth;
  const offenders = [];
  for (const el of document.querySelectorAll(selector)) {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    if (r.right > vw + 1 || r.left < -1) offenders.push({id: el.id, right: Math.round(r.right), vw});
  }
  return {scroll: document.documentElement.scrollWidth, vw, offenders};
}"""


def _shot_0088(page, name):
    if os.environ.get("UBYHOST_CAPTURE_0088") == "1":
        _EVIDENCE_0088.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(_EVIDENCE_0088 / f"{name}.png"), full_page=True)


def _assert_operator_fits(page):
    result = page.evaluate(_FIT_JS, "#operator-picker, #operator-picker select, #operator-picker .btn, #alternate-controller select")
    assert result["scroll"] <= result["vw"] + 1, result
    assert not result["offenders"], result


def _sidebar(page, collapsed):
    page.evaluate(
        """(want) => {
          const now = document.body.classList.contains('sidebar-collapsed');
          if (want === now) return;
          const btn = document.querySelector('button[data-sidebar-collapse]');
          if (btn && btn.offsetParent !== null) { btn.click(); return; }
          document.body.classList.toggle('sidebar-collapsed', want);
        }""",
        collapsed,
    )


def _extra_host(entities):
    username = f"property-controls-{secrets.token_hex(4)}"
    owner_id = auth.create_account(f"{username}@example.test", "Operator Evidence", role="host", username=username)
    for index in range(entities):
        db.insert("legal_entity", {
            "name": "Sole Operator s.r.o." if index == 0 else f"Operator {index}",
            "owner_user_id": owner_id,
            "created_at": db.utcnow(),
        })
    client = TestClient(app)
    assert login_as(client, username, url="/login?lang=en", follow_redirects=False).status_code == 303
    return owner_id, client.cookies.get(auth.SESSION_COOKIE)


def _drop_host(owner_id):
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


def test_required_operator_controls_in_browser(host, base):
    """Zero, one and several operators; no active switch; visible controller."""
    none_owner, none_cookie = _extra_host(0)
    one_owner, one_cookie = _extra_host(1)
    try:
        with sync_api.sync_playwright() as playwright:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
            contexts = {}
            for key, cookie in (("many", _session_cookie(host)), ("none", none_cookie), ("one", one_cookie)):
                context = browser.new_context(viewport={"width": 1280, "height": 1000})
                context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
                contexts[key] = context.new_page()

            many = contexts["many"]
            for width in (360, 390, 1280):
                for page in contexts.values():
                    page.set_viewport_size({"width": width, "height": 900})
                for lang in ("en", "cs"):
                    many.goto(f"{base}/apartments/new?lang={lang}")
                    select = many.locator("#legal_entity_id")
                    assert select.is_visible()
                    assert many.locator('[name="legal_entity_id"]').count() == 1
                    assert select.evaluate("el => el.required && el.value === ''")
                    assert many.locator("#active, #controller_is_operator").count() == 0
                    _assert_operator_fits(many)
                    _shot_0088(many, f"new-many-{width}-{lang}")

                    none = contexts["none"]
                    none.goto(f"{base}/apartments/new?lang={lang}")
                    message = none.locator("#operator-message")
                    assert message.is_visible()
                    assert none.locator('#operator-message a[href="/entities"]').is_visible()
                    assert none.locator('button[name="operator_refresh"]').is_visible()
                    assert not none.locator("#legal_entity_id").evaluate("el => el.checkValidity()")
                    _assert_operator_fits(none)
                    _shot_0088(none, f"new-none-{width}-{lang}")

                    one = contexts["one"]
                    one.goto(f"{base}/apartments/new?lang={lang}")
                    assert one.locator("#legal_entity_id").input_value() != ""
                    assert one.locator("#legal_entity_id option:checked").inner_text().strip() == "Sole Operator s.r.o."
                    _assert_operator_fits(one)
                    _shot_0088(one, f"new-one-{width}-{lang}")

                    many.goto(f"{base}/apartments/{host['apartment']}?view=settings&section=property&lang={lang}")
                    controller = many.locator("#data_controller_entity_id")
                    assert controller.is_visible()
                    assert controller.locator("option").first.inner_text().strip() in ("Same as operator", "Stejný jako provozovatel")
                    assert many.locator("#active").count() == 0
                    _assert_operator_fits(many)
                    _shot_0088(many, f"edit-{width}-{lang}")

            # The browser itself refuses a blank choice; no JS needed.
            many.set_viewport_size({"width": 1280, "height": 1000})
            many.goto(f"{base}/apartments/new?lang=en")
            many.fill("#internal_name", "Browser Operator Flat")
            many.fill("#addr_obec", "Praha")
            many.fill("#addr_house_no", "12")
            many.fill("#addr_zip", "11000")
            assert not many.locator("#legal_entity_id").evaluate("el => el.checkValidity()")
            # A forged blank operator (validation bypassed) comes back with the draft and an error.
            many.evaluate("() => { document.querySelector('#legal_entity_id').required = false; }")
            many.locator(".property-create-actions button[type=submit]").click()
            many.wait_for_load_state()
            assert many.locator("#operator-message[role=alert]").is_visible()
            assert many.locator("#internal_name").input_value() == "Browser Operator Flat"
            _shot_0088(many, "new-error-1280-en")
            many.select_option("#legal_entity_id", str(host["free"]))
            many.locator(".property-create-actions button[type=submit]").click()
            many.wait_for_load_state()
            created = db.query_one(
                "SELECT * FROM apartment WHERE internal_name = ? AND owner_user_id = ?",
                ("Browser Operator Flat", host["owner"]),
            )
            assert created and created["legal_entity_id"] == host["free"] and created["active"] == 1

            # Zero operators: "Check again" keeps the typed name after one is added.
            none = contexts["none"]
            none.set_viewport_size({"width": 1280, "height": 1000})
            none.goto(f"{base}/apartments/new?lang=en")
            none.fill("#internal_name", "Detour Flat")
            db.insert("legal_entity", {"name": "Added Later", "owner_user_id": none_owner, "created_at": db.utcnow()})
            none.locator('button[name="operator_refresh"]').click()
            none.wait_for_load_state()
            assert none.locator("#internal_name").input_value() == "Detour Flat"
            assert none.locator("#legal_entity_id option:checked").inner_text().strip() == "Added Later"
            _shot_0088(none, "new-detour-1280-en")

            # Geometry across wider lanes, sidebar expanded and collapsed.
            for width in (760, 1024, 1440, 1680, 1920, 2048):
                many.set_viewport_size({"width": width, "height": 900})
                for path in ("/apartments/new?lang=cs", f"/apartments/{host['apartment']}?view=settings&lang=cs"):
                    many.goto(base + path)
                    many.evaluate("() => { const d = document.querySelector('#basics'); if (d) d.open = true; }")
                    for collapsed in (False, True):
                        _sidebar(many, collapsed)
                        _assert_operator_fits(many)
                _sidebar(many, False)
            browser.close()
    finally:
        db.execute(
            "DELETE FROM apartment WHERE internal_name = ? AND owner_user_id = ?",
            ("Browser Operator Flat", host["owner"]),
        )
        _drop_host(none_owner)
        _drop_host(one_owner)


# --- 0089: calendar platform first, required with the link ------------------

_EVIDENCE_0089 = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "0089-evidence"


def _shot_0089(page, name):
    if os.environ.get("UBYHOST_CAPTURE_0089") == "1":
        _EVIDENCE_0089.mkdir(parents=True, exist_ok=True)
        page.locator("#calendar-add").scroll_into_view_if_needed()
        page.screenshot(path=str(_EVIDENCE_0089 / f"{name}.png"), full_page=True)


def test_calendar_platform_controls_in_browser(host, base):
    apartment = host["apartment"]
    db.insert("ical_feed", {
        "apartment_id": apartment, "url": "https://admin.booking.com/hotel/ical.html?t=synthetic",
        "label": "", "own_name": "", "active": 1, "created_at": db.utcnow(),
    })
    try:
        with sync_api.sync_playwright() as playwright:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
            context = browser.new_context(viewport={"width": 1280, "height": 1000})
            context.add_cookies([{"name": auth.SESSION_COOKIE, "value": _session_cookie(host), "url": base + "/"}])
            page = context.new_page()
            for width in (360, 390, 1280):
                page.set_viewport_size({"width": width, "height": 900})
                for lang in ("en", "cs"):
                    page.goto(f"{base}/apartments/{apartment}?lang={lang}#calendar-connect")
                    form = page.locator("#calendar-add")
                    platform = form.locator("#label")
                    assert platform.is_visible()
                    assert form.locator("details").count() == 0
                    top_platform = platform.bounding_box()["y"]
                    assert top_platform < form.locator("#url").bounding_box()["y"]
                    assert platform.evaluate("el => el.required && el.value === ''")
                    assert not form.locator("#label_other").is_visible()
                    assert form.locator("#own_name").is_visible()
                    table = page.locator(".feed-table")
                    assert "Booking.com" in table.inner_text()
                    assert "—" not in table.inner_text()
                    fit = page.evaluate(_FIT_JS, "#calendar-add, #calendar-add select, #calendar-add input, #calendar-add .btn")
                    assert fit["scroll"] <= fit["vw"] + 1 and not fit["offenders"], fit
                    _shot_0089(page, f"calendar-add-{width}-{lang}")
                    platform.select_option("other")
                    assert form.locator("#label_other").is_visible()
                    _shot_0089(page, f"calendar-other-{width}-{lang}")

            # Validation bypassed in the browser: the server still refuses, keeps the draft, focuses the error.
            page.set_viewport_size({"width": 1280, "height": 1000})
            page.goto(f"{base}/apartments/{apartment}?lang=en#calendar-connect")
            page.evaluate("() => document.querySelectorAll('#calendar-add [required]').forEach(el => el.required = false)")
            page.fill("#calendar-add #url", "https://example.invalid/synthetic.ics")
            page.fill("#calendar-add #own_name", "Garden")
            page.locator("#calendar-add button[type=submit]").click()
            page.wait_for_load_state()
            assert page.locator("#label-error[role=alert]").is_visible()
            assert page.locator("#calendar-add #url").input_value() == "https://example.invalid/synthetic.ics"
            assert page.locator("#calendar-add #own_name").input_value() == "Garden"
            assert page.evaluate("() => document.activeElement && document.activeElement.id") == "label"
            assert db.query("SELECT id FROM ical_feed WHERE apartment_id = ? AND url LIKE '%example.invalid%'", (apartment,)) == []
            _shot_0089(page, "calendar-error-1280-en")
            browser.close()
    finally:
        db.execute("DELETE FROM ical_feed WHERE apartment_id = ?", (apartment,))
