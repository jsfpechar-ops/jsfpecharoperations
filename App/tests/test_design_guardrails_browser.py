"""Layout guard: MASTER 11.0 hard layout rules on every host page (0156)."""
from __future__ import annotations

import json
import os
import secrets
from pathlib import Path

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth, db, property_setup
from app.main import app
from fastapi.testclient import TestClient
from tests.conftest import login_as
from tests.browser_support import chromium_launch_kwargs
from test_host_wide_geometry_browser import (  # noqa: F401  (fixtures are re-created here)
    CAPTURE_ROUTES,
    _dismiss_optional_security_prompt,
    _wait_for_host_layout,
    wide_base,
    wide_host,
)

GUARD = (Path(__file__).parent / "design_guard.js").read_text()

ROUTES = {key: path for key, (path, _selector) in CAPTURE_ROUTES.items()}
ROUTES.update({
    "cleaning": "/cleaning",
    "guest-guide": "/apartments/{property_id}/guide",
    "guest-guide-qr": "/apartments/{property_id}/guide/qr",
    "guest-questions": "/apartments/{property_id}/guide/questions",
    "guest-new": "/reservations/{reservation_id}/guests/new",
    "setup-property": "/apartments/{property_id}/setup/property",
    "setup-police": "/apartments/{property_id}/setup/police",
    "setup-guest-link": "/apartments/{property_id}/setup/guest_link",
    "setup-calendar": "/apartments/{property_id}/setup/calendar",
    "setup-stay-fee": "/apartments/{property_id}/setup/stay_fee",
    "setup-door-lock": "/apartments/{property_id}/setup/door_lock",
    "setup-automation": "/apartments/{property_id}/setup/automation",
    "setup-try-it": "/apartments/{property_id}/setup/try_it",
    "settings-account": "/settings",
    "havel": "/havel",
})


def test_every_host_page_passes_the_layout_guard(wide_host, wide_base):
    cookie = wide_host["cookie"]
    routes = {
        key: path.format(
            invoice_id=wide_host["invoice"], entity_id=wide_host["entity"],
            reservation_id=wide_host["reservations"][0],
            submission_id=wide_host["submission"],
            property_id=wide_host["apartments"][0],
            unconfigured_apartment=wide_host["unconfigured_apartment"],
            configured_apartment=wide_host["configured_apartment"],
            today=wide_host["today"], housebook_end=wide_host["housebook_end"],
        )
        for key, path in ROUTES.items()
    }
    findings = []
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception:
            if REQUIRE_BROWSER:
                raise
            pytest.skip("Chromium is required for the layout guard")
        for width in (390, 1280, 2000):
            for collapsed in ((False, True) if width >= 1024 else (False,)):
                state = "collapsed" if collapsed else "open"
                context = browser.new_context(viewport={"width": width, "height": 1000})
                context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": wide_base + "/"}])
                context.add_init_script(
                    "try { localStorage.setItem('ubyhost-sidebar-collapsed', '%s'); } catch (e) {}"
                    % ("1" if collapsed else "0")
                )
                page = context.new_page()
                for name, path in routes.items():
                    separator = "&" if "?" in path else "?"
                    response = page.goto(f"{wide_base}{path}{separator}lang=en")
                    assert response and response.status < 400, (
                        f"{name}/{width}/{state}: HTTP {response.status if response else 'none'}"
                    )
                    _wait_for_host_layout(page)
                    _dismiss_optional_security_prompt(page)
                    for finding in page.evaluate(GUARD, width < 1024):
                        findings.append((name, width, state, finding))
                    trigger = page.locator("button.row-menu-trigger:visible").first
                    if trigger.count():
                        trigger.click()
                        panel = page.locator(".row-menu-panel:visible").first
                        if panel.count():
                            box = panel.bounding_box()
                            doc_h = page.evaluate("document.documentElement.scrollHeight")
                            if box and (box["x"] < 0 or box["x"] + box["width"] > width
                                        or box["y"] + box["height"] > doc_h):
                                findings.append((name, width, state, ["menu-off-screen", box]))
                            if panel.locator("input:not([type=hidden]):not(.sr-only):visible, textarea:visible, select:visible").count():
                                findings.append((name, width, state, ["menu-holds-form"]))
                        page.keyboard.press("Escape")
                context.close()
        browser.close()
    report = os.environ.get("UBYHOST_GUARD_REPORT", "/tmp/ubyhost-layout-guard.json")
    Path(report).write_text(json.dumps(
        [{"route": r, "width": w, "sidebar": s, "finding": f} for r, w, s, f in findings], indent=1))
    counts = {}
    for _r, _w, _s, f in findings:
        counts[f[0]] = counts.get(f[0], 0) + 1
    lines = [f"{r} {w} {s}: {f}" for r, w, s, f in findings[:40]]
    assert not findings, f"{len(findings)} layout findings {counts}\n" + "\n".join(lines)


