"""Brief 1098: guest page polish (design-check findings 5 to 11).

Run with ``UBYHOST_REQUIRE_BROWSER=1`` so a missing browser fails instead of skipping.
Screenshots go to ``docs/tasks/screenshots-1098/``.
"""
from __future__ import annotations

import secrets
from pathlib import Path

import pytest

from app import i18n
from tests.test_guest_browser_e2e import _fee_seed
from tests.test_pay_rule_1084_browser import _add_guest, _guest_pages  # noqa: F401
from tests.test_pay_rule_1084_browser import _open as _open_stay
from tests.test_under15_signature_1090_browser import (  # noqa: F401
    ADULT,
    CHILD,
    EN,
    _new_url,
    _open,
    _send,
    _stay,
    _to_signature_step,
    browser,
    live_server,
)

__all__ = ["browser", "live_server"]

SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-1098"
WIDTHS = (390, 768, 1280)

# A custom property resolved to the colour the browser paints.
COLOUR_JS = """(name) => {
  const probe = document.createElement('div');
  probe.style.background = `var(${name})`;
  document.body.appendChild(probe);
  const value = getComputedStyle(probe).backgroundColor;
  probe.remove();
  return value;
}"""

GAPS_JS = """() => {
  const vis = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.height > 0 && r.width > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const step = [...document.querySelectorAll('[data-guest-step]')].find(vis);
  const content = el => Math.max(...[...el.querySelectorAll('*')].filter(vis)
    .filter(d => d.children.length === 0 || d.matches('label, input, select, textarea, .hint, .err'))
    .map(d => d.getBoundingClientRect().bottom));
  const top = el => el.getBoundingClientRect().top;
  const blocks = [];
  [...step.querySelectorAll('.g-row, .g-field')].filter(vis).forEach(el => {
    if (el.matches('.g-field') && (el.parentElement.closest('.g-row') || el.parentElement.closest('.g-field'))) return;
    if (el.matches('.g-row') && el.parentElement.closest('.g-row, .g-field')) return;
    if (el.matches('.g-row')) {
      const fields = [...el.children].filter(f => f.matches('.g-field') && vis(f));
      const tops = fields.map(top);
      if (fields.length > 1 && Math.max(...tops) - Math.min(...tops) > 2) {
        fields.forEach(f => blocks.push({name: f.querySelector('input, select, textarea')?.id || 'field', top: top(f), bottom: content(f)}));
        return;
      }
      blocks.push({name: 'row:' + fields.map(f => f.querySelector('input, select, textarea')?.id).join('+'),
                   top: top(el), bottom: Math.max(...fields.map(content))});
      return;
    }
    blocks.push({name: el.querySelector('input, select, textarea')?.id || 'field', top: top(el), bottom: content(el)});
  });
  blocks.sort((a, b) => a.top - b.top);
  const gaps = [];
  for (let i = 1; i < blocks.length; i++)
    gaps.push([blocks[i - 1].name + ' > ' + blocks[i].name, Math.round(blocks[i].top - blocks[i - 1].bottom)]);
  return gaps;
}"""


def _colour(page, name):
    return page.evaluate(COLOUR_JS, name)


def _style(page, selector, prop):
    return page.evaluate(
        "([s, p]) => { const el = document.querySelector(s); return el ? getComputedStyle(el)[p] : null; }",
        [selector, prop],
    )


def _fonts(page):
    page.evaluate("() => document.fonts.ready.then(() => true)")


def _no_sideways(page):
    assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")


def test_1098_5_even_field_gaps(live_server, browser, monkeypatch):
    token, stay = _stay(monkeypatch, "gaps")
    bad = {}
    for width in WIDTHS:
        page, _guest = _open(browser, live_server, token, stay, width)
        try:
            _fonts(page)
            gaps = page.evaluate(GAPS_JS)
            assert gaps, "no fields measured"
            if any(abs(g[1] - 16) > 1 for g in gaps):
                bad[width] = gaps
        finally:
            page.close()
    print("GAPS", bad)
    assert not bad, bad


