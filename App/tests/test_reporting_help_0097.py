"""0097: Settings > Reporting & fees explained in plain words.

* Police reporting: the example police letter is linked next to the heading,
  one fine-print line replaces the request-letter generator, and every police
  field (IDUB, login, password, abbreviation, facility name, contact) has a
  ``?`` that says where the value is on the police letter.
* Stay fee: every field has a ``?`` in plain words (no annotated fee example
  exists, so none is linked).
* Stay fees list: the month summary sits in the page lane above the table.

Synthetic data only. Screenshots: ``UBYHOST_CAPTURE_0097=1`` writes
docs/tasks/0097-evidence/.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from app.host_i18n import STRINGS
from tests.browser_support import chromium_launch_kwargs
from tests.test_host_ux_acceptance import (  # noqa: F401  (fixtures and helpers)
    _context, _dismiss_prompt, _settle, _with_lang, acc, base, sync_api,
)

EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "0097-evidence"
CAPTURE = os.environ.get("UBYHOST_CAPTURE_0097") == "1"
SAMPLE = "/static/docs/ubyport-ws-credential-sample.pdf?v=20261004a"
POLICE_PAGE = "https://policie.gov.cz/reditelstvi-sluzby-cizinecke-policie/jake-jsou-moznosti-zasilani-dat-aplikaci-ubyport"
POLICE_HELP = {
    "uby_idub": "apartment.form.ubyport.idub_hint",
    "uby_ws_user": "apartment.form.ubyport.login_hint",
    "uby_ws_password": "apartment.form.ubyport.password_help",
    "uby_mark": "apartment.form.ubyport.mark_hint",
    "uby_name": "apartment.form.ubyport.name_hint",
    "uby_contact": "apartment.form.ubyport.contact_hint",
}
FEE_HELP = {
    "stay_fee_rate_czk": "apartment.form.stay_fee.rate_help",
    "stay_fee_cadence": "apartment.form.stay_fee.cadence_help",
    "stay_fee_vs": "apartment.form.stay_fee.vs_help",
    "stay-fee-account": "apartment.form.stay_fee.account_help",
    "stay_fee_authority_name": "apartment.form.stay_fee.authority_name_help",
    "stay_fee_authority_address": "apartment.form.stay_fee.authority_address_help",
    "stay_fee_authority_contact": "apartment.form.stay_fee.authority_contact_help",
    "stay_fee_authority_databox": "apartment.form.stay_fee.authority_databox_hint",
    "stay_fee_payee": "apartment.form.stay_fee.payee_hint",
    "stay_fee_instruction": "apartment.form.stay_fee.instruction_hint",
}


def _reporting(acc, lang):
    response = acc["client"].get(f"/apartments/{acc['p1']}?view=settings&section=reporting&lang={lang}")
    assert response.status_code == 200, response.text
    return response.text


def _section(html, section_id):
    return html.split(f'id="{section_id}"', 1)[1].split("\n    </section>", 1)[0]


def _escaped(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&#34;").replace("'", "&#39;")


def test_police_fields_have_plain_help_with_the_letter_line(acc):
    for lang in ("en", "cs"):
        section = _section(_reporting(acc, lang), "ubyport")
        for field, key in POLICE_HELP.items():
            assert f'aria-controls="{field}-help"' in section, (lang, field)
            assert _escaped(STRINGS[lang][key]) in section, (lang, field)
            assert f"{field}-help" in re.search(rf'<input [^>]*id="{field}"[^>]*>', section).group(0)
        # Where each value sits on the police letter, by its Czech line.
        assert "Zkratka ubytovacího zařízení" in STRINGS[lang]["apartment.form.ubyport.mark_hint"]
        assert "UBY-WS_" in STRINGS[lang]["apartment.form.ubyport.mark_hint"]
        assert "Ubytovací zařízení:" in STRINGS[lang]["apartment.form.ubyport.name_hint"]
        assert "IDUB:" in STRINGS[lang]["apartment.form.ubyport.idub_hint"]
        assert "Přihlašovací jméno:" in STRINGS[lang]["apartment.form.ubyport.login_hint"]
        assert "Přístupové heslo:" in STRINGS[lang]["apartment.form.ubyport.password_help"]
        # The saved-password state stays visible, not inside a tip.
        assert 'id="uby_ws_password-hint"' in section


def test_police_section_links_the_example_letter_and_the_police_page_once(acc):
    for lang in ("en", "cs"):
        html = _reporting(acc, lang)
        section = _section(html, "ubyport")
        head = section.split('id="uby_idub"', 1)[0]
        tag = re.search(r'<a [^>]*id="police-sample-link"[^>]*>([^<]*)</a>', head)
        assert tag and SAMPLE in tag.group(0) and 'target="_blank"' in tag.group(0)
        assert tag.group(1).strip() == STRINGS[lang]["apartment.form.ubyport.sample_link"]
        assert section.count(POLICE_PAGE) == 1
        assert "ws-request.txt" not in html and 'id="ws-request-body"' not in html


def test_stay_fee_fields_have_plain_help_and_no_invented_example(acc):
    for lang in ("en", "cs"):
        section = _section(_reporting(acc, lang), "stay-fee-settings")
        for field, key in FEE_HELP.items():
            assert f'aria-controls="{field}-help"' in section, (lang, field)
            assert _escaped(STRINGS[lang][key]) in section, (lang, field)
        # No annotated fee example ever existed; none is linked.
        assert ".pdf" not in section
        # Input names are unchanged.
        for name in ("stay_fee_rate_czk", "stay_fee_cadence", "stay_fee_vs", "account_prefix", "account_number",
                     "account_bank", "stay_fee_authority_name", "stay_fee_authority_address",
                     "stay_fee_authority_contact", "stay_fee_authority_databox", "stay_fee_payee",
                     "stay_fee_instruction"):
            assert f'name="{name}"' in section, name


_PAGE_JS = """() => {
  const vw = document.documentElement.clientWidth;
  const r = el => { if (!el) return null; const b = el.getBoundingClientRect();
    return {left: b.left, right: b.right, top: b.top, bottom: b.bottom, width: b.width}; };
  const police = document.querySelector('#ubyport');
  return {
    overflow: document.documentElement.scrollWidth > vw + 1, vw,
    police: r(police), title: r(police.querySelector('.property-section-title')),
    sample: r(document.querySelector('#police-sample-link')),
    fine: r(document.querySelector('.police-no-credentials')),
    fee: r(document.querySelector('#stay-fee-settings')),
  };
}"""

_TIP_JS = """(id) => { const t = document.getElementById(id); const b = t.getBoundingClientRect();
  return {visible: getComputedStyle(t).display !== 'none' && b.width > 0, left: b.left, right: b.right,
          vw: document.documentElement.clientWidth}; }"""

_LIST_JS = """() => { const r = sel => { const el = document.querySelector(sel); if (!el) return null;
    const b = el.getBoundingClientRect(); return {left: b.left, right: b.right, top: b.top, bottom: b.bottom, w: b.width}; };
  const panel = r('.panel.list-cards'); const toolbar = r('[data-filter-toolbar]');
  const filter = r('#list-filter-panel');
  return {summary: r('#fee-list-summary'), panel, toolbar, filter: filter && filter.w > 0 ? filter : toolbar,
          overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1}; }"""


def _shot(page, name, locator=None):
    if not CAPTURE or "-390" in name:
        return
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    if locator:
        # Evidence only: keep the phone app bar from covering an element shot.
        page.add_style_tag(content=".appbar { position: static !important; }")
    target = page.locator(locator) if locator else page
    full = {} if locator or name.startswith("tip-") else {"full_page": True}
    target.screenshot(path=str(EVIDENCE / f"{name}.png"), **full)


def test_reporting_and_fee_list_geometry_and_tips_in_the_browser(acc, base):
    failures = []
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        for lang in ("en", "cs"):
            for width in (360, 390, 1280):
                context = _context(browser, base, acc["cookie"], width=width, height=900, has_touch=width < 400)
                page = context.new_page()
                page.goto(base + _with_lang(f"/apartments/{acc['p1']}?view=settings&section=reporting", lang))
                _settle(page)
                _dismiss_prompt(page)
                label = (lang, width)
                geo = page.evaluate(_PAGE_JS)
                if geo["overflow"]:
                    failures.append((label, "page scrolls sideways"))
                for key in ("sample", "fine"):
                    box = geo[key]
                    if not box or box["width"] < 1:
                        failures.append((label, key, "not visible"))
                    elif box["left"] < geo["police"]["left"] - 1 or box["right"] > geo["police"]["right"] + 1:
                        failures.append((label, key, "outside the Police reporting panel", box))
                # The example link sits beside the heading on a wide lane, right under it on a phone.
                if geo["sample"] and geo["title"]:
                    gap = geo["sample"]["top"] - geo["title"]["bottom"]
                    if width >= 1280 and geo["sample"]["top"] > geo["title"]["bottom"]:
                        failures.append((label, "example link not beside the heading", geo["sample"], geo["title"]))
                    if gap > 24:
                        failures.append((label, "example link far from the heading", gap))
                for field in list(POLICE_HELP) + list(FEE_HELP):
                    button = page.locator(f'[aria-controls="{field}-help"]')
                    button.scroll_into_view_if_needed()
                    if width < 400:
                        button.tap()
                    else:
                        button.click()
                    tip = page.evaluate(_TIP_JS, f"{field}-help")
                    if not tip["visible"]:
                        failures.append((label, field, "tip does not open"))
                    elif tip["left"] < -0.5 or tip["right"] > tip["vw"] + 0.5:
                        failures.append((label, field, "tip outside the viewport", tip))
                    if field in ("uby_name", "stay_fee_vs"):
                        _shot(page, f"tip-{field}-{lang}-{width}")
                    page.keyboard.press("Escape")
                page.evaluate("window.scrollTo(0, 0)")
                page.locator("#ubyport").scroll_into_view_if_needed()
                _shot(page, f"police-reporting-{lang}-{width}", "#ubyport")
                _shot(page, f"stay-fee-{lang}-{width}", "#stay-fee-settings")

                page.goto(base + _with_lang("/stay-fees", lang))
                _settle(page)
                _dismiss_prompt(page)
                lst = page.evaluate(_LIST_JS)
                summary, panel, filt = lst["summary"], lst["panel"], lst["filter"]
                if lst["overflow"]:
                    failures.append((label, "fee list scrolls sideways"))
                if not summary or not panel:
                    failures.append((label, "fee list summary or panel missing"))
                else:
                    if abs(summary["left"] - panel["left"]) > 1 or summary["right"] > panel["right"] + 1:
                        failures.append((label, "fee summary outside the content lane", summary, panel))
                    if filt and abs(summary["left"] - filt["left"]) > 1:
                        failures.append((label, "fee summary not aligned with the filter row", summary, filt))
                    if summary["bottom"] > panel["top"] + 1:
                        failures.append((label, "fee summary not above the table", summary, panel))
                _shot(page, f"stay-fees-list-{lang}-{width}")
                context.close()
        browser.close()
    assert not failures, failures
