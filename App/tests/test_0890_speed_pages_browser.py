"""0890: speed pages (stay-fee list, invoice picker, invoice form, housebook) in a real browser.

Covers the controls of 0845-0849 and 0889. The 0888 invoice price and payment defaults are not
on this branch yet, so nothing here checks them.
"""
from __future__ import annotations

import os
import re
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

from app import auth, claim, db, stay_fee, stay_fee_filing
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as
from tests.invoice_stay_helper import UID_PREFIX, drop_stays, make_stay, stay_form
from tests.v2_mockup import geometry_findings

WIDTHS = (320, 390, 768, 1024, 1280, 1440, 1920)
PREFIX = "speed-0890-"
SIGNATURE = "data:image/png;base64,AAAA"

# Josef's rules for one control group: 12 px between neighbours, text 16 px from its card edge
# (checked with a 15.5 px floor for rounding), no button over text, no text under 12 px.
PAGE_CHECK_JS = """
(sel) => {
  const root = document.querySelector(sel);
  if (!root) return ['missing ' + sel];
  const out = [];
  const vis = (e) => {
    const r = e.getBoundingClientRect(); const cs = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none';
  };
  const name = (e) => (e.textContent || e.getAttribute('aria-label') || e.tagName).trim().replace(/\\s+/g, ' ').slice(0, 40);
  const ctrls = [...root.querySelectorAll('a, button')].filter(vis);
  for (let i = 0; i < ctrls.length; i++) for (let j = i + 1; j < ctrls.length; j++) {
    const a = ctrls[i].getBoundingClientRect(), b = ctrls[j].getBoundingClientRect();
    const vo = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
    const ho = Math.min(a.right, b.right) - Math.max(a.left, b.left);
    if (vo > 0.5) {
      const gap = b.left >= a.right ? b.left - a.right : (a.left >= b.right ? a.left - b.right : -1);
      if (gap < 11.5) out.push('row gap ' + gap.toFixed(1) + 'px: ' + name(ctrls[i]) + ' / ' + name(ctrls[j]));
    }
    if (ho > 0.5) {
      const gap = b.top >= a.bottom ? b.top - a.bottom : (a.top >= b.bottom ? a.top - b.bottom : -1);
      if (gap < 11.5) out.push('column gap ' + gap.toFixed(1) + 'px: ' + name(ctrls[i]) + ' / ' + name(ctrls[j]));
    }
  }
  const texts = [...root.querySelectorAll('*')].filter(
    (e) => vis(e) && [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()));
  for (const t of texts) {
    const fs = parseFloat(getComputedStyle(t).fontSize);
    if (fs < 12) out.push('font ' + fs + 'px: ' + name(t));
  }
  const card = root.closest('.card');
  if (card) {
    const c = card.getBoundingClientRect();
    for (const t of texts) {
      const r = t.getBoundingClientRect();
      const d = Math.min(r.left - c.left, c.right - r.right, r.top - c.top, c.bottom - r.bottom);
      if (d < 15.5) out.push('text ' + d.toFixed(1) + 'px from card edge: ' + name(t));
    }
  }
  for (const c of ctrls) {
    const a = c.getBoundingClientRect();
    for (const t of texts) {
      if (c.contains(t) || t.contains(c)) continue;
      const r = t.getBoundingClientRect();
      const ox = Math.min(a.right, r.right) - Math.max(a.left, r.left);
      const oy = Math.min(a.bottom, r.bottom) - Math.max(a.top, r.top);
      if (ox > 0.5 && oy > 0.5) out.push('control over text: ' + name(c) + ' / ' + name(t));
    }
  }
  return out;
}
"""


def _launch(playwright):
    try:
        return playwright.chromium.launch(**chromium_launch_kwargs())
    except Exception:
        if REQUIRE_BROWSER:
            raise
        pytest.skip("chromium is not available")