def test_1098_6_dates_link(live_server, browser, monkeypatch):
    token, stay = _stay(monkeypatch, "dates")
    for width in WIDTHS:
        page, _guest = _open(browser, live_server, token, stay, width)
        try:
            links = page.locator("a.g-dates-link")
            assert links.count() == 2, page.content()[:600]
            visible = [i for i in range(2) if links.nth(i).is_visible()]
            assert len(visible) == 1, (width, visible)
            link = links.nth(visible[0])
            assert link.get_attribute("href") == f"/l/{token}?lang=en"
            assert link.evaluate("el => getComputedStyle(el).color") == _colour(page, "--g-accent")
            box = link.bounding_box()
            assert box["height"] >= 44, box
            if width == 1280:
                rail = page.locator(".g-checkin-rail").bounding_box()
                card = page.locator(".g-checkin-stay").bounding_box()
                assert rail["x"] - 1 <= box["x"] and box["x"] + box["width"] <= rail["x"] + rail["width"] + 1, (box, rail)
                assert 0 <= box["y"] - (card["y"] + card["height"]) <= 80, (box, card)
            else:
                line = page.locator("p.g-form-line").bounding_box()
                assert abs(box["y"] - (line["y"] + line["height"])) <= 24, (box, line)
            assert page.get_by_role("link", name=EN("wrong_dates")).count() == 1
            assert page.locator("a.g-back").count() == 0
            _no_sideways(page)
        finally:
            page.close()


def _assert_neutral(page, scope):
    checked = f"{scope} .checkline:has(input:checked)"
    accent, soft = _colour(page, "--g-accent"), _colour(page, "--g-accent-soft")
    background = _style(page, checked, "backgroundColor")
    border = _style(page, checked, "borderTopColor")
    for value in (background, border):
        assert value not in (accent, soft), (scope, value, accent, soft)
    assert background == _colour(page, "--surface-3"), (scope, background)
    unchecked = f"{scope} .checkline:not(:has(input:checked))"
    assert _style(page, unchecked, "backgroundColor") == _colour(page, "--g-surface-2")
    assert _style(page, f"{checked} input", "accentColor") == accent


def _child_role_ticked(browser, live_server, monkeypatch, width, part):
    """The child's own form after an adult was sent, role 'parent' ticked."""
    token, stay = _stay(monkeypatch, part)
    page, guest = _open(browser, live_server, token, stay, width)
    _to_signature_step(page, guest, "Grownup", ADULT)
    guest.sign()
    _send(page, stay, "Grownup")
    page.goto(_new_url(live_server, token, stay))
    _to_signature_step(page, guest, "Kid", CHILD)
    page.get_by_label(EN("sign_role_parent")).check()
    return page, guest


def _adult_signs_for(browser, live_server, monkeypatch, width, part):
    """The adult after a pending child, signing for them."""
    token, stay = _stay(monkeypatch, part)
    page, guest = _open(browser, live_server, token, stay, width)
    _to_signature_step(page, guest, "Kid", CHILD)
    _send(page, stay, "Kid")
    page.goto(_new_url(live_server, token, stay))
    _to_signature_step(page, guest, "Grownup", ADULT)
    guest.sign()
    page.locator("#sign-for-children").get_by_label(EN("sign_role_responsible")).check()
    return page, guest


def test_1098_7_selected_role_is_neutral(live_server, browser, monkeypatch):
    page, _guest = _child_role_ticked(browser, live_server, monkeypatch, 390, "role")
    try:
        scope = page.evaluate(
            "() => ['#sign-for-who', '#sign-for-role'].find(s => document.querySelector(s + ' .checkline:has(input:checked)'))"
        )
        assert scope, "no ticked role option"
        _assert_neutral(page, scope)
    finally:
        page.close()
    page, _guest = _adult_signs_for(browser, live_server, monkeypatch, 390, "rolefor")
    try:
        _assert_neutral(page, "#sign-for-children")
    finally:
        page.close()


STICKY_JS = """(targets) => {
  const btn = document.querySelector('[data-guest-step]:not([hidden]) > .g-btn[type=submit]')
    || [...document.querySelectorAll('[data-guest-step] > .g-btn[type=submit]')].find(b => b.getBoundingClientRect().height > 0);
  const b = btn.getBoundingClientRect();
  const H = window.innerHeight;
  const out = {btnTop: Math.round(b.top), btnBottom: Math.round(b.bottom), innerHeight: H, targets: {}};
  for (const sel of targets) {
    const el = document.querySelector(sel);
    if (!el) continue;
    const r = el.getBoundingClientRect();
    if (r.height === 0) continue;
    const inside = r.top >= 0 && r.bottom <= H;
    const clear = b.top >= r.bottom || b.bottom <= r.top;
    out.targets[sel] = {top: Math.round(r.top), bottom: Math.round(r.bottom), inside, clear};
  }
  return out;
}"""

