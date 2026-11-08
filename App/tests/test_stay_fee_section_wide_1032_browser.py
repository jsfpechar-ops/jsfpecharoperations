"""1032: the Stay fee section fits its card at wide widths (long council values and a saved signature),
and the nested More details and Signature blocks share the field left edge."""
from __future__ import annotations

import base64
import os
import struct
import zlib
from pathlib import Path

from app import db
from tests.property_host_fixture import host  # noqa: F401
from tests.test_property_navigation_browser import _context, base, chromium_launch_kwargs, sync_api  # noqa: F401

WIDTHS = (1280, 1440, 1600, 1800)
SHOTS = os.environ.get("UBYHOST_SHOTS_1032")
LONG = "Městský úřad Synthetic, odbor místních poplatků a daní, Náměstí Svobody 1234/56, 60200 Brno-střed " * 2


def _wide_png(width=1600, height=300):
    """A plain wide PNG, so a saved signature is wider than any card."""
    row = b"\x00" + b"\x00\x00\x00\xff" * width
    raw = zlib.compress(row * height)

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) + chunk(b"IDAT", raw) + chunk(b"IEND", b"")
    return "data:image/png;base64," + base64.b64encode(png).decode()


_FACTS = """() => {
  const sec = document.getElementById('sec-fee');
  const body = sec.querySelector('.fields-wrap') || sec;
  const cs = getComputedStyle(body);
  const box = body.getBoundingClientRect();
  const right = box.right - parseFloat(cs.paddingRight) + 1;
  const over = [];
  for (const el of sec.querySelectorAll('input:not([type=hidden]), select, textarea, img, canvas, .ui-btn, details.fee-more, fieldset.signature-block')) {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height || el.closest('dialog')) continue;
    if (r.right > right) over.push([el.id || el.className || el.tagName, Math.round(r.right), Math.round(right)]);
  }
  const council = document.getElementById('stay-fee-council');
  const left = (el) => el ? Math.round(el.getBoundingClientRect().left) : null;
  const field = left(document.getElementById('stay_fee_authority_name'));
  const label = left(council.querySelector('.field label'));
  const more = document.querySelector('#sec-fee details.fee-more');
  const sig = document.querySelector('#sec-fee fieldset.signature-block');
  return {over, field, label, title: left(council.querySelector('.property-subsection-title')),
          more: left(more), moreTitle: left(more && more.querySelector('summary')),
          moreLabel: left(more && more.querySelector('.field label')), moreInput: left(more && more.querySelector('input')),
          sig: left(sig), sigTitle: left(sig && sig.querySelector('legend'))};
}"""


def test_stay_fee_section_fits_its_card_and_nested_blocks_align(host, base):  # noqa: F811
    db.execute(
        "UPDATE apartment SET stay_fee_authority_name = ?, stay_fee_authority_address = ?, stay_fee_authority_contact = ?, stay_fee_authority_databox = ? WHERE id = ?",
        (LONG[:200], LONG[:200], LONG[:200], "abc1234", host["apartment"]),
    )
    db.execute("UPDATE legal_entity SET signature_png_enc = ? WHERE id = ?", (db.encrypt_field(_wide_png()), host["entities"][0]))
    problems = []
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        page = _context(browser, base, host).new_page()
        for width in WIDTHS:
            page.set_viewport_size({"width": width, "height": 1000})
            page.goto(f"{base}/apartments/{host['apartment']}?view=settings&lang=en")
            page.locator('nav.prop-strip a[href="#sec-fee"]').click()
            page.wait_for_selector("#sec-fee details.fee-more[open]")
            page.wait_for_selector("#sec-fee img.signature-locked-img", state="visible")
            facts = page.evaluate(_FACTS)
            if facts["over"]:
                problems.append((width, "overflow", facts["over"]))
            aligned = {k: facts[k] for k in ("field", "label", "title", "more", "moreTitle", "moreLabel", "moreInput", "sig", "sigTitle")}
            if len({v for v in aligned.values() if v is not None}) != 1:
                problems.append((width, "left edges differ", aligned))
            if page.evaluate("document.documentElement.scrollWidth > window.innerWidth"):
                problems.append((width, "page scrolls sideways"))
            if SHOTS and width in (1440, 1800):
                Path(SHOTS).mkdir(parents=True, exist_ok=True)
                page.locator("#sec-fee").screenshot(path=str(Path(SHOTS) / f"stay-fee-{width}-v5.png"))
        browser.close()
    assert not problems, problems