def _cleanup():
    db.init_db()
    for user in db.query("SELECT id FROM user_account WHERE username LIKE ?", (PREFIX + "%",)):
        owner_id = user["id"]
        db.execute(
            "INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', '1') "
            "ON CONFLICT(key) DO UPDATE SET value = '1'"
        )
        db.execute(
            "DELETE FROM invoice_item WHERE invoice_id IN (SELECT id FROM invoice WHERE owner_user_id = ?)",
            (owner_id,),
        )
        db.execute("DELETE FROM invoice WHERE owner_user_id = ?", (owner_id,))
        drop_stays(owner_id)
        db.execute(
            "INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', '') "
            "ON CONFLICT(key) DO UPDATE SET value = ''"
        )
        db.execute(
            "DELETE FROM stay_fee_filing WHERE apartment_id IN (SELECT id FROM apartment WHERE owner_user_id = ?)",
            (owner_id,),
        )
        db.execute(
            "DELETE FROM guest WHERE reservation_id IN (SELECT id FROM reservation WHERE apartment_id IN "
            "(SELECT id FROM apartment WHERE owner_user_id = ?))",
            (owner_id,),
        )
        db.execute(
            "DELETE FROM reservation WHERE apartment_id IN (SELECT id FROM apartment WHERE owner_user_id = ?)",
            (owner_id,),
        )
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner_id,))
        db.execute(
            "DELETE FROM invoice_sequence WHERE legal_entity_id IN (SELECT id FROM legal_entity WHERE owner_user_id = ?)",
            (owner_id,),
        )
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM settings WHERE key = ?", (f"onboarding_dismissed_{owner_id}",))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


def _fee_property(owner_id, entity_id, name, rate):
    return db.insert("apartment", {
        "internal_name": name,
        "owner_user_id": owner_id,
        "legal_entity_id": entity_id,
        "addr_obec": "Praha 3",
        "active": 1,
        "stay_fee_rate_czk": rate,
        "stay_fee_vs": "123456",
        "stay_fee_authority_name": "Městský úřad",
        "stay_fee_council_account": "19-2000781379/0800",
        "stay_fee_council_iban": "CZ3008000000192000781379",
        "created_at": db.utcnow(),
    })


def _signed_stay(apartment_id, prev, tag):
    now = db.utcnow()
    rid = db.insert("reservation", {
        "apartment_id": apartment_id,
        "uid": f"{UID_PREFIX}fee-{tag}-{apartment_id}",
        "date_from": prev.replace(day=10).isoformat(),
        "date_to": prev.replace(day=14).isoformat(),
        "status": "active",
        "created_at": now,
        "updated_at": now,
    })
    db.insert("guest", {
        "reservation_id": rid,
        "first_name": "Ada",
        "surname": "Guest",
        "birth_date": "01011990",
        "nationality": "DEU",
        "signature_png": SIGNATURE,
        "created_at": now,
        "updated_at": now,
    })


@pytest.fixture(scope="module")
def speed_host():
    _cleanup()
    tag = secrets.token_hex(4)
    username = f"{PREFIX}{tag}"
    owner_id = auth.create_account(f"{username}@example.test", "Speed Host", role="host", username=username)
    entity_id = db.insert("legal_entity", {
        "name": "Speed 0890 s.r.o.",
        "seat": "Praha 1",
        "ico": "04656679",
        "registry_entry": "Fyzická osoba zapsaná v živnostenském rejstříku",
        "vat_status": "non_payer",
        "invoice_due_days": 14,
        "owner_user_id": owner_id,
        "created_at": db.utcnow(),
    })
    prev = stay_fee.previous_month(claim.prague_today())
    fee_ids = {
        "Fee A": _fee_property(owner_id, entity_id, "Fee A", 50),
        "Fee B": _fee_property(owner_id, entity_id, "Fee B", 50),
        "Fee C": _fee_property(owner_id, entity_id, "Fee C", 0),
    }
    _signed_stay(fee_ids["Fee A"], prev, tag)
    _signed_stay(fee_ids["Fee B"], prev, tag)

    client = TestClient(app)
    assert login_as(client, username, url="/login?lang=en", follow_redirects=False).status_code == 303
    s1 = make_stay(owner_id, entity_id=entity_id)
    response = client.post(
        "/invoices",
        data={
            "legal_entity_id": str(entity_id),
            **stay_form(s1, price="2500"),
            "buyer_name": "Speed Buyer",
            "paid_via": "cash",
            "lang": "cs",
        },
        follow_redirects=False,
    )
    assert response.status_code in (302, 303), response.text
    s2 = make_stay(owner_id, entity_id=entity_id)
    try:
        yield {
            "client": client,
            "cookie": client.cookies.get(auth.SESSION_COOKIE),
            "owner": owner_id,
            "entity": entity_id,
            "s2": s2,
            "fee_ids": fee_ids,
            "month": stay_fee.month_key(prev),
        }
    finally:
        _cleanup()


