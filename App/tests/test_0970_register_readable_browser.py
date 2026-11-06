"""0970: the house book is readable and its statutory output is untouched.

Browser checks (Chromium, 0 skipped with UBYHOST_REQUIRE_BROWSER=1) for the populated register at
390, 768, 1024 and 1280 px in English and Czech, plus a byte-for-byte check of the CSV export
against a copy recorded on the unchanged code (UBYHOST_B12_RECORD=1 records, no value compares).
"""
from __future__ import annotations

import hashlib
import os
import secrets
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

from app import auth, db, validation
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as
from tests.v2_mockup import geometry_findings

PREFIX = "reg-0970-"
SIGNATURE = "data:image/png;base64,AAAA"
SHOTS = Path(os.environ.get("UBYHOST_SHOTS_DIR") or "/tmp/ubyhost-b12")
_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "export-before-0970.csv"
GOLDEN = Path(os.environ.get("UBYHOST_B12_EXPORT_GOLDEN") or str(_FIXTURES))
LONG_SURNAME = "Kowalczyk-Nowakowska"
LONG_PROPERTY = "Rooftop Suite Vinohrady Residence"


def _cleanup():
    db.init_db()
    for user in db.query("SELECT id FROM user_account WHERE username LIKE ?", (PREFIX + "%",)):
        owner_id = user["id"]
        apartments = "(SELECT id FROM apartment WHERE owner_user_id = ?)"
        db.execute(
            "DELETE FROM guest WHERE reservation_id IN (SELECT id FROM reservation WHERE apartment_id IN "
            + apartments + ")",
            (owner_id,),
        )
        db.execute("DELETE FROM reservation WHERE apartment_id IN " + apartments, (owner_id,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM settings WHERE key = ?", (f"onboarding_dismissed_{owner_id}",))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


def _guest(reservation_id, **fields):
    now = db.utcnow()
    db.insert("guest", {"reservation_id": reservation_id, "created_at": now, "updated_at": now, **fields})


@pytest.fixture(scope="module")
def reg():
    _cleanup()
    tag = secrets.token_hex(4)
    username = f"{PREFIX}{tag}"
    owner_id = auth.create_account(f"{username}@example.test", "Register Host", role="host", username=username)
    now = db.utcnow()
    apartment_id = db.insert("apartment", {
        "internal_name": LONG_PROPERTY, "owner_user_id": owner_id, "permalink_token": f"reg0970-{tag}",
        "automation_mode": "manual", "default_purpose": "10", "active": 1, "created_at": now,
    })
    rid = db.insert("reservation", {
        "apartment_id": apartment_id, "source": "manual", "uid": f"reg0970-{tag}",
        "date_from": "2026-03-10", "date_to": "2026-03-15", "status": "active",
        "created_at": now, "updated_at": now,
    })
    # Complete, long name, tourism, filed.
    _guest(rid, first_name="Maximilian Alexander", surname=LONG_SURNAME, birth_date="15031985",
           nationality="DEU", doc_number="C01X00T47", res_street="Hauptstrasse 12", res_city="Berlin",
           res_country="DEU", purpose="10", signature_png=SIGNATURE, submit_state="sent",
           submitted_at="2026-03-16T09:00:00+00:00", stay_from="2026-03-10", stay_to="2026-03-15")
    # Incomplete: no document, no residence, not signed, not sent.
    _guest(rid, first_name="Ann", surname="Short", birth_date="01011990", nationality="USA",
           purpose="01", submit_state="pending", stay_from="2026-03-10", stay_to="2026-03-15")
    # Visa holder, business, rejected.
    _guest(rid, first_name="Olivia", surname="Smith", birth_date="02022000", nationality="GBR",
           doc_number="P1234567", visa_number="V998877", res_street="High Street 1", res_city="London",
           res_country="GBR", purpose="03", signature_png=SIGNATURE, submit_state="error",
           stay_from="2026-03-10", stay_to="2026-03-15")
    client = TestClient(app)
    assert login_as(client, username, url="/login?lang=en", follow_redirects=False).status_code == 303
    try:
        yield {"client": client, "cookie": client.cookies.get(auth.SESSION_COOKIE), "apartment": apartment_id}
    finally:
        _cleanup()


@pytest.fixture(scope="module")
def base(reg):
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
        pytest.fail("the 0970 test server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def _launch(playwright):
    try:
        return playwright.chromium.launch(**chromium_launch_kwargs())
    except Exception:
        if REQUIRE_BROWSER:
            raise
        pytest.skip("chromium is not available")


def _open(browser, base_url, reg, width, lang):
    context = browser.new_context(viewport={"width": width, "height": 1000}, reduced_motion="reduce")
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": reg["cookie"], "url": base_url + "/"}])
    context.add_init_script("try { localStorage.setItem('ubyhost-sidebar-collapsed', '0'); } catch (e) {}")
    page = context.new_page()
    page.goto(f"{base_url}/housebook?apartment={reg['apartment']}&lang={lang}")
    page.wait_for_load_state("networkidle")
    later = page.locator("#security-prompt [data-security-prompt-later]")
    if later.is_visible():
        later.click()
    page.evaluate("window.scrollTo(0, 0)")
    return context, page


def _shot(page, name):
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / name), full_page=True)


# ---------------------------------------------------------------- export

def test_csv_export_is_byte_identical_to_the_recorded_baseline(reg):
    """Statutory output: the CSV must be the same bytes before and after this change."""
    response = reg["client"].get(f"/housebook.csv?apartment={reg['apartment']}")
    assert response.status_code == 200
    body = response.content
    text = body.decode("utf-8-sig")
    # The statutory values stay in Czech and as codes, whatever the interface language.
    assert "Turistika" in text and "Obchodní" not in text.split("Short")[0]
    assert ";DEU;" in text and ";USA;" in text and "DEU-" in text
    if os.environ.get("UBYHOST_B12_RECORD") == "1":
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_bytes(body)
        print("recorded", len(body), hashlib.sha256(body).hexdigest())
        return
    assert GOLDEN.exists(), f"record the baseline first with UBYHOST_B12_RECORD=1 ({GOLDEN})"
    assert body == GOLDEN.read_bytes(), "the CSV export changed"


def test_register_rows_keep_every_export_column(reg):
    """The on-screen helper keys must not leak into the export columns."""
    from app import housebook

    rows = housebook.housebook_rows(reg["apartment"])
    assert len(rows) == 3
    for row in rows:
        for key, _label in housebook.HOUSEBOOK_COLUMNS:
            assert not key.startswith("_") and key in row
    assert [key for key, _ in housebook.HOUSEBOOK_COLUMNS][:4] == ["apartment", "idub", "stay_from", "stay_to"]


# ---------------------------------------------------------------- labels

def test_presentation_labels_follow_the_interface_language(reg):
    client = reg["client"]
    en = client.get(f"/housebook?apartment={reg['apartment']}&lang=en").text
    assert "Tourism" in en and "Germany (DEU)" in en and "Visiting family or friends" in en
    for czech in ("Turistika", "Obchodní", "Návštěva rodiny", "Německo"):
        assert czech not in en, czech
    cs = client.get(f"/housebook?apartment={reg['apartment']}&lang=cs").text
    assert "Turistika" in cs and "Podrobnosti" in cs and "Německo (DEU)" in cs
    assert "Tourism" not in cs
    vi = client.get(f"/housebook?apartment={reg['apartment']}&lang=vi").text
    assert validation.purpose_label("10", "vi") in vi and "(DEU)" in vi


# ---------------------------------------------------------------- browser

@pytest.mark.parametrize("lang", ["en", "cs"])
@pytest.mark.parametrize("width", [390, 768, 1024, 1280])
def test_register_is_readable(width, lang, base, reg):
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        context, page = _open(browser, base, reg, width, lang)
        try:
            overflow = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
            assert overflow <= 0, f"page overflows by {overflow}px at {width}px"
            _shot(page, f"register-{width}-{lang}.png")
            assert geometry_findings(page, width) == []
            if width < 1024:
                # Phones and tablets: stacked cards, no table at all, so nothing scrolls sideways.
                assert not page.locator(".housebook-scroll").is_visible()
                cards = page.locator(".stays-phone .card.stay")
                assert cards.count() == 3
                for i in range(3):
                    card = cards.nth(i)
                    assert card.is_visible()
                    box = card.bounding_box()
                    assert box["x"] >= 0 and box["x"] + box["width"] <= width + 0.5
                    # Identity and reporting status are readable together in the same card.
                    name_box = card.locator(".in b").bounding_box()
                    pill_box = card.locator(".pill").bounding_box()
                    for inner in (name_box, pill_box):
                        assert inner["height"] > 0
                        assert box["y"] <= inner["y"] and inner["y"] + inner["height"] <= box["y"] + box["height"] + 0.5
                        assert inner["x"] + inner["width"] <= width + 0.5
            else:
                assert page.locator(".housebook-scroll").is_visible()
                assert page.locator(".housebook-table thead th").count() == 6
                if width >= 1280:  # 1024 keeps the card's own sideways scroll for very wide rows
                    scroll = page.evaluate(
                        "() => { const e = document.querySelector('.housebook-scroll'); return e.scrollWidth - e.clientWidth; }")
                    assert scroll <= 1, f"the register table scrolls sideways by {scroll}px at {width}px"
                rows = page.locator(".housebook-table tbody tr")
                assert rows.count() == 3
                for i in range(3):
                    row = rows.nth(i)
                    name_box = row.locator(".col-guest strong").bounding_box()
                    pill_box = row.locator(".col-reported .pill").bounding_box()
                    assert name_box["x"] + name_box["width"] <= width and pill_box["x"] + pill_box["width"] <= width
                # Keyboard: Tab from the first row reaches its Details button, Enter opens the facts.
                first = rows.first
                first.focus()
                reached = False
                for _ in range(10):
                    page.keyboard.press("Tab")
                    if page.evaluate("() => document.activeElement.matches('.col-more > button[popovertarget]')"):
                        reached = True
                        break
                assert reached, "Details was not reachable with Tab"
                page.keyboard.press("Enter")
                opened = page.locator(".housebook-facts:popover-open")
                opened.wait_for(state="visible")
                assert "/housebook" in page.url and "/guests/" not in page.url
                text = opened.inner_text()
                for needle in (LONG_SURNAME, "15.03.1985", "C01X00T47", "Hauptstrasse 12"):
                    assert needle in text, needle
                if lang == "en":
                    assert "Tourism" in text and "Germany (DEU)" in text and "Date of birth" in text
                    for czech in ("Turistika", "Německo"):
                        assert czech not in text
                else:
                    assert "Turistika" in text and "Německo (DEU)" in text and "Datum narození" in text
                assert page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth") <= 0
                _shot(page, f"register-{width}-{lang}-open.png")
                # Escape closes it and puts focus back on the button.
                page.keyboard.press("Escape")
                assert page.locator(".housebook-facts:popover-open").count() == 0
                assert page.evaluate("() => document.activeElement.matches('.col-more > button[popovertarget]')")
                # Every record's facts are complete and follow the interface language.
                for i in range(3):
                    rows.nth(i).locator(".col-more > button[popovertarget]").click()
                    shown = page.locator(".housebook-facts:popover-open")
                    shown.wait_for(state="visible")
                    body = shown.inner_text()
                    if lang == "en":
                        for czech in ("Turistika", "Obchodní", "Návštěva rodiny", "Německo", "Spojené"):
                            assert czech not in body, czech
                    page.keyboard.press("Escape")
        finally:
            context.close()
            browser.close()