def test_admin_pages_pass_the_layout_guard(wide_host, wide_base):
    username = f"guard-admin-{secrets.token_hex(4)}"
    admin_id = auth.create_account(f"{username}@example.test", "Guard Admin", role="admin", username=username)
    client = TestClient(app)
    login_as(client, username, url="/login?lang=en", follow_redirects=False)
    cookie = client.cookies.get(auth.SESSION_COOKIE)
    assert cookie
    routes = {
        "admin-users": "/admin/users",
        "admin-customers": "/admin/customers",
        "admin-customer": f"/admin/customers/{wide_host['owner']}",
        "admin-users-manage": f"/admin/users?manage={wide_host['owner']}",
        "admin-operations": "/admin/operations",
    }
    findings = []
    try:
        with sync_api.sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(**chromium_launch_kwargs())
            except Exception:
                if REQUIRE_BROWSER:
                    raise
                pytest.skip("Chromium is required for the layout guard")
            for width in (390, 1280, 2000):
                for collapsed in ((False, True) if width >= 1024 else (False,)):
                    state = "collapsed" if collapsed else "open"
                    context = browser.new_context(viewport={"width": width, "height": 1000})
                    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": wide_base + "/"}])
                    context.add_init_script(
                        "try { localStorage.setItem('ubyhost-sidebar-collapsed', '%s'); } catch (e) {}"
                        % ("1" if collapsed else "0")
                    )
                    page = context.new_page()
                    for name, path in routes.items():
                        separator = "&" if "?" in path else "?"
                        response = page.goto(f"{wide_base}{path}{separator}lang=en")
                        assert response and response.status < 400, (
                            f"{name}/{width}/{state}: HTTP {response.status if response else 'none'}"
                        )
                        _wait_for_host_layout(page)
                        _dismiss_optional_security_prompt(page)
                        for finding in page.evaluate(GUARD, width < 1024):
                            findings.append((name, width, state, finding))
                        trigger = page.locator("button.row-menu-trigger:visible").first
                        if trigger.count():
                            trigger.click()
                            panel = page.locator(".row-menu-panel:visible").first
                            if panel.count():
                                box = panel.bounding_box()
                                doc_h = page.evaluate("document.documentElement.scrollHeight")
                                if box and (box["x"] < 0 or box["x"] + box["width"] > width
                                            or box["y"] + box["height"] > doc_h):
                                    findings.append((name, width, state, ["menu-off-screen", box]))
                                if panel.locator("input:not([type=hidden]):not(.sr-only):visible, textarea:visible, select:visible").count():
                                    findings.append((name, width, state, ["menu-holds-form"]))
                            page.keyboard.press("Escape")
                    context.close()
            browser.close()
    finally:
        db.execute("DELETE FROM audit WHERE owner_user_id = ? OR actor_user_id = ?", (admin_id, admin_id))
        db.execute("DELETE FROM legal_acceptance WHERE user_account_id = ?", (admin_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (admin_id,))
    lines = [f"{r} {w} {s}: {f}" for r, w, s, f in findings[:40]]
    assert not findings, f"{len(findings)} admin layout findings\n" + "\n".join(lines)


def test_admin_users_columns_start_on_one_line(wide_host, wide_base):
    username = f"guard-admin-{secrets.token_hex(4)}"
    admin_id = auth.create_account(f"{username}@example.test", "Guard Admin", role="admin", username=username)
    client = TestClient(app)
    login_as(client, username, url="/login?lang=en", follow_redirects=False)
    cookie = client.cookies.get(auth.SESSION_COOKIE)
    assert cookie
    try:
        with sync_api.sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(**chromium_launch_kwargs())
            except Exception:
                if REQUIRE_BROWSER:
                    raise
                pytest.skip("Chromium is required for the columns test")
            context = browser.new_context(viewport={"width": 1280, "height": 1000})
            context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": wide_base + "/"}])
            context.add_init_script("try { localStorage.setItem('ubyhost-sidebar-collapsed', '0'); } catch (e) {}")
            page = context.new_page()
            response = page.goto(f"{wide_base}/admin/users?manage={wide_host['owner']}&lang=en")
            assert response and response.status < 400, f"HTTP {response.status if response else 'none'}"
            _wait_for_host_layout(page)
            _dismiss_optional_security_prompt(page)
            gap = page.evaluate(
                "() => { const s = document.querySelector('.split.wide'); const a = s.children[0].getBoundingClientRect().top, b = s.children[1].getBoundingClientRect().top; return Math.abs(a - b); }"
            )
            assert gap <= 2, f"split columns start {gap}px apart"
            email = page.locator("#user-manage input[type=email]")
            if email.count() == 0:
                email = page.locator("#user-manage input:not([type=hidden]):visible")
            width = email.first.bounding_box()["width"]
            assert width <= 660, f"manage input is {width}px wide"
            context.close()
            browser.close()
    finally:
        db.execute("DELETE FROM audit WHERE owner_user_id = ? OR actor_user_id = ?", (admin_id, admin_id))
        db.execute("DELETE FROM legal_acceptance WHERE user_account_id = ?", (admin_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (admin_id,))


def test_empty_state_action_is_centred_under_its_text(wide_host, wide_base):
    """0176: the empty-state action sits on the text's centre line (ui_btn-group centres it)."""
    cookie = wide_host["cookie"]
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception:
            if REQUIRE_BROWSER:
                raise
            pytest.skip("Chromium is required for the empty-state test")
        context = browser.new_context(viewport={"width": 1280, "height": 1000})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": wide_base + "/"}])
        page = context.new_page()
        response = page.goto(f"{wide_base}/invoices?lang=en")
        assert response and response.status < 400, f"HTTP {response.status if response else 'none'}"
        _wait_for_host_layout(page)
        _dismiss_optional_security_prompt(page)
        centres = page.evaluate(
            """() => {
                const main = document.querySelector('main') || document.body;
                const wrap = document.createElement('div');
                wrap.className = 'host-workspace';
                wrap.innerHTML = '<div class="ui-empty" data-empty-state><h2>No invoices yet</h2>'
                    + '<p>Generate your first invoice to get started.</p>'
                    + '<div class="ui-btn-group"><a class="ui-btn ui-btn-secondary" href="#guard"><span>Generate invoice</span></a></div></div>';
                main.prepend(wrap);
                const empty = wrap.querySelector('.ui-empty');
                const text = empty.querySelector('p').getBoundingClientRect();
                const btn = empty.querySelector('a').getBoundingClientRect();
                return { text: text.left + text.width / 2, button: btn.left + btn.width / 2 };
            }"""
        )
        gap = abs(centres["button"] - centres["text"])
        assert gap <= 2, f"empty-state action centre is {gap}px off the text centre"
        context.close()
        browser.close()


def test_setup_checklist_is_a_padded_card(wide_host, wide_base):
    """0286: the health check lives on the overview cards; no separate checklist box, details stay."""
    cookie = wide_host["cookie"]
    property_id = wide_host["configured_apartment"]
    # The checklist shows only when the setup wizard is not active (_property_overview.html line 48):
    # mark this property's wizard finished with the same helpers the app uses.
    property_setup.start(property_id)
    property_setup.finish(property_id)
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception:
            if REQUIRE_BROWSER:
                raise
            pytest.skip("Chromium is required for the setup checklist test")
        context = browser.new_context(viewport={"width": 1280, "height": 1000})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": wide_base + "/"}])
        page = context.new_page()
        response = page.goto(f"{wide_base}/apartments/{property_id}?lang=en")
        assert response and response.status < 400, f"HTTP {response.status if response else 'none'}"
        _wait_for_host_layout(page)
        _dismiss_optional_security_prompt(page)
        # Fails the test if the checklist is absent: the configured fixture property must show it.
        page.wait_for_selector("[data-setup-status]", timeout=5000)
        facts = page.evaluate(
            """() => ({
                box: !!document.querySelector('.host-checklist'),
                dots: document.querySelectorAll('.host-property-grid [data-health-check] .host-property-card-dot').length,
                details: !!document.querySelector('.host-workspace details.setup-readiness-help[data-setup-status]'),
            })"""
        )
        print(f"setup health measured: {facts}")
        assert not facts["box"], "the separate health check box is back"
        assert facts["dots"] >= 4, f"only {facts['dots']} cards carry a health dot"
        assert facts["details"], "the checklist details are missing"
        context.close()
        browser.close()


def test_guest_card_facts_share_four_column_lines(wide_host, wide_base):
    """0179: both rows of a guest card's facts start on the same four column lines."""
    cookie = wide_host["cookie"]
    reservation_id = wide_host["reservations"][0]
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception:
            if REQUIRE_BROWSER:
                raise
            pytest.skip("Chromium is required for the guest card test")
        context = browser.new_context(viewport={"width": 1280, "height": 1000})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": wide_base + "/"}])
        page = context.new_page()
        response = page.goto(f"{wide_base}/reservations/{reservation_id}?lang=en")
        assert response and response.status < 400, f"HTTP {response.status if response else 'none'}"
        _wait_for_host_layout(page)
        _dismiss_optional_security_prompt(page)
        page.wait_for_selector(".guest-card .guest-facts dt", timeout=5000)
        lefts = page.evaluate(
            """() => Array.from(document.querySelector('.guest-card').querySelectorAll('.guest-facts dt'))
                .map(dt => dt.getBoundingClientRect().left)"""
        )
        context.close()
        browser.close()
    distinct = sorted({round(x / 2) * 2 for x in lefts})
    print(f"guest card fact column lines: {distinct}")
    assert len(lefts) >= 4, f"guest card shows only {len(lefts)} facts"
    assert len(distinct) <= 4, f"guest card facts start on {len(distinct)} different lines: {distinct}"


def test_table_rows_have_their_own_border_on_desktop(wide_host, wide_base):
    """0181: on desktop each table row is its own bordered card, with a gap between rows."""
    cookie = wide_host["cookie"]
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception:
            if REQUIRE_BROWSER:
                raise
            pytest.skip("Chromium is required for the table row border test")
        context = browser.new_context(viewport={"width": 1280, "height": 1000})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": wide_base + "/"}])
        page = context.new_page()
        response = page.goto(f"{wide_base}/reservations?lang=en")
        assert response and response.status < 400, f"HTTP {response.status if response else 'none'}"
        _wait_for_host_layout(page)
        _dismiss_optional_security_prompt(page)
        page.wait_for_selector(".host-workspace .ui-table tbody tr:nth-child(2) td", timeout=5000)
        facts = page.evaluate(
            """() => {
                const rows = document.querySelectorAll('.host-workspace .ui-table tbody tr');
                const first = rows[0].querySelector('td');
                const style = getComputedStyle(first);
                return {
                    top: style.borderTopWidth,
                    left: style.borderLeftWidth,
                    gap: rows[1].getBoundingClientRect().top - rows[0].getBoundingClientRect().bottom,
                };
            }"""
        )
        print(f"table row border measured: {facts}")
        assert facts["top"] == "1px", f"row top border is {facts['top']}, not 1px"
        assert facts["left"] == "1px", f"first cell left border is {facts['left']}, not 1px"
        assert facts["gap"] >= 4, f"rows are only {facts['gap']}px apart"
        context.close()
        browser.close()


def test_cleaning_card_facts_line_up_across_cards(wide_host, wide_base):
    """0182: the first and second fact of every cleaning card start on the same x."""
    cookie = wide_host["cookie"]
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception:
            if REQUIRE_BROWSER:
                raise
            pytest.skip("Chromium is required for the cleaning facts test")
        context = browser.new_context(viewport={"width": 1280, "height": 1000})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": wide_base + "/"}])
        page = context.new_page()
        response = page.goto(f"{wide_base}/cleaning?lang=en")
        assert response and response.status < 400, f"HTTP {response.status if response else 'none'}"
        _wait_for_host_layout(page)
        _dismiss_optional_security_prompt(page)
        page.wait_for_selector(".cleaning-card .cleaning-facts > div", timeout=5000)
        lefts = page.evaluate(
            """() => Array.from(document.querySelectorAll('.cleaning-card')).map(card =>
                Array.from(card.querySelectorAll('.cleaning-facts > div')).map(d => d.getBoundingClientRect().left))"""
        )
        context.close()
        browser.close()
    assert len(lefts) >= 2, f"cleaning list shows only {len(lefts)} cards"
    for index in (0, 1):
        firsts = {round(card[index] / 2) * 2 for card in lefts if len(card) > index}
        assert len(firsts) == 1, f"fact {index + 1} starts at different x across cards: {sorted(firsts)}"


def test_sidebar_search_has_a_border(wide_host, wide_base):
    """0183: the sidebar search row has a visible 1 px border, not a borderless grey fill."""
    cookie = wide_host["cookie"]
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception:
            if REQUIRE_BROWSER:
                raise
            pytest.skip("Chromium is required for the sidebar search border test")
        context = browser.new_context(viewport={"width": 1280, "height": 1000})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": wide_base + "/"}])
        page = context.new_page()
        response = page.goto(f"{wide_base}/?lang=en")
        assert response and response.status < 400, f"HTTP {response.status if response else 'none'}"
        _wait_for_host_layout(page)
        _dismiss_optional_security_prompt(page)
        page.wait_for_selector(".host-workspace .ui-search-row", timeout=5000)
        facts = page.evaluate(
            """() => {
                const style = getComputedStyle(document.querySelector('.host-workspace .ui-search-row'));
                return { top: style.borderTopWidth, color: style.borderTopColor };
            }"""
        )
        print(f"sidebar search border measured: {facts}")
        assert facts["top"] == "1px", f"search border-top-width is {facts['top']}, not 1px"
        assert facts["color"] not in ("", "transparent", "rgba(0, 0, 0, 0)"), "search border is transparent"
        context.close()
        browser.close()


BORDERED_ROUTES = {
    "settings": "/settings",
    "housebook": "/housebook",
    "reservation": "/reservations/{reservation_id}",
    "setup-property": "/apartments/{property_id}/setup/property",
    "setup-police": "/apartments/{property_id}/setup/police",
    "setup-stay-fee": "/apartments/{property_id}/setup/stay_fee",
}


def test_host_sections_are_bordered_panels(wide_host, wide_base):
    """0189: every top-level .ui-section (except .ui-section-plain) has a border and padding."""
    cookie = wide_host["cookie"]
    paths = {
        key: path.format(
            reservation_id=wide_host["reservations"][0],
            property_id=wide_host["apartments"][0],
        )
        for key, path in BORDERED_ROUTES.items()
    }
    js = """() => Array.from(document.querySelectorAll('.ui-section:not(.ui-section-plain)'))
        .filter(el => !el.parentElement || !el.parentElement.closest('.ui-section'))
        .map(el => {
          const cs = getComputedStyle(el);
          const border = ['Top', 'Right', 'Bottom', 'Left'].reduce((n, side) => n + parseFloat(cs['border' + side + 'Width']), 0);
          const pad = ['Top', 'Right', 'Bottom', 'Left'].reduce((n, side) => n + parseFloat(cs['padding' + side]), 0);
          return {id: el.id || el.className, border, pad};
        })"""
    counts = {}
    findings = []
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception:
            if REQUIRE_BROWSER:
                raise
            pytest.skip("Chromium is required for the bordered section test")
        context = browser.new_context(viewport={"width": 1280, "height": 1000})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": wide_base + "/"}])
        page = context.new_page()
        for name, path in paths.items():
            separator = "&" if "?" in path else "?"
            response = page.goto(f"{wide_base}{path}{separator}lang=en")
            assert response and response.status < 400, f"{name}: HTTP {response.status if response else 'none'}"
            _wait_for_host_layout(page)
            _dismiss_optional_security_prompt(page)
            sections = page.evaluate(js)
            counts[name] = len(sections)
            for section in sections:
                if section["border"] <= 0 or section["pad"] <= 0:
                    findings.append((name, section))
        context.close()
        browser.close()
    print(f"bordered sections per page: {counts}")
    assert len(paths) >= 6
    assert sum(counts.values()) >= 6, f"too few .ui-section panels found: {counts}"
    assert not findings, f"flat .ui-section panels: {findings[:20]}"
