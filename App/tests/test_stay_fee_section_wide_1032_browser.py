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