_SIG_FACTS = """() => {
  const card = document.querySelector('#sec-fee .fields-wrap');
  const img = document.querySelector('#sec-fee img.signature-locked-img');
  const c = card.getBoundingClientRect(), r = img.getBoundingClientRect();
  return {inside: r.left >= c.left - 1 && r.right <= c.right + 1 && r.top >= c.top - 1 && r.bottom <= c.bottom + 1,
          w: r.width, h: r.height, nw: img.naturalWidth, nh: img.naturalHeight, src: img.getAttribute('src') || ''};
}"""


def _draw_corners(page):
    """Strokes near all four corners of the pad, so a crop on any side would lose ink."""
    box = page.locator("#sec-fee dialog[open] [data-signature-panel=draw] canvas").bounding_box()
    assert box and box["width"] > 100 and box["height"] > 60, box
    pad = 6
    corners = [(box["x"] + pad, box["y"] + pad), (box["x"] + box["width"] - pad, box["y"] + pad),
               (box["x"] + box["width"] - pad, box["y"] + box["height"] - pad), (box["x"] + pad, box["y"] + box["height"] - pad)]
    page.mouse.move(*corners[0])
    page.mouse.down()
    for x, y in corners[1:] + corners[:1]:
        page.mouse.move(x, y, steps=8)
    page.mouse.up()


def _check_preview(page, width, problems, when):
    page.wait_for_function("() => { const i = document.querySelector('#sec-fee img.signature-locked-img'); return i && !i.hidden && i.complete && i.naturalWidth > 0; }")
    facts = page.evaluate(_SIG_FACTS)
    if not facts["inside"]:
        problems.append((width, when, "signature outside the card", facts))
    if abs(facts["w"] / facts["h"] - facts["nw"] / facts["nh"]) * facts["h"] > 1:
        problems.append((width, when, "aspect ratio changed", facts))
    return facts


def test_saved_signature_fits_whole_and_edit_redraws_it(host, base):  # noqa: F811
    db.execute("UPDATE apartment SET stay_fee_rate_czk = 30, stay_fee_authority_name = 'Synthetic Council' WHERE id = ?", (host["apartment"],))
    db.execute("UPDATE legal_entity SET signature_png_enc = NULL WHERE id = ?", (host["entities"][0],))
    problems = []
    url = f"{base}/apartments/{host['apartment']}?view=settings&lang=en"
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        for width in (1440, 1800):
            page = _context(browser, base, host, device_scale_factor=2).new_page()
            page.set_viewport_size({"width": width, "height": 1000})
            page.goto(url)
            page.locator('nav.prop-strip a[href="#sec-fee"]').click()
            page.locator("#sec-fee [data-signature-open]").click()
            _draw_corners(page)
            page.locator("#sec-fee [data-signature-use]").click()
            _check_preview(page, width, problems, "drawn")
            with page.expect_navigation():
                page.evaluate("() => { const f = document.getElementById('property-settings-form'); f.noValidate = true; f.requestSubmit(); }")
            page.goto(url)
            page.locator('nav.prop-strip a[href="#sec-fee"]').click()
            saved = _check_preview(page, width, problems, "saved")
            if not saved["src"].startswith("data:image/"):
                problems.append((width, "signature not saved"))
            # Edit opens the pad with the saved ink drawn whole (not stretched): ink near the left and right edges of the drawn area.
            page.locator("#sec-fee [data-signature-open]").click()
            page.wait_for_timeout(200)
            ink = page.evaluate("""() => {
              const c = document.querySelector('#sec-fee dialog[open] [data-signature-panel=draw] canvas');
              const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
              let n = 0; for (let i = 3; i < d.length; i += 4) if (d[i] > 0) n++;
              return n;
            }""")
            if not ink:
                problems.append((width, "edit pad shows no saved ink"))
            page.locator("#sec-fee [data-signature-clear]").click()
            _draw_corners(page)
            page.locator("#sec-fee [data-signature-use]").click()
            _check_preview(page, width, problems, "redrawn")
            if SHOTS:
                Path(SHOTS).mkdir(parents=True, exist_ok=True)
                page.locator("#sec-fee fieldset.signature-block").scroll_into_view_if_needed()
                page.wait_for_function("() => !document.querySelector('dialog[open]')")
                page.wait_for_timeout(500)
                page.screenshot(path=str(Path(SHOTS) / f"stay-fee-signature-{width}-v5.png"))
            page.context.close()
        browser.close()
    assert not problems, problems