TARGETS = ["#u15-note", "#sign-for-children-text", ".g-review h2", ".g-review h2 + .g-intro",
           ".g-legal-text > summary", "#legal_ack"]


def _check_position(geometry, where):
    assert geometry["btnBottom"] <= geometry["innerHeight"] + 1, (where, geometry)
    for sel, t in geometry["targets"].items():
        if t["inside"]:
            assert t["clear"], (where, sel, geometry)


@pytest.mark.parametrize("path", ["child", "adult_for"])
def test_1098_8_sticky_never_covers_legal_or_intro(live_server, browser, monkeypatch, path):
    opener = _child_role_ticked if path == "child" else _adult_signs_for
    page, _guest = opener(browser, live_server, monkeypatch, 390, f"sticky{path}")
    try:
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("() => window.innerHeight") == 844
        seen = {}
        for sel in TARGETS:
            if page.locator(sel).count() == 0 or not page.locator(sel).first.is_visible():
                continue
            page.evaluate("(s) => document.querySelector(s).scrollIntoView({block: 'start'})", sel)
            geometry = page.evaluate(STICKY_JS, TARGETS)
            seen[f"start {sel}"] = geometry
            _check_position(geometry, f"start {sel}")
        page.evaluate("() => window.scrollTo(0, 0)")
        page.locator("#legal_ack").focus()
        page.keyboard.press("Shift+Tab")
        page.keyboard.press("Tab")
        geometry = page.evaluate(STICKY_JS, TARGETS)
        assert page.evaluate("() => document.activeElement.id") == "legal_ack"
        seen["focus"] = geometry
        _check_position(geometry, "focus legal_ack")
        page.evaluate("() => window.scrollTo(0, document.documentElement.scrollHeight)")
        geometry = page.evaluate(STICKY_JS, TARGETS)
        seen["bottom"] = geometry
        _check_position(geometry, "bottom")
        readable = {"#legal_ack": False, ".g-review h2": False}
        height = page.evaluate("() => document.documentElement.scrollHeight")
        for y in range(0, height + 120, 120):
            page.evaluate("(y) => window.scrollTo(0, y)", y)
            geometry = page.evaluate(STICKY_JS, TARGETS)
            for sel in readable:
                t = geometry["targets"].get(sel)
                if t and t["inside"] and t["clear"]:
                    readable[sel] = True
        assert all(readable.values()), readable
        print(path, {k: (v["btnTop"], v["btnBottom"], v["targets"]) for k, v in seen.items()})
    finally:
        page.close()


def _fee_stay(part):
    token = f"browser-1098-{part}-{secrets.token_hex(4)}"
    stay = _fee_seed(token, nationality="DEU", declared=2)
    _add_guest(stay, "CZE")  # registered on another phone: no cookie here
    return token, stay


def test_1098_9_fee_box_one_level(live_server, browser, _guest_pages):  # noqa: F811
    token, stay = _fee_stay("fee")
    for width in WIDTHS:
        context, page = _open_stay(browser, live_server, token, stay, width)
        try:
            assert page.locator("#fee-pay").count() == 1
            assert _style(page, "#fee-pay", "backgroundColor") == _colour(page, "--g-surface")
            assert _style(page, "#fee-pay", "backgroundColor") != "rgb(243, 244, 248)"
            opts = page.evaluate("""() => [...document.querySelectorAll('#fee-pay .g-fee-opt')].map(el => {
              const s = getComputedStyle(el);
              return {radius: s.borderTopLeftRadius, bg: s.backgroundColor,
                      sides: ['Top', 'Right', 'Bottom', 'Left'].filter(k => parseFloat(s['border' + k + 'Width']) > 0).length};
            })""")
            assert opts, "no payment options"
            for opt in opts:
                assert opt["radius"] == "0px" and opt["bg"] == "rgba(0, 0, 0, 0)" and opt["sides"] < 4, opts
            pay = "#fee-pay .g-fee-panel--pay"
            assert _style(page, pay, "borderTopWidth") == "1px"
            assert _style(page, pay, "borderTopColor") not in (_colour(page, "--g-ink"), "rgb(0, 0, 0)")
            assert page.locator(f"{pay} .g-fee-dot").count() == 1
            assert page.locator(f"{pay} svg").count() == 0
            qr = page.locator("#fee-pay .g-fee-qr-img").bounding_box()
            assert round(qr["width"]) == 176 and round(qr["height"]) == 176, qr
            _no_sideways(page)
        finally:
            context.close()


