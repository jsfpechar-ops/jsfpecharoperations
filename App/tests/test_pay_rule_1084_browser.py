"""Brief 1084 (F2, P5): on the guest stay page the QR follows the stay, not the phone.

A German guest registered on this browser (owned cookie) and a Czech guest
registered elsewhere: the bank way shows the QR, as the completion mail does.
A stay with only a German guest: bank details, no QR.
"""
from __future__ import annotations

import secrets
from pathlib import Path

import pytest

from app import config, db, mail
from app.routes import guest as guest_routes
from tests.test_guest_browser_e2e import (  # noqa: F401  (fixtures and helpers)
    SIGNED_PNG, _fee_seed, browser, live_server,
)

SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-1084"

GEOMETRY_JS = """() => {
  const f = [], r = e => e.getBoundingClientRect();
  if (document.documentElement.scrollWidth > window.innerWidth) f.push('page scrolls sideways');
  const img = document.querySelector('#fee-pay .g-fee-qr-img');
  if (!img) return f.concat('no QR');
  const q = r(img);
  if (Math.round(q.width) !== 176 || Math.round(q.height) !== 176) f.push('QR is ' + q.width + 'x' + q.height);
  if (q.left < 0 || q.right > window.innerWidth) f.push('QR outside viewport');
  const box = img.closest('.g-fee-qr'), opt = img.closest('.g-fee-opt');
  const next = [box.nextElementSibling, opt.nextElementSibling].filter(Boolean);
  next.forEach(e => { const b = r(e);
    const apart = b.top >= q.bottom || b.bottom <= q.top || b.left >= q.right || b.right <= q.left;
    if (!apart) f.push('QR overlaps ' + (e.className || e.tagName)); });
  return f;
}"""


@pytest.fixture
def _guest_pages(monkeypatch):
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    monkeypatch.setattr(config, "GUEST_PIN_REQUIRED", False)  # the hub otherwise shows the PIN page
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)  # no claim page before the hub


def _add_guest(stay, nationality):
    now = db.utcnow()
    return db.insert("guest", {
        "reservation_id": stay, "first_name": "Bea", "surname": "Guest",
        "birth_date": "01011982", "nationality": nationality, "doc_number": "987654321",
        "res_street": "Hauptstrasse 2", "res_country": "DEU", "res_city": "Berlin",
        "purpose": "10", "signature_png": SIGNED_PNG, "created_at": now, "updated_at": now,
    })


def _open(browser, base, token, stay, width):  # noqa: F811
    context = browser.new_context(viewport={"width": width, "height": 900})
    own = db.query_one("SELECT id FROM guest WHERE reservation_id = ? AND nationality = 'DEU' "
                       "ORDER BY id LIMIT 1", (stay,))
    context.add_cookies([{"name": guest_routes.OWNED_COOKIE, "url": base,
                          "value": guest_routes._serializer().dumps([int(own["id"])])}])
    page = context.new_page()
    page.goto(f"{base}/l/{token}/{stay}?lang=en", wait_until="networkidle")
    return context, page


def test_the_qr_follows_the_stay_not_the_phone(live_server, browser, _guest_pages):  # noqa: F811
    token = f"browser-1084-mixed-{secrets.token_hex(4)}"
    stay = _fee_seed(token, nationality="DEU", declared=2)
    _add_guest(stay, "CZE")  # registered on another phone: no cookie here
    for width in (390, 768, 1280):
        context, page = _open(browser, live_server, token, stay, width)
        try:
            card = page.locator("#fee-pay")
            assert card.count() == 1, page.inner_text("body")[:400]
            assert card.locator(".g-fee-opt-h", has_text="Bank transfer").is_visible()
            assert card.locator(".g-fee-qr-img").count() == 1
            assert card.locator(".g-fee-qr-img").is_visible()
            assert page.evaluate(GEOMETRY_JS) == []
            if width == 390:
                SHOTS.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(SHOTS / "stay-qr-390.png"), full_page=True)
        finally:
            context.close()


def test_a_german_only_stay_shows_bank_details_without_qr(live_server, browser, _guest_pages):  # noqa: F811
    token = f"browser-1084-deu-{secrets.token_hex(4)}"
    stay = _fee_seed(token, nationality="DEU", declared=1)
    for width in (390, 768, 1280):
        context, page = _open(browser, live_server, token, stay, width)
        try:
            card = page.locator("#fee-pay")
            assert card.count() == 1, page.inner_text("body")[:400]
            assert card.locator(".g-fee-opt-h", has_text="Bank transfer").is_visible()
            assert card.locator(".g-fee-iban").is_visible()
            assert card.locator(".g-fee-qr-img").count() == 0
            assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")
        finally:
            context.close()