@pytest.fixture(scope="module")
def base(speed_host):
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
        pytest.fail("the 0890 test server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def _open(browser, base_url, cookie, path, width, height=1000):
    """Like _open_app in the 0710 suite, but adds ?lang=en or &lang=en when the path has a query."""
    context = browser.new_context(viewport={"width": width, "height": height}, reduced_motion="reduce")
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base_url + "/"}])
    context.add_init_script("try { localStorage.setItem('ubyhost-sidebar-collapsed', '0'); } catch (e) {}")
    page = context.new_page()
    urls: list[str] = []
    page.on("request", lambda request: urls.append(request.url))
    separator = "&" if "?" in path else "?"
    page.goto(f"{base_url}{path}{separator}lang=en")
    page.wait_for_load_state("networkidle")
    later = page.locator("#security-prompt [data-security-prompt-later]")
    if later.is_visible():
        later.click()
    page.evaluate("window.scrollTo(0, 0)")
    return context, page, urls


def _confirm_if_asked(page):
    proceed = page.locator("[data-confirm-proceed]")
    try:
        proceed.wait_for(state="visible", timeout=1500)
    except Exception:
        return False
    proceed.click()
    return True


def _paths(speed_host):
    month = speed_host["month"]
    entity = speed_host["entity"]
    s2 = speed_host["s2"]
    return {
        "stay-fees": (f"/stay-fees?month={month}", ".fee-bulk"),
        "invoice-picker": ("/invoices/new", ".invoice-quick-stays"),
        "invoice-form": (f"/invoices/new?reservation_id={s2}&entity={entity}", 'form:has(input[name="stay_price"])'),
        "housebook": ("/housebook", ".housebook-presets"),
    }


CASES = [(name, width) for name in ("stay-fees", "invoice-picker", "invoice-form", "housebook") for width in WIDTHS]


@pytest.mark.parametrize("page_name,width", CASES, ids=[f"{n}-{w}" for n, w in CASES])
def test_speed_pages_geometry(page_name, width, base, speed_host):
    path, root = _paths(speed_host)[page_name]
    roots = [root]
    if page_name == "stay-fees":
        roots = [".fee-bulk", ".fee-copy"]
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        context, page, _ = _open(browser, base, speed_host["cookie"], path, width)
        try:
            overflow = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
            assert overflow <= 0, f"horizontal overflow of {overflow}px at {width}px"
            for selector in roots:
                assert page.locator(selector).first.is_visible(), f"{selector} is not visible at {width}px"
                findings = page.evaluate(PAGE_CHECK_JS, selector)
                assert findings == [], f"{page_name} {selector} at {width}px: {findings}"
            if page_name in ("stay-fees", "housebook"):
                # The invoice pages still use the old shell; its shared chrome (skip link, help "?", bottom nav) is out of scope here.
                assert geometry_findings(page, width) == []
        finally:
            context.close()
            browser.close()


