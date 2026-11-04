"""0911: guest fee notice gate, guest RUIAN suggest route and picker, six-language key parity."""
import json
import re
import urllib.error
import urllib.parse
import urllib.request

from app import config, i18n, mail, ruian
from tests.test_guest_browser_e2e import _fee_seed, _seed, browser, live_server  # noqa: F401 (fixtures)

NEW_KEYS = [
    "legal_notice_fee_title", "legal_notice_fee_body", "legal_notice_fee_link",
    "ruian_suggest_label", "ruian_suggest_hint", "ruian_suggest_none",
]
LANGS = ["en", "cs", "de", "es", "fr", "uk"]
RESIDENCE_WORDS = re.compile(r"trval|permanent|resid|wohnsitz|domicil|empadron|aufenthaltsort", re.I)
FULL_ACT_LINK = 'href="https://www.e-sbirka.cz/sb/1990/565" rel="noopener" target="_blank"'
FAKE_SUGGESTIONS = [{
    "label": "Vodičkova 36/12, 110 00 Praha 1",
    "fields": {"addr_street": "Vodičkova", "addr_house_no": "36", "addr_orient_no": "12",
               "addr_obec": "Praha", "addr_obec_cast": "Praha 1"},
}]
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _get(url, params=None):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    try:
        with _OPENER.open(url, timeout=15) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")

def _set_country(page, code):
    """The visible control is a combobox over a hidden select; set the select and fire change."""
    page.evaluate("""(code) => { const s = document.getElementById('res_country');
        s.value = code; s.dispatchEvent(new Event('change', { bubbles: true })); }""", code)


def test_every_guest_language_has_the_0911_keys():
    for lang in LANGS:
        for key in NEW_KEYS:
            assert i18n.STRINGS[lang].get(key), (lang, key)


def test_fee_copy_never_mentions_residence():
    for lang in LANGS:
        for key in NEW_KEYS:
            assert not RESIDENCE_WORDS.search(i18n.STRINGS[lang][key]), (lang, key)


def _show_all_steps(page):
    """The guest wizard shows one step at a time (step.hidden). Unhide them all so the
    residence card and the legal notice can be checked; the picker itself is what is tested."""
    page.evaluate("() => document.querySelectorAll('[data-guest-step]').forEach(s => { s.hidden = false; })")


def test_fee_section_only_when_the_gate_is_open(live_server, monkeypatch):
    monkeypatch.setattr(config, "GUEST_PIN_REQUIRED", False)
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    token = "ruian-gate-open"
    stay = _fee_seed(token, signed=False)
    path = f"{live_server}/l/{token}/{stay}/new"
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    status, html = _get(path, {"lang": "en"})
    assert status == 200
    assert 'id="legal-fee-section"' in html
    assert FULL_ACT_LINK in html
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", False)
    assert 'id="legal-fee-section"' not in _get(path, {"lang": "en"})[1]
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    zero = _fee_seed("ruian-gate-zero", rate=0, signed=False)
    assert 'id="legal-fee-section"' not in _get(f"{live_server}/l/ruian-gate-zero/{zero}/new", {"lang": "en"})[1]


def test_ruian_suggest_route_guards(live_server, monkeypatch):
    monkeypatch.setattr(config, "GUEST_PIN_REQUIRED", False)
    token = "ruian-route-guards"
    _seed(token)
    url = f"{live_server}/l/{token}/ruian-suggest"
    monkeypatch.setattr(ruian, "enabled", lambda: False)
    assert _get(url, {"q": "Vodičkova Praha"})[0] == 404
    monkeypatch.setattr(ruian, "enabled", lambda: True)
    monkeypatch.setattr(ruian, "suggest", lambda q: FAKE_SUGGESTIONS)
    status, body = _get(url, {"q": "Vodičkova Praha"})
    assert status == 200 and json.loads(body) == FAKE_SUGGESTIONS
    monkeypatch.setattr(ruian, "rate_limited", lambda owner: True)
    assert _get(url, {"q": "Vodičkova Praha"})[0] == 429


def test_residence_pick_fills_obec_and_street_for_cz_only(live_server, browser, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "GUEST_PIN_REQUIRED", False)
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    monkeypatch.setattr(ruian, "suggest", lambda q: FAKE_SUGGESTIONS)
    monkeypatch.setattr(ruian, "enabled", lambda: True)  # the test env may switch RUIAN off
    token = "ruian-pick-js"
    stay = _seed(token)
    page = browser.new_page(viewport={"width": 390, "height": 800})
    try:
        page.goto(f"{live_server}/l/{token}/{stay}/new?lang=en")
        _set_country(page, "DEU")
        _show_all_steps(page)
        page.fill("#res_street", "Vodič")
        page.wait_for_timeout(800)
        assert page.locator("#ruian-suggest").is_hidden()
        _set_country(page, "CZE")
        page.fill("#res_street", "Vodič")
        page.wait_for_selector("#ruian-suggest-list button", state="visible")
        page.locator("#ruian-suggest-list button").first.click()
        assert page.input_value("#res_city") == "Praha"
        assert page.input_value("#res_street") == "Vodičkova 36/12"
        assert page.locator("#ruian-suggest").is_hidden()
    finally:
        page.close()
