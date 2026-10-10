"""Wide-screen lane geometry with isolated synthetic host and invoice records."""
from __future__ import annotations

import json
import os
import re
import secrets
import socket
import threading
import time
from datetime import timedelta
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient
from playwright import sync_api

from app import alerts, auth, claim, db
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
WIDE_WIDTHS = (1024, 1280, 1440, 1680, 1920, 2048)
MOBILE_WIDTHS = (360, 390, 760)
MOBILE_ROUTE_KEYS = {
    "dashboard", "stays", "properties", "invoices", "fees-unset", "fees-configured",
    "invoice-new-picker", "invoice-new-selected", "invoice-settings", "invoice-detail",
    "property-new", "operator-add", "operator-edit", "property-detail",
    "property-detail-configured", "fee-setup", "fee-detail", "stay-detail",
}
CAPTURE_ROUTES = {
    "dashboard": ("/", ".dashboard-stats"),
    "stays": ("/reservations", ".stays-view, .panel.empty"),
    "properties": ("/apartments", ".panel.tight.scroll-x, .panel.empty"),
    "operators": ("/entities", ".entities-page, .panel.empty"),
    "operator-add": ("/entities?new=1", ".entity-add"),
    "operator-edit": ("/entities?edit={entity_id}", ".entity-form"),
    "invoices": ("/invoices", ".panel.tight.scroll-x, .panel.empty"),
    "fees-unset": ("/stay-fees?apartment={unconfigured_apartment}", ".panel.tight.scroll-x, .panel.empty"),
    "fees-configured": ("/stay-fees?apartment={configured_apartment}", ".panel.tight.scroll-x, .panel.empty"),
    "fee-setup": ("/stay-fees/{unconfigured_apartment}/setup", ".panel"),
    "fee-detail": ("/stay-fees/{configured_apartment}", ".stay-fee-detail, .panel"),
    "invoice-new-picker": ("/invoices/new", ".panel"),
    "invoice-new-selected": ("/invoices/new?entity={entity_id}&reservation_id={reservation_id}", ".invoice-workspace, .invoice-stay-picker"),
    "invoice-settings": ("/invoices/settings?entity={entity_id}", ".invoice-settings-form"),
    "invoice-detail": ("/invoices/{invoice_id}", ".invoice-workspace"),
    "property-new": ("/apartments/new", "form[action='/apartments']"),
    "stay-detail": ("/reservations/{reservation_id}", ".reservation-detail, .panel"),
    "stays-archive": ("/reservations?range=archive", ".stays-view, .panel.empty"),
    "property-detail": ("/apartments/{property_id}", ".property-detail, .panel"),
    "property-detail-configured": ("/apartments/{configured_apartment}", ".property-detail, .panel"),
    "housebook": ("/housebook?apartment={unconfigured_apartment}&from={today}&to={housebook_end}", ".housebook-page, .panel"),
    "submissions": ("/submissions", ".panel.tight.scroll-x, .panel.empty"),
    "submission-detail": ("/submissions/{submission_id}", ".submission-detail, .panel"),
    "guest-links": ("/guest-links", ".link-cards, .panel.empty"),
    "automation": ("/automation", ".panel"),
    "archive": ("/settings/archived", ".panel"),
    "settings": ("/settings", ".host-property-grid"),
    "smart-locks": ("/smart-locks", ".panel"),
}


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def wide_host():
    db.init_db()
    suffix = secrets.token_hex(4)
    username = f"wide-geometry-{suffix}"
    owner_id = auth.create_account(
        f"{username}@example.test", "Wide Geometry Fixture", role="host", username=username
    )
    now = db.utcnow()
    entity_id = db.insert("legal_entity", {
        "name": "Wide Geometry Fixture s.r.o.", "seat": "Praha", "ico": "12345678",
        "contact_email": "geometry@example.test", "vat_status": "non_payer",
        "invoice_due_days": 14, "owner_user_id": owner_id, "created_at": now,
    })
    apartment_ids = []
    for name, token, fee_rate in (
        ("Praha Riverside Loft — West Building", "widewest", 0),
        ("Dům U Šesti růží, long synthetic property name", "wideeast", 650),
    ):
        apartment_ids.append(db.insert("apartment", {
            "internal_name": name, "owner_user_id": owner_id, "legal_entity_id": entity_id,
            "permalink_token": f"{token}{suffix}", "permalink_pin": "123456",
            "automation_mode": "scheduled", "submit_after_hours": 24, "active": 1,
            "addr_obec": "Praha", "addr_street": "Testovací", "addr_house_no": "12",
            "addr_zip": "11000", "created_at": now,
            "stay_fee_rate_czk": fee_rate,
        }))

    today = claim.prague_today()
    reservation_ids = []
    for apartment_id, label, start, end, source, reservation_url in (
        (apartment_ids[0], "current", today, today + timedelta(days=2), "manual", None),
        (apartment_ids[0], "next", today + timedelta(days=4), today + timedelta(days=6), "manual", None),
        (apartment_ids[1], "later", today + timedelta(days=8), today + timedelta(days=10),
         "airbnb", "https://www.airbnb.com/rooms/1234567890123456789"),
        (apartment_ids[0], "overdue", today - timedelta(days=8), today - timedelta(days=6), "manual", None),
    ):
        reservation_ids.append(db.insert("reservation", {
            "apartment_id": apartment_id, "source": source, "uid": f"wide-{suffix}-{label}",
            "reservation_url": reservation_url,
            "date_from": start.isoformat(), "date_to": end.isoformat(), "status": "active",
            "expected_guests_override": None if label == "next" else 1,
            "created_at": now, "updated_at": now,
        }))

    db.insert("guest", {
        "reservation_id": reservation_ids[0], "surname": "NOVAK", "first_name": "TOMAS",
        "birth_date": "01011990", "nationality": "GBR", "doc_number": "P1234567",
        "res_street": "Street 1", "res_city": "London", "res_country": "GBR",
        "purpose": "10", "is_lead": 1, "entered_by": "host",
        "signature_png": "imported", "signed_at": now, "identity_verified_at": now,
        "submit_state": "pending", "created_at": now, "updated_at": now,
    })

    invoice_id = db.insert("invoice", {
        "legal_entity_id": entity_id, "apartment_id": apartment_ids[0],
        "reservation_id": reservation_ids[0], "kind": "invoice", "seq_year": today.year,
        "seq_no": 918, "number": f"{today.year}-0918-{suffix[:4]}",
        "vs": f"{today.year}0918", "lang": "en", "vat_status": "non_payer",
        "issue_date": today.isoformat(), "seller_name": "Wide Geometry Fixture s.r.o.",
        "seller_seat": "Praha", "buyer_name": "Synthetic Buyer with a Long Name",
        "total_haler": 123450, "owner_user_id": owner_id, "created_at": now,
    })
    db.insert("invoice_item", {
        "invoice_id": invoice_id, "position": 1, "kind": "accommodation",
        "description": "Synthetic accommodation", "quantity": 2, "unit": "nights",
        "vat_rate": 0, "base_haler": 123450, "vat_haler": 0, "gross_haler": 123450,
    })
    submission_id = db.insert("submission", {
        "apartment_id": apartment_ids[0], "created_at": now,
        "finished_at": now, "mode": "manual", "state": "error",
        "guest_ids": "[]", "header_errors": "", "record_errors": "[]",
        "error_text": "Synthetic browser audit fixture",
    })
    client = TestClient(app)
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    cookie = client.cookies.get(auth.SESSION_COOKIE)
    assert cookie
    yield {
        "owner": owner_id, "entity": entity_id, "apartments": apartment_ids,
        "reservations": reservation_ids, "invoice": invoice_id, "submission": submission_id, "cookie": cookie,
        "alert_key": f"wide-geometry:{suffix}",
        "today": today.isoformat(), "housebook_end": (today + timedelta(days=14)).isoformat(),
        "unconfigured_apartment": apartment_ids[0], "configured_apartment": apartment_ids[1],
    }
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM alert WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM invoice_item WHERE invoice_id = ?", (invoice_id,))
    db.execute("DELETE FROM invoice WHERE id = ?", (invoice_id,))
    db.execute("DELETE FROM guest WHERE reservation_id IN (?, ?, ?, ?)", tuple(reservation_ids))
    db.execute("DELETE FROM reservation WHERE apartment_id IN (?, ?)", tuple(apartment_ids))
    db.execute("DELETE FROM apartment WHERE id IN (?, ?)", tuple(apartment_ids))
    db.execute("DELETE FROM legal_entity WHERE id = ?", (entity_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


@pytest.fixture(scope="module")
def wide_base(wide_host):
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        pytest.fail("the wide geometry test server did not start")
    alert_id = db.insert("alert", {
        "level": "critical", "kind": "dates_changed_resign",
        "apartment_id": wide_host["apartments"][0], "reservation_id": wide_host["reservations"][0],
        "owner_user_id": wide_host["owner"], "dedupe_key": wide_host["alert_key"],
        "message": "Synthetic guest dates changed", "detail": "Synthetic date review required",
        "created_at": db.utcnow(),
    })
    wide_host["alert"] = alert_id
    assert alerts.open_alert(wide_host["alert_key"]), "synthetic date-change alert must remain open after app startup"
    probe = TestClient(app)
    probe.cookies.set(auth.SESSION_COOKIE, wide_host["cookie"])
    alert_probe = probe.get("/?lang=en")
    assert alert_probe.status_code == 200
    assert 'data-host-alerts' in alert_probe.text, "synthetic open date-change alert must render in signed-in host UI"
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def _capture_geometry(page, result_selector):
    return page.evaluate(
        """(resultSelector) => {
          const box = (selector) => {
            const element = selector && document.querySelector(selector);
            if (!element) return null;
            const rect = element.getBoundingClientRect();
            return Object.fromEntries(['left','right','top','bottom','width','height']
              .map(key => [key, Math.round(rect[key] * 100) / 100]));
          };
          const hostLane = (() => {
            const main = document.querySelector('main.wrap.with-sidebar');
            if (!main) return null;
            const rect = main.getBoundingClientRect();
            const style = getComputedStyle(main);
            const innerLeft = rect.left + parseFloat(style.paddingLeft);
            const innerWidth = main.clientWidth - parseFloat(style.paddingLeft)
              - parseFloat(style.paddingRight);
            const width = Math.min(1080, innerWidth);
            const left = innerLeft + Math.max(0, (innerWidth - width) / 2);
            return {left: Math.round(left * 100) / 100,
              right: Math.round((left + width) * 100) / 100, width};
          })();
          const table = document.querySelector('.panel.tight.scroll-x table');
          const staysPanel = document.querySelector(
            '.stays-view .panel.tight.scroll-x, .stays-view'
          );
          const rowActions = [...document.querySelectorAll(
            '.stays-view td.row-actions a, .stays-view td.row-actions button'
          )].map(element => {
            const r = element.getBoundingClientRect();
            const panel = staysPanel?.getBoundingClientRect();
            const visible = r.width > 0 && r.height > 0 && element.getClientRects().length > 0;
            const cell = element.closest('td.row-actions');
            return {text: element.innerText.trim() || element.getAttribute('aria-label') || '',
              className: element.className?.toString() || '', tagName: element.tagName,
              isCopy: element.hasAttribute('data-copy'),
              isMenu: element.classList.contains('row-menu-trigger'),
              rowGroup: cell ? [...document.querySelectorAll('.stays-view td.row-actions')].indexOf(cell) : -1,
              left: r.left, right: r.right, top: r.top, bottom: r.bottom,
              width: r.width, height: r.height,
              panelLeft: panel?.left ?? null, panelRight: panel?.right ?? null,
              visible, fullyVisible: visible && !!panel && r.left >= panel.left - 1
                && r.right <= panel.right + 1};
          });
          const compactCells = [...document.querySelectorAll(
            '.stays-view .stay-col-reporting, .stays-view .stay-col-deadline'
          )].map(cell => {
            const r = cell.getBoundingClientRect();
            const range = document.createRange();
            range.selectNodeContents(cell);
            return {className: cell.className, text: cell.innerText.trim(), left: r.left, right: r.right,
              width: r.width, scrollWidth: cell.scrollWidth, clientWidth: cell.clientWidth,
              height: r.height, lineRects: range.getClientRects().length};
          });
          const stayTracks = [...document.querySelectorAll('.stays-view tbody tr')].flatMap((row, rowIndex) =>
            ['.stay-col-stay .row-primary-link', '.stay-col-property .property-identity',
             '.stay-col-source .stay-portal-link', '.stay-col-guests',
             '.stay-col-reporting', '.stay-col-deadline'].flatMap(selector => {
              const content = row.querySelector(selector);
              const cell = content?.closest('td');
              if (!content || !cell) return [];
              const cellRect = cell.getBoundingClientRect();
              const range = document.createRange();
              const walker = document.createTreeWalker(content, NodeFilter.SHOW_TEXT, {
                acceptNode: node => node.parentElement?.closest('.sr-only')
                  ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT
              });
              const visibleTextRects = [];
              while (walker.nextNode()) {
                range.selectNode(walker.currentNode);
                visibleTextRects.push(...range.getClientRects());
              }
              return [{rowIndex, selector, text: content.innerText.trim(),
                cell: {left: cellRect.left, right: cellRect.right, width: cellRect.width,
                  clientWidth: cell.clientWidth, scrollWidth: cell.scrollWidth},
                contentRects: visibleTextRects.filter(rect => rect.width && rect.height)
                  .map(rect => ({left: rect.left, right: rect.right, top: rect.top,
                    bottom: rect.bottom, width: rect.width, height: rect.height}))}];
            })
          );
          const actionSelectors = [
            '.page-actions .btn', '.dashboard-actions .btn',
            '.dashboard-row-actions .btn', '.filter-panel-actions .btn',
            '.host-property-save .btn', '.invoice-form button[type=submit]',
            '.stays-view td.row-actions a', '.stays-view td.row-actions button'
          ];
          const actions = actionSelectors.flatMap(selector =>
            [...document.querySelectorAll(selector)].map(element => {
              const rect = element.getBoundingClientRect();
              return {selector, text: element.innerText.trim(), left: rect.left,
                right: rect.right, top: rect.top, bottom: rect.bottom,
                width: rect.width, height: rect.height};
            }));
          const alertCard = document.querySelector('.notification-stack [data-notification]');
          const laneChildren = [...document.querySelectorAll('main.wrap.with-sidebar > *')]
            .filter(element => getComputedStyle(element).display !== 'none')
            .map(element => ({className: element.className?.toString() || element.tagName,
              rect: boxFrom(element)}));
          function boxFrom(element) {
            const r = element.getBoundingClientRect();
            return {left: Math.round(r.left * 100) / 100, right: Math.round(r.right * 100) / 100,
              width: Math.round(r.width * 100) / 100};
          }
          return {
            viewport: {width: innerWidth, scrollWidth: document.documentElement.scrollWidth},
            hostLane,
            title: box('.page-header-main h1, .host-today-head h1'),
            pageHeader: box('.page-header, .host-today-head'),
            directBacklink: box('main.wrap.with-sidebar > a.back-link'),
            headerMain: box('.page-header-main, .host-today-head'),
            headerActions: box('.page-actions, .dashboard-actions'),
            navigation: box('.host-local-nav'),
            alertStack: box('.notification-stack'),
            feedbackRegion: box('[data-host-feedback]'),
            alertPosition: alertCard ? getComputedStyle(document.querySelector('.notification-stack')).position : null,
            alertLink: box('.notification-stack .notification-link'),
            alertDismissCount: document.querySelectorAll(
              '.notification-stack [data-notification-dismiss]'
            ).length,
            filterToolbar: box('.filter-toolbar'), filterPanel: box('.list-filter'),
            result: box(resultSelector), table: box('.panel.tight.scroll-x'),
            staysPanel: staysPanel ? {...boxFrom(staysPanel), clientWidth: staysPanel.clientWidth,
              scrollWidth: staysPanel.scrollWidth, scrollLeft: staysPanel.scrollLeft} : null,
            portalLinks: [...document.querySelectorAll('.stays-view .stay-portal-link')].map(link => {
              const r = link.getBoundingClientRect();
              return {text: link.innerText.trim(), left: r.left, right: r.right,
                width: r.width, height: r.height, whiteSpace: getComputedStyle(link).whiteSpace};
            }),
            rowActions,
            compactCells,
            stayTracks,
            form: box('form.invoice-form, .invoice-settings-form, form[action="/apartments"]'),
            tableTracks: table ? [...table.querySelectorAll('thead th')].map(th =>
              Math.round(th.getBoundingClientRect().width * 100) / 100) : [],
            actionControls: actions, laneChildren
          };
        }""",
        result_selector,
    )


def _dismiss_optional_security_prompt(page):
    """Use the visible, session-only Later control so page actions are interactable."""
    later = page.locator("button[data-security-prompt-later]")
    if later.count() and later.is_visible():
        later.click()


def _wait_for_host_layout(page):
    """Wait for the host script and two paint frames without network-idle delay."""
    page.wait_for_function(
        "document.readyState === 'complete' && document.documentElement.classList.contains('has-js')"
    )
    page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")


def _assert_stay_track_content(geometry, *, max_date_lines=None):
    """Ensure dates, property/source labels and compact values stay inside cells."""
    for track in geometry["stayTracks"]:
        for rect in track["contentRects"]:
            assert rect["left"] >= track["cell"]["left"] - 2 and rect["right"] <= (
                track["cell"]["right"] + 2
            ), f"stay content escapes {track['selector']} cell: {track}"
        if track["selector"] == ".stay-col-stay .row-primary-link" and max_date_lines is not None:
            assert len(track["contentRects"]) <= max_date_lines, (
                f"stay date broke into too many fragments: {track}"
            )


def test_host_wide_lanes_align(wide_host, wide_base):
    """Shared headers, filters and results use the same centered lane."""
    output_dir = Path(os.environ.get(
        "UBYHOST_WIDE_GEOMETRY_DIR", "/workspace/generated_images/host-wide-audit/after"
    ))
    output_dir.mkdir(parents=True, exist_ok=True)
    cookie = wide_host["cookie"]
    route_map = {
        key: (path.format(invoice_id=wide_host["invoice"], entity_id=wide_host["entity"],
                          reservation_id=wide_host["reservations"][0],
                          submission_id=wide_host["submission"],
                          property_id=wide_host["apartments"][0],
                          unconfigured_apartment=wide_host["unconfigured_apartment"],
                          configured_apartment=wide_host["configured_apartment"],
                          today=wide_host["today"], housebook_end=wide_host["housebook_end"]), selector)
        for key, (path, selector) in CAPTURE_ROUTES.items()
    }
    rect_rows = []
    mismatches = []
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception:
            if REQUIRE_BROWSER:
                raise
            pytest.skip("Chromium is required for wide host geometry capture")
        for width in (*WIDE_WIDTHS, *MOBILE_WIDTHS):
            for lang in ("en", "cs"):
                context = browser.new_context(viewport={"width": width, "height": 1100})
                context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": wide_base + "/"}])
                page = context.new_page()
                routes = route_map.items() if width in WIDE_WIDTHS else (
                    (key, value) for key, value in route_map.items() if key in MOBILE_ROUTE_KEYS
                )
                for name, (path, result_selector) in routes:
                    separator = "&" if "?" in path else "?"
                    response = page.goto(f"{wide_base}{path}{separator}lang={lang}")
                    assert response and response.status < 400, f"{name}/{lang}: HTTP {response.status if response else 'none'}"
                    _wait_for_host_layout(page)
                    _dismiss_optional_security_prompt(page)
                    page.evaluate("window.scrollTo(0, 0)")
                    toggle = page.locator("button[data-filter-toggle]")
                    if toggle.count() and toggle.is_visible() and toggle.get_attribute("aria-expanded") == "false":
                        toggle.click()
                        page.locator("form[data-filter-panel]").wait_for(state="visible")
                        page.evaluate("window.scrollTo(0, 0)")
                    geometry = _capture_geometry(page, result_selector)
                    assert geometry["viewport"]["scrollWidth"] <= width, (
                        f"document horizontally overflows at {name}/{lang}/{width}: "
                        f"{geometry['viewport']}"
                    )
                    record = {"route": name, "path": path, "locale": lang, "width": width, **geometry}
                    rect_rows.append(record)
                    title = geometry["title"]
                    result = geometry["result"]
                    assert result, f"{name}/{lang}/{width}: selected result lane {result_selector!r} is missing"
                    header = geometry["pageHeader"]
                    assert header, f"{name}/{lang}/{width}: page header is missing"
                    alert_stack = geometry["alertStack"]
                    assert alert_stack and geometry["alertLink"], (
                        f"synthetic persistent date-change alert not rendered on {name}/{lang}/{width}"
                    )
                    assert geometry["alertPosition"] == "static", geometry
                    assert geometry["alertDismissCount"] == 0, (
                        "dates_changed_resign alerts are filing gates and must remain non-dismissible"
                    )
                    for edge in ("left", "right"):
                        if abs(alert_stack[edge] - geometry["hostLane"][edge]) > 2:
                            mismatches.append({"route": name, "locale": lang, "width": width,
                                "lane": f"alertStack.{edge}", "result": geometry["hostLane"],
                                "candidate": alert_stack})
                    feedback_region = geometry["feedbackRegion"]
                    assert feedback_region and alert_stack["bottom"] <= feedback_region["top"] + 1, (
                        f"persistent alert overlaps feedback region on {name}/{lang}/{width}: "
                        f"alert={alert_stack}, feedback={feedback_region}"
                    )
                    navigation = geometry["navigation"]
                    if navigation:
                        assert feedback_region["bottom"] <= navigation["top"] + 1, (
                            f"feedback region overlaps local navigation on {name}/{lang}/{width}"
                        )
                    for edge in ("left", "right"):
                        delta = round(result[edge] - header[edge], 2)
                        if abs(delta) > 2:
                            mismatches.append({"route": name, "locale": lang, "width": width,
                                "lane": f"pageHeader.{edge}", "result": result,
                                "candidate": header, "delta": delta})
                    direct_backlink = geometry["directBacklink"]
                    if direct_backlink:
                        delta = round(direct_backlink["left"] - header["left"], 2)
                        if abs(delta) > 2:
                            mismatches.append({"route": name, "locale": lang, "width": width,
                                "lane": "directBacklink.left", "result": header,
                                "candidate": direct_backlink, "delta": delta})
                    if title and result and abs(result["left"] - title["left"]) > 2:
                        mismatches.append({"route": name, "locale": lang, "width": width,
                            "lane": "pageHeader.titleLeft", "result": result, "candidate": title})
                    lane = geometry["result"]
                    for lane_name in ("filterToolbar", "filterPanel"):
                        candidate = geometry[lane_name]
                        if lane and candidate and (abs(lane["left"] - candidate["left"]) > 2
                                                   or abs(lane["right"] - candidate["right"]) > 2):
                            mismatches.append({"route": name, "locale": lang, "width": width,
                                "lane": lane_name, "result": lane, "candidate": candidate})
                    if width >= 961 and geometry["headerActions"] and lane and abs(
                        geometry["headerActions"]["right"] - lane["right"]
                    ) > 2:
                        mismatches.append({"route": name, "locale": lang, "width": width,
                            "lane": "headerActions.right", "result": lane,
                            "candidate": geometry["headerActions"]})
                    if name == "stays":
                        _assert_stay_track_content(geometry, max_date_lines=2 if width >= 721 else None)
                        status_text = "\n".join(page.locator(
                            ".stays-view .stay-col-reporting"
                        ).all_inner_texts())
                        state_labels = (
                            ("Ready (scheduled)", "Waiting for guest", "Incomplete")
                            if lang == "en"
                            else ("Připraveno (naplánováno)", "Čeká na hosta", "Neúplné")
                        )
                        for state_label in state_labels:
                            assert state_label in status_text, (
                                f"synthetic rendered stay state {state_label!r} missing at {lang}/{width}: "
                                f"{status_text}"
                            )
                        visible_actions = [item for item in geometry["rowActions"] if item["visible"]]
                        assert len(visible_actions) >= 7, (
                            f"stay row actions missing at {lang}/{width}: {geometry['rowActions']}"
                        )
                        if width >= 1280:
                            hidden = [item for item in visible_actions if not item["fullyVisible"]]
                            assert not hidden, (
                                f"stay row actions clipped by visible list panel at {lang}/{width}: {hidden}"
                            )
                        for portal in geometry["portalLinks"]:
                            assert portal["whiteSpace"] == "nowrap" and portal["height"] <= 24, (
                                f"portal action wrapped at {lang}/{width}: {portal}"
                            )
                        expected_action_height = 44 if width in MOBILE_WIDTHS else 42
                        copy_groups = 0
                        for group in {item["rowGroup"] for item in visible_actions}:
                            grouped = [item for item in visible_actions if item["rowGroup"] == group]
                            menus = [item for item in grouped if item["isMenu"]]
                            assert menus, f"stay row has no visible More control: {grouped}"
                            more = menus[0]
                            for control in grouped:
                                assert abs(control["top"] - more["top"]) <= 2, (control, more)
                                assert abs(control["height"] - expected_action_height) <= 1, (control, more)
                            copies = [item for item in grouped if item["isCopy"]]
                            if copies:
                                copy_groups += 1
                        assert copy_groups >= 2, f"copy actions missing from synthetic incomplete rows: {visible_actions}"
                    visible_text = page.locator("body").inner_text()
                    raw_keys = [line.strip() for line in visible_text.splitlines()
                                if re.fullmatch(r"(?:common|confirm|host)\.[a-z0-9_.-]+", line.strip(), re.IGNORECASE)]
                    assert not raw_keys, f"raw translation key visible on {name}/{lang}/{width}: {raw_keys}"
                    if width in {1440, 1920} or width in MOBILE_WIDTHS or name in {
                        "dashboard", "stays", "properties", "invoices", "fees-unset", "fees-configured"
                    }:
                        page.screenshot(path=str(output_dir / f"after-{name}-{lang}-{width}.png"), full_page=True)
                context.close()
        browser.close()
    (output_dir / "rectangles.json").write_text(json.dumps(rect_rows, indent=2, ensure_ascii=False) + "\n")
    (output_dir / "lane-mismatches.json").write_text(json.dumps(mismatches, indent=2, ensure_ascii=False) + "\n")
    assert not mismatches, mismatches


def test_stay_row_actions_fit_midwidth_lanes(wide_host, wide_base):
    """Copy, More, portal, status and deadline content stays visible at mid widths."""
    output_dir = Path("/workspace/generated_images/host-wide-audit/after")
    output_dir.mkdir(parents=True, exist_ok=True)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        for width in (1024, 1280):
            for lang in ("en", "cs"):
                context = browser.new_context(viewport={"width": width, "height": 1000})
                context.add_cookies([{
                    "name": auth.SESSION_COOKIE, "value": wide_host["cookie"], "url": wide_base + "/",
                }])
                page = context.new_page()
                response = page.goto(f"{wide_base}/reservations?range=all&lang={lang}")
                assert response and response.status == 200
                page.wait_for_load_state("networkidle")
                _dismiss_optional_security_prompt(page)
                page.evaluate("window.scrollTo(0, 0)")
                geometry = _capture_geometry(page, ".stays-view")
                (output_dir / f"midwidth-rectangles-{lang}-{width}.json").write_text(json.dumps(
                    {"width": width, "locale": lang, **geometry}, indent=2, ensure_ascii=False
                ) + "\n")
                page.screenshot(path=str(output_dir / f"after-stays-actions-{lang}-{width}.png"), full_page=True)
                _assert_stay_track_content(geometry, max_date_lines=2)
                offenders = page.evaluate("""() => [...document.querySelectorAll('body *')].map(e => {
                  const r = e.getBoundingClientRect();
                  return {tag:e.tagName, cls:typeof e.className === 'string' ? e.className : '',
                    text:(e.innerText || '').trim().slice(0,60), left:r.left, right:r.right,
                    width:r.width, scrollWidth:e.scrollWidth, clientWidth:e.clientWidth};
                }).filter(x => x.right > innerWidth + 1 || x.left < -1).slice(0,25)""")
                assert geometry["viewport"]["scrollWidth"] <= width, (geometry["viewport"], offenders)
                visible_actions = [item for item in geometry["rowActions"] if item["visible"]]
                assert len(visible_actions) >= 7, geometry["rowActions"]
                assert all(item["fullyVisible"] for item in visible_actions), geometry["rowActions"]
                copy_groups = 0
                for group in {item["rowGroup"] for item in visible_actions}:
                    grouped = [item for item in visible_actions if item["rowGroup"] == group]
                    more = next(item for item in grouped if item["isMenu"])
                    for control in grouped:
                        assert abs(control["top"] - more["top"]) <= 2, (control, more)
                        assert abs(control["height"] - 42) <= 1, (control, more)
                    copies = [item for item in grouped if item["isCopy"]]
                    if copies:
                        copy_groups += 1
                assert copy_groups >= 2, geometry["rowActions"]
                assert len(geometry["portalLinks"]) >= 1, "synthetic Airbnb portal action was not rendered"
                assert all(item["whiteSpace"] == "nowrap" and item["height"] <= 24
                           for item in geometry["portalLinks"]), geometry["portalLinks"]
                overflow_cells = [cell for cell in geometry["compactCells"]
                                  if cell["scrollWidth"] > cell["clientWidth"] + 1]
                assert not overflow_cells, overflow_cells
                context.close()
        browser.close()


def test_direct_fee_backlinks_align_with_page_lane(wide_host, wide_base):
    """The fee setup/detail back links share the centered header lane."""
    output_dir = Path("/workspace/generated_images/host-wide-audit/after")
    output_dir.mkdir(parents=True, exist_ok=True)
    routes = (
        f"/stay-fees/{wide_host['unconfigured_apartment']}/setup",
        f"/stay-fees/{wide_host['configured_apartment']}",
    )
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = browser.new_context(viewport={"width": 1920, "height": 1000})
        context.add_cookies([{
            "name": auth.SESSION_COOKIE, "value": wide_host["cookie"], "url": wide_base + "/",
        }])
        page = context.new_page()
        for width in (1024, 1440, 1920):
            page.set_viewport_size({"width": width, "height": 1000})
            for lang in ("en", "cs"):
                for index, route in enumerate(routes):
                    response = page.goto(f"{wide_base}{route}?lang={lang}")
                    assert response and response.status == 200
                    page.wait_for_load_state("networkidle")
                    _dismiss_optional_security_prompt(page)
                    page.evaluate("window.scrollTo(0, 0)")
                    header = page.locator(".page-header").bounding_box()
                    back = page.locator("main.wrap.with-sidebar > a.back-link").bounding_box()
                    assert header and back
                    assert abs(back["x"] - header["x"]) <= 2, {
                        "width": width, "lang": lang, "route": route, "header": header, "back": back,
                    }
                    page.screenshot(path=str(output_dir / (
                        f"after-fee-backlink-{lang}-{width}-{index}.png"
                    )))
        context.close()
        browser.close()


def test_mobile_property_save_bar_does_not_cover_focused_address_field(wide_host, wide_base):
    """The live save bar leaves the focused address input visible and usable."""
    output_dir = Path("/workspace/generated_images/host-wide-audit/after")
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        for width in (360, 390):
            for lang in ("en", "cs"):
                context = browser.new_context(viewport={"width": width, "height": 820})
                context.add_cookies([{
                    "name": auth.SESSION_COOKIE, "value": wide_host["cookie"], "url": wide_base + "/",
                }])
                page = context.new_page()
                response = page.goto(f"{wide_base}/apartments/new?lang={lang}")
                assert response and response.status == 200
                page.wait_for_load_state("networkidle")
                _dismiss_optional_security_prompt(page)
                field = page.locator("#addr_zip")
                field.evaluate("(element) => element.scrollIntoView({block:'end', behavior:'instant'})")
                field.focus()
                field_box = field.bounding_box()
                save_box = page.locator(".host-property-save").bounding_box()
                assert field_box and save_box
                overlap_height = min(field_box["y"] + field_box["height"], save_box["y"] + save_box["height"]) - max(
                    field_box["y"], save_box["y"]
                )
                overlap_width = min(field_box["x"] + field_box["width"], save_box["x"] + save_box["width"]) - max(
                    field_box["x"], save_box["x"]
                )
                assert overlap_height <= 0 or overlap_width <= 0, {
                    "width": width, "lang": lang, "field": field_box, "save": save_box,
                }
                assert 0 <= field_box["y"] and field_box["y"] + field_box["height"] <= 821, {
                    "width": width, "lang": lang, "field": field_box,
                }
                rows.append({"width": width, "locale": lang, "field": field_box, "save": save_box,
                             "scrollY": page.evaluate("window.scrollY")})
                page.screenshot(path=str(output_dir / f"after-property-new-{lang}-{width}-focused.png"))
                context.close()
        browser.close()
    (output_dir / "address-focused-rectangles.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False) + "\n"
    )


def test_collapsed_sidebar_keeps_dashboard_and_stays_lanes_aligned(wide_host, wide_base):
    """A real sidebar collapse preserves both desktop lanes in EN and CS."""
    output_dir = Path("/workspace/generated_images/host-wide-audit/after")
    output_dir.mkdir(parents=True, exist_ok=True)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        for lang in ("en", "cs"):
            context = browser.new_context(viewport={"width": 1920, "height": 1100})
            context.add_cookies([{
                "name": auth.SESSION_COOKIE, "value": wide_host["cookie"], "url": wide_base + "/",
            }])
            page = context.new_page()
            for key, path, selector in (
                ("dashboard", "/", ".dashboard-stats"),
                ("stays", "/reservations", ".stays-view"),
            ):
                response = page.goto(f"{wide_base}{path}?lang={lang}")
                assert response and response.status == 200
                page.wait_for_load_state("networkidle")
                _dismiss_optional_security_prompt(page)
                if not page.locator("body").evaluate(
                    "element => element.classList.contains('sidebar-collapsed')"
                ):
                    page.locator("button[data-sidebar-collapse]").click()
                    page.wait_for_function("document.body.classList.contains('sidebar-collapsed')")
                else:
                    assert page.locator("body").evaluate(
                        "element => element.classList.contains('sidebar-collapsed')"
                    )
                page.evaluate("window.scrollTo(0, 0)")
                if key == "stays":
                    toggle = page.locator("button[data-filter-toggle]")
                    if toggle.count() and toggle.get_attribute("aria-expanded") == "false":
                        toggle.click()
                        page.locator("form[data-filter-panel]").wait_for(state="visible")
                        page.evaluate("window.scrollTo(0, 0)")
                geometry = _capture_geometry(page, selector)
                assert geometry["viewport"]["scrollWidth"] <= 1920, geometry["viewport"]
                for edge in ("left", "right"):
                    assert abs(geometry["pageHeader"][edge] - geometry["result"][edge]) <= 2, geometry
                assert abs(geometry["title"]["left"] - geometry["result"]["left"]) <= 2, geometry
                if key == "stays":
                    assert all(item["fullyVisible"] for item in geometry["rowActions"] if item["visible"])
                    for edge in ("left", "right"):
                        if geometry["filterToolbar"]:
                            assert abs(geometry["filterToolbar"][edge] - geometry["result"][edge]) <= 2
                        if geometry["filterPanel"]:
                            assert abs(geometry["filterPanel"][edge] - geometry["result"][edge]) <= 2
                page.screenshot(path=str(output_dir / f"after-{key}-{lang}-1920-collapsed.png"), full_page=True)
            context.close()
        browser.close()


def test_dashboard_760_header_and_actions_remain_in_the_shared_lane(wide_host, wide_base):
    """The compact dashboard title stays left-aligned and controls stay contained."""
    output_dir = Path("/workspace/generated_images/host-wide-audit/after")
    output_dir.mkdir(parents=True, exist_ok=True)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        for lang in ("en", "cs"):
            context = browser.new_context(viewport={"width": 760, "height": 1000})
            context.add_cookies([{
                "name": auth.SESSION_COOKIE, "value": wide_host["cookie"], "url": wide_base + "/",
            }])
            page = context.new_page()
            response = page.goto(f"{wide_base}/?lang={lang}")
            assert response and response.status == 200
            page.wait_for_load_state("networkidle")
            _dismiss_optional_security_prompt(page)
            page.evaluate("window.scrollTo(0, 0)")
            geometry = _capture_geometry(page, ".dashboard-stats")
            assert abs(geometry["pageHeader"]["left"] - geometry["result"]["left"]) <= 2, geometry
            assert abs(geometry["pageHeader"]["right"] - geometry["result"]["right"]) <= 2, geometry
            assert abs(geometry["title"]["left"] - geometry["result"]["left"]) <= 2, geometry
            actions = geometry["headerActions"]
            assert actions and actions["left"] >= geometry["pageHeader"]["left"] - 1
            assert actions["right"] <= geometry["pageHeader"]["right"] + 1
            title = geometry["title"]
            overlaps_x = min(actions["right"], title["right"]) > max(actions["left"], title["left"])
            overlaps_y = min(actions["bottom"], title["bottom"]) > max(actions["top"], title["top"])
            assert not (overlaps_x and overlaps_y), {
                "title": title, "actions": actions,
            }
            assert geometry["alertPosition"] == "static" and geometry["alertDismissCount"] == 0, {
                "alert": geometry["alertStack"], "body": page.locator("body").inner_text()[:500],
                "title": page.title(), "url": page.url,
            }
            assert geometry["alertStack"]["bottom"] <= geometry["feedbackRegion"]["top"] + 1
            page.screenshot(path=str(output_dir / f"after-dashboard-{lang}-760.png"), full_page=True)
            context.close()
        browser.close()