def test_speed_paths_end_to_end(base, speed_host):
    taps: dict[str, list[str]] = {}
    fee_ids = speed_host["fee_ids"]
    month = speed_host["month"]
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)

        # Stay fee: 5 taps for two properties, including the ZIP and the copy card.
        context, page, urls = _open(browser, base, speed_host["cookie"], f"/stay-fees?month={month}", 390)
        steps = ["open the stay fee list"]
        page.locator('form[action="/stay-fees/confirm-ready"] button').click()
        steps.append("confirm all ready")
        assert _confirm_if_asked(page)
        steps.append("confirm in dialog")
        page.wait_for_load_state("networkidle")
        page.wait_for_selector("text=Periods saved: 2", timeout=10000)
        zip_link = page.locator('a[href^="/stay-fees/pdfs.zip"]')
        assert zip_link.is_visible()
        with page.expect_download() as download:
            zip_link.click()
        steps.append("download the ZIP")
        assert download.value.suggested_filename.endswith(".zip")
        assert stay_fee_filing.latest(fee_ids["Fee A"], month) is not None
        assert stay_fee_filing.latest(fee_ids["Fee B"], month) is not None
        copy_card = page.locator(".fee-copy").first
        assert copy_card.is_visible()
        copy_card.locator("button, a", has_text="Use this setup").first.click()
        steps.append("use this setup")
        _confirm_if_asked(page)
        page.wait_for_load_state("networkidle")
        rate_c = db.query_one("SELECT stay_fee_rate_czk FROM apartment WHERE id = ?", (fee_ids["Fee C"],))
        rate_a = db.query_one("SELECT stay_fee_rate_czk FROM apartment WHERE id = ?", (fee_ids["Fee A"],))
        assert rate_c["stay_fee_rate_czk"] == rate_a["stay_fee_rate_czk"]
        taps["stay fee"] = steps
        assert urls and not [u for u in urls if "/submit" in u]
        context.close()

        # Invoice picker: 2 taps to the form (the price defaults tap comes with 0888).
        context, page, urls = _open(browser, base, speed_host["cookie"], "/invoices/new", 390)
        steps = ["open the invoice picker"]
        page.locator(f'.invoice-quick-stays a[href="/invoices/new?reservation_id={speed_host["s2"]}"]').click()
        steps.append("quick link for the stay")
        page.wait_for_url(re.compile(r"reservation_id=\d+"))
        page.wait_for_load_state("networkidle")
        assert page.locator('input[name="stay_price"]').is_visible()
        taps["invoice"] = steps
        assert not [u for u in urls if "/submit" in u]
        context.close()

        # Housebook: 2 taps.
        context, page, urls = _open(browser, base, speed_host["cookie"], "/housebook", 390)
        steps = ["open housebook"]
        page.locator(".housebook-presets a", has_text="Last month").click()
        steps.append("Last month")
        page.wait_for_url(re.compile(r"from=.*to="))
        page.wait_for_load_state("networkidle")
        assert "from=" in page.url and "to=" in page.url
        taps["housebook"] = steps
        assert not [u for u in urls if "/submit" in u]
        context.close()
        browser.close()

    for name, steps in taps.items():
        print(f"TAPS {name}: {len(steps)} {steps}")
    assert len(taps["stay fee"]) == 5
    assert len(taps["invoice"]) == 2
    assert len(taps["housebook"]) == 2


def test_speed_screenshots(base, speed_host):
    """Only when UBYHOST_SHOTS_DIR is set (returns early otherwise)."""
    shots = os.environ.get("UBYHOST_SHOTS_DIR")
    if not shots:
        return
    out = Path(shots)
    out.mkdir(parents=True, exist_ok=True)
    names = {
        "stay-fees": "stay-fees-390.png",
        "invoice-picker": "invoice-picker-390.png",
        "invoice-form": "invoice-form-390.png",
        "housebook": "housebook-390.png",
    }
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        for page_name, path_root in _paths(speed_host).items():
            context, page, _ = _open(browser, base, speed_host["cookie"], path_root[0], 390, height=844)
            page.screenshot(path=str(out / names[page_name]), full_page=True)
            context.close()
        browser.close()