@pytest.mark.parametrize("lang", ["en", "cs", "de", "es", "fr", "uk"])
def test_1098_10_no_duplicate_sentence(live_server, browser, _guest_pages, lang):  # noqa: F811
    t = i18n.translator(lang)
    expected = {
        "en": "Pay the stay fee above, then you can close this page.",
        "cs": "Poplatek za pobyt uhraďte výše, pak můžete stránku zavřít.",
        "de": "Zahlen Sie die Aufenthaltsabgabe oben, dann können Sie die Seite schließen.",
        "es": "Pague la tasa arriba y luego puede cerrar la página.",
        "fr": "Payez la taxe ci-dessus, puis vous pouvez fermer la page.",
        "uk": "Сплатіть збір за проживання вище, після цього можна закрити сторінку.",
    }
    body, title = t("all_done_body_fee"), t("all_done_title")
    assert body == expected[lang]
    rest = title.split(". ", 1)[-1]
    assert rest.lower() not in body.lower()
    token, stay = _fee_stay(f"dup{lang}")
    context, page = _open_stay(browser, live_server, token, stay, 390)
    try:
        page.goto(f"{live_server}/l/{token}/{stay}?lang={lang}", wait_until="networkidle")
        assert page.locator("#fee-pay").count() == 1
        text = page.inner_text("body")
        assert body in text
        assert text.count(rest) == 1, (lang, rest)
    finally:
        context.close()


ROWS_JS = """() => {
  const own = document.querySelector('details.g-summary > summary');
  const other = document.querySelector('.g-summary-row');
  const card = document.querySelector('details.g-card.g-summary');
  const pick = (el, keys) => { const s = getComputedStyle(el); return Object.fromEntries(keys.map(k => [k, s[k]])); };
  const text = ['fontSize', 'fontWeight', 'paddingLeft', 'paddingTop', 'minHeight'];
  const box = ['borderTopLeftRadius', 'borderTopWidth', 'backgroundColor'];
  const a = card.getBoundingClientRect(), b = other.getBoundingClientRect();
  return {ownText: pick(own, text), otherText: pick(other, text), ownBox: pick(card, box), otherBox: pick(other, box),
          left: [a.left, b.left], right: [a.right, b.right], gap: b.top - a.bottom,
          ownLabel: own.textContent, otherLabel: other.textContent};
}"""


def test_1098_11_done_guests_one_style(live_server, browser, _guest_pages):  # noqa: F811
    token, stay = _fee_stay("rows")
    saved = EN("summary_fold_saved")
    for width in WIDTHS:
        context, page = _open_stay(browser, live_server, token, stay, width)
        try:
            rows = page.evaluate(ROWS_JS)
            assert rows["ownText"] == rows["otherText"], rows
            assert rows["ownBox"] == rows["otherBox"], rows
            assert abs(rows["left"][0] - rows["left"][1]) <= 1 and abs(rows["right"][0] - rows["right"][1]) <= 1, rows
            assert 12 <= rows["gap"] <= 20, rows
            assert saved in rows["ownLabel"] and saved in rows["otherLabel"], rows
            assert page.locator(".g-tick").count() == 0 and page.locator(".g-person").count() == 0
        finally:
            context.close()


def test_1098_screenshots(live_server, browser, monkeypatch, _guest_pages):  # noqa: F811
    SHOTS.mkdir(parents=True, exist_ok=True)
    token, stay = _stay(monkeypatch, "shots")
    for width in WIDTHS:
        page, _guest = _open(browser, live_server, token, stay, width)
        try:
            _fonts(page)
            page.screenshot(path=str(SHOTS / f"form-{width}.png"), full_page=True)
        finally:
            page.close()
    for width in WIDTHS:
        page, _guest = _adult_signs_for(browser, live_server, monkeypatch, width, f"shot{width}")
        try:
            _fonts(page)
            if width == 390:
                page.set_viewport_size({"width": 390, "height": 844})
                page.locator("#legal_ack").scroll_into_view_if_needed()
                page.screenshot(path=str(SHOTS / "u15-role-390.png"), full_page=False)
            else:
                page.screenshot(path=str(SHOTS / f"u15-role-{width}.png"), full_page=True)
        finally:
            page.close()
    token, stay = _fee_stay("shots")
    for width in WIDTHS:
        context, page = _open_stay(browser, live_server, token, stay, width)
        try:
            _fonts(page)
            page.screenshot(path=str(SHOTS / f"stay-fee-{width}.png"), full_page=True)
        finally:
            context.close()
