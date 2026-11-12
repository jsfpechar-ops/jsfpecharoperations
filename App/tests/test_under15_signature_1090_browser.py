"""Brief 1090 (K-L04): the guest form for a guest under 15, in a real browser.

A child under 15 on the arrival day sees one note instead of the pad; an adult
this phone saved confirms for them with a role tick, in either order. The
script only shows and hides; the server (brief 1089) decides again on save.

Browser tests; run with UBYHOST_REQUIRE_BROWSER=1 so a missing Chromium fails instead of skipping.
Screenshots go to docs/tasks/screenshots-1090/.
"""
from __future__ import annotations

import secrets
from datetime import date
from pathlib import Path

import pytest

from app import claim, db, i18n, mail
from tests.test_guest_browser_e2e import Guest, _fee_seed, browser, live_server  # noqa: F401

__all__ = ["browser", "live_server"]

WIDTHS = [390, 768, 1280]
SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-1090"
EN = i18n.translator("en")

STATE_JS = """() => {
  const el = id => document.getElementById(id);
  const shown = id => { const e = el(id); return !!e && e.getClientRects().length > 0; };
  const checked = name => Array.from(document.querySelectorAll('input[name="' + name + '"]:checked')).map(e => e.value);
  return {
    pad: shown('sig-canvas'),
    padHidden: el('sig-block').hidden,
    noteHidden: el('u15-block').hidden,
    note: shown('u15-note'),
    forChild: shown('sign-for-child'),
    forChildren: shown('sign-for-children'),
    sentence: el('sign-for-child-text') ? el('sign-for-child-text').textContent : '',
    childrenSentence: el('sign-for-children-text') ? el('sign-for-children-text').textContent : '',
    childRole: checked('child_sign_role'),
    adultRole: checked('sign_for_role'),
    status: el('sig-status') ? el('sig-status').textContent : '',
    scroll: document.documentElement.scrollWidth - window.innerWidth,
  };
}"""

GEOMETRY_JS = """() => {
  const card = document.getElementById('sig-canvas').closest('.g-card');
  const box = e => { const r = e.getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; };
  return {
    card: card.getBoundingClientRect().height,
    canvas: box(document.getElementById('sig-canvas')),
    fields: Array.from(card.querySelectorAll('.g-field')).filter(e => e.getClientRects().length)
      .map(e => { const r = e.getBoundingClientRect(); return [r.left, r.width]; }),
    scroll: document.documentElement.scrollWidth - window.innerWidth,
  };
}"""

BLOCK_STYLE_JS = """() => {
  const s = getComputedStyle(document.getElementById('sig-block'));
  return ['marginTop', 'marginRight', 'marginBottom', 'marginLeft', 'paddingTop', 'paddingRight',
          'paddingBottom', 'paddingLeft', 'borderTopWidth', 'borderRightWidth', 'borderBottomWidth',
          'borderLeftWidth'].map(k => s[k]);
}"""

GAPS_JS = """() => {
  const vis = e => e.getClientRects().length > 0;
  const rect = e => e.getBoundingClientRect();
  const out = { rows: [] };
  for (const id of ['sign-for-children', 'sign-for-child']) {
    const box = document.getElementById(id);
    if (!box || !vis(box)) continue;
    const rows = Array.from(box.querySelectorAll('.checkline')).filter(vis);
    for (let i = 1; i < rows.length; i += 1) out.rows.push(rect(rows[i]).top - rect(rows[i - 1]).bottom);
  }
  const text = document.getElementById('sign-for-children-text');
  const pad = document.querySelector('.g-sign');
  if (text && vis(text) && pad && vis(pad)) out.underPad = rect(text).top - rect(pad).bottom;
  const who = document.getElementById('sign-for-who');
  const role = document.getElementById('sign-for-role');
  if (who && role && vis(who)) out.groups = rect(role).top - rect(who).bottom;
  return out;
}"""

UNWRAP_JS = """() => {
  const block = document.getElementById('sig-block');
  while (block.firstChild) block.parentNode.insertBefore(block.firstChild, block);
  block.remove();
}"""


def _years_before(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year - years)
    except ValueError:  # 29 February
        return day.replace(year=day.year - years, day=28)


def _digits(day: date) -> str:
    return day.strftime("%d%m%Y")


ARRIVAL = claim.prague_today()  # the seeded booking starts today
CHILD = _digits(_years_before(ARRIVAL, 10))
TEEN = _digits(_years_before(ARRIVAL, 16))
ADULT = "01011980"
_DOC = iter(range(100, 999))


def _stay(monkeypatch, part):
    from app import config

    monkeypatch.setattr(config, "GUEST_PIN_REQUIRED", False)
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    token = f"browser-1090-{part}-{secrets.token_hex(4)}"
    stay = _fee_seed(token, signed=False, declared=6)
    return token, stay


def _new_url(live_server, token, stay, lang="en"):
    return f"{live_server}/l/{token}/{stay}/new?lang={lang}"


def _state(page):
    return page.evaluate(STATE_JS)


def _row(stay, first_name):
    rows = db.query("SELECT * FROM guest WHERE reservation_id = ?", (stay,))
    return next((r for r in rows if (r["first_name"] or "").upper() == first_name.upper()), None)


def _to_signature_step(page, guest, first, birth):
    """Fill the first two steps as a guest would and stop on the last step."""
    page.fill("#first_name", first)
    page.fill("#surname", "Testovic")
    page.click("#birth_date")
    page.keyboard.type(birth)
    guest.pick_country("nationality", "CZE")
    page.fill("#doc_number", f"SYN1090{next(_DOC)}")
    guest.next()
    page.fill("#res_street", "Examplova 5")
    page.fill("#res_city", "Testov")
    page.evaluate("() => { document.querySelector('#res_country').value = 'CZE'; }")
    guest.next()


def _send(page, stay, first):
    page.check("#legal_ack")
    page.locator("[data-guest-save]").click()
    for _ in range(100):
        row = _row(stay, first)
        if row is not None:
            page.wait_for_load_state("load")
            return row
        page.wait_for_timeout(100)
    raise AssertionError(f"{first} was not saved; status: {_state(page)['status']!r}")


def _shot(page, name):
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / name), full_page=True)


def _open(browser, live_server, token, stay, width=390, lang="en"):
    page = browser.new_page(viewport={"width": width, "height": 812})
    page.goto(_new_url(live_server, token, stay, lang))
    return page, Guest(page, width, lang=lang)


def test_a_child_after_the_adult_gets_the_note_and_the_role(live_server, browser, monkeypatch):
    token, stay = _stay(monkeypatch, "after")
    page, guest = _open(browser, live_server, token, stay)
    try:
        _to_signature_step(page, guest, "Grownup", ADULT)
        start = _state(page)
        assert start["pad"] and not start["note"] and not start["forChild"], start
        guest.sign()
        adult = _send(page, stay, "Grownup")

        page.goto(_new_url(live_server, token, stay))
        _to_signature_step(page, guest, "Kid", CHILD)
        state = _state(page)
        assert not state["pad"] and state["padHidden"], state
        assert state["note"] and state["forChild"], state
        assert EN("u15_note") in page.inner_text("#u15-block")
        assert state["sentence"] == EN("sign_for_child", names="Kid Testovic"), state["sentence"]
        assert state["childRole"] == [], "a role was ticked for the guest"
        assert state["scroll"] <= 0, state
        guest.check_layout("child note")
        assert not guest.problems, guest.problems

        page.get_by_label(EN("sign_role_parent")).check()
        child = _send(page, stay, "Kid")
        assert child["signed_for_guest_id"] == adult["id"]
        assert child["signed_for_role"] == "parent"
        assert (child["signature_png"] or "") == ""
    finally:
        page.close()


def test_an_adult_after_the_child_signs_for_them(live_server, browser, monkeypatch):
    token, stay = _stay(monkeypatch, "before")
    page, guest = _open(browser, live_server, token, stay)
    try:
        _to_signature_step(page, guest, "Kid", CHILD)
        state = _state(page)
        assert not state["pad"] and state["note"], state
        assert not state["forChild"], "role radios with no adult saved yet"
        assert page.locator("#u15-block input").count() == 0
        child = _send(page, stay, "Kid")
        assert child["signed_for_guest_id"] is None and (child["signature_png"] or "") == ""

        page.goto(_new_url(live_server, token, stay))
        _to_signature_step(page, guest, "Grownup", ADULT)
        state = _state(page)
        assert state["pad"] and not state["note"] and state["forChildren"], state
        assert "Kid Testovic".lower() in state["childrenSentence"].lower(), state
        assert state["adultRole"] == []
        guest.check_layout("adult signs for")
        assert not guest.problems, guest.problems
        guest.sign()
        page.get_by_label(EN("sign_role_responsible")).check()
        adult = _send(page, stay, "Grownup")
        linked = _row(stay, "Kid")
        assert linked["signed_for_guest_id"] == adult["id"]
        assert linked["signed_for_role"] == "responsible_adult"
        assert adult["signature_png"]
    finally:
        page.close()


def test_15_to_17_and_adults_see_todays_step(live_server, browser, monkeypatch):
    token, stay = _stay(monkeypatch, "teen")
    page, guest = _open(browser, live_server, token, stay)
    try:
        _to_signature_step(page, guest, "Teen", TEEN)
        state = _state(page)
        assert state["pad"] and not state["note"] and not state["forChild"], state
        assert not state["forChildren"]
        page.check("#legal_ack")
        page.locator("[data-guest-save]").click()
        page.wait_for_timeout(600)
        assert _row(stay, "Teen") is None, "a 16-year-old was saved without a signature"
        missing = page.get_attribute("#sig-status", "data-missing")
        assert missing and _state(page)["status"] == missing, _state(page)
        guest.sign()
        _send(page, stay, "Teen")

        # An adult with no pending child (the 16-year-old is no child here).
        page.goto(_new_url(live_server, token, stay))
        _to_signature_step(page, guest, "Grownup", ADULT)
        state = _state(page)
        assert state["pad"] and not state["note"], state
        assert page.locator("#sign-for-children").count() == 0
        assert page.locator("#u15-block input").count() == 0, "a 17-year-old signer was offered"
    finally:
        page.close()


def test_typing_and_changing_the_birth_date(live_server, browser, monkeypatch):
    token, stay = _stay(monkeypatch, "typing")
    # The page's rule is the stay's own arrival day. Read it from the seeded booking: a
    # clock taken at import can be a day behind when the shard crosses Prague midnight.
    arrival = date.fromisoformat(db.query_one("SELECT date_from FROM reservation WHERE id = ?", (stay,))["date_from"][:10])
    page, guest = _open(browser, live_server, token, stay)

    def hidden():
        s = page.evaluate(
            "() => [document.getElementById('sig-block').hidden, document.getElementById('u15-block').hidden]"
        )
        return tuple(s)

    def retype(digits, partial_expect):
        page.click("#birth_date")
        page.keyboard.press("Control+A")
        for key in digits[:-1]:
            page.keyboard.type(key)
            assert hidden() == partial_expect, f"changed on a half-typed date {page.input_value('#birth_date')!r}"
        page.keyboard.type(digits[-1])

    try:
        assert hidden() == (False, True), "a new form does not start with the pad"
        retype(CHILD, (False, True))
        assert hidden() == (True, False), "a 10-year-old keeps the pad"
        retype("01011990", (True, False))
        assert hidden() == (False, True), "a 30-year-old does not get the pad back"
        # An unknown day and month: under 15 only when the whole year is.
        retype(f"0000{ARRIVAL.year - 14}", (False, True))
        assert hidden() == (True, False)
        retype(f"0000{ARRIVAL.year - 15}", (True, False))
        assert hidden() == (False, True)
        # The day before the 15th birthday, and the birthday itself.
        fifteen = _years_before(ARRIVAL, 15)
        if fifteen.day < 28:
            retype(_digits(fifteen.replace(day=fifteen.day + 1)), (False, True))
            assert hidden() == (True, False), "14 on arrival keeps the pad"
        retype(_digits(fifteen), hidden())
        assert hidden() == (False, True), "15 on the arrival day loses the pad"

        # The pad that came back still takes a signature.
        page.fill("#first_name", "Later")
        page.fill("#surname", "Testovic")
        guest.pick_country("nationality", "CZE")
        page.fill("#doc_number", "SYN1090T")
        guest.next()
        page.fill("#res_street", "Examplova 5")
        page.fill("#res_city", "Testov")
        page.evaluate("() => { document.querySelector('#res_country').value = 'CZE'; }")
        guest.next()
        guest.sign()
        assert _send(page, stay, "Later")["signature_png"]
    finally:
        page.close()


@pytest.mark.parametrize("tick_again", [False, True])
def test_a_language_switch_keeps_the_note_and_unticks_the_role(live_server, browser, monkeypatch, tick_again):
    token, stay = _stay(monkeypatch, f"lang{int(tick_again)}")
    page, guest = _open(browser, live_server, token, stay)
    page.on("dialog", lambda dialog: dialog.accept())
    cs = i18n.translator("cs")
    try:
        _to_signature_step(page, guest, "Grownup", ADULT)
        guest.sign()
        adult = _send(page, stay, "Grownup")

        page.goto(_new_url(live_server, token, stay))
        _to_signature_step(page, guest, "Kid", CHILD)
        page.get_by_label(EN("sign_role_parent")).check()
        assert _state(page)["childRole"] == ["parent"]

        page.locator("[data-lang-menu] summary").click()
        with page.expect_navigation():
            page.locator('[data-lang-draft][lang="cs"]').click()
        assert page.get_attribute("html", "lang") == "cs"
        state = _state(page)
        assert state["note"] and not state["pad"], state
        assert cs("u15_note") in page.inner_text("#u15-block")
        assert state["sentence"] == cs("sign_for_child", names="Kid Testovic"), state["sentence"]
        assert state["childRole"] == [], "the role tick survived the language switch"

        if tick_again:
            page.get_by_label(cs("sign_role_responsible")).check()
        child = _send(page, stay, "Kid")
        if tick_again:
            assert child["signed_for_guest_id"] == adult["id"]
            assert child["signed_for_role"] == "responsible_adult"
        else:
            assert child["signed_for_guest_id"] is None
        assert (child["signature_png"] or "") == ""
    finally:
        page.close()


def test_a_childs_form_sends_without_javascript(live_server, browser, monkeypatch):
    token, stay = _stay(monkeypatch, "nojs")
    context = browser.new_context(java_script_enabled=False, viewport={"width": 390, "height": 812})
    page = context.new_page()
    try:
        page.goto(_new_url(live_server, token, stay))
        # No script: the server does not know the age yet, so both are there.
        assert page.locator("#sig-block").is_visible()
        assert page.locator("#u15-note").is_visible()
        page.fill("#first_name", "Kid")
        page.fill("#surname", "Testovic")
        page.fill("#birth_date", CHILD[:2] + "." + CHILD[2:4] + "." + CHILD[4:])
        page.select_option("#nationality", "CZE")
        page.fill("#doc_number", "SYN1090N")
        page.fill("#res_street", "Examplova 5")
        page.fill("#res_city", "Testov")
        page.select_option("#res_country", "CZE")
        page.check("#legal_ack")
        page.locator("[data-guest-save]").click()
        page.wait_for_load_state("load")
        row = _row(stay, "Kid")
        assert row is not None, page.inner_text("body")[-600:]
        assert (row["signature_png"] or "") == ""
    finally:
        context.close()


@pytest.mark.parametrize("width", WIDTHS)
def test_the_design_is_unchanged(live_server, browser, monkeypatch, width):
    token, stay = _stay(monkeypatch, f"design{width}")
    page, guest = _open(browser, live_server, token, stay, width)
    try:
        # An adult with no pending child: the wrapper must not be felt.
        _to_signature_step(page, guest, "Grownup", ADULT)
        assert page.evaluate(BLOCK_STYLE_JS) == ["0px"] * 12
        guest.check_layout(f"adult {width}")
        _shot(page, f"adult-{width}.png")
        before = page.evaluate(GEOMETRY_JS)
        assert before["scroll"] <= 0, before
        guest.sign()
        _send(page, stay, "Grownup")

        # The child after the adult: the note and the role radios.
        page.goto(_new_url(live_server, token, stay))
        _to_signature_step(page, guest, "Kid", CHILD)
        page.get_by_label(EN("sign_role_parent")).check()
        guest.check_layout(f"child note {width}")
        assert _state(page)["scroll"] <= 0
        gaps = page.evaluate(GAPS_JS)
        assert gaps["rows"] and min(gaps["rows"]) >= 12, gaps
        _shot(page, f"child-note-{width}.png")

        # Unwrap #sig-block on a fresh adult form: nothing may move.
        page.goto(_new_url(live_server, token, stay))
        _to_signature_step(page, guest, "Second", ADULT)
        wrapped = page.evaluate(GEOMETRY_JS)
        page.evaluate(UNWRAP_JS)
        bare = page.evaluate(GEOMETRY_JS)
        assert abs(wrapped["card"] - bare["card"]) <= 1, (wrapped, bare)
        assert all(abs(a - b) <= 1 for a, b in zip(wrapped["canvas"], bare["canvas"])), (wrapped, bare)
        assert len(wrapped["fields"]) == len(bare["fields"])
        for a, b in zip(wrapped["fields"], bare["fields"]):
            assert abs(a[0] - b[0]) <= 1 and abs(a[1] - b[1]) <= 1, (wrapped, bare)
        assert abs(wrapped["card"] - before["card"]) <= 1, (wrapped, before)
        assert not guest.problems, guest.problems
    finally:
        page.close()

    # The adult after a child: the sentence and the role radios under the pad.
    token, stay = _stay(monkeypatch, f"design{width}b")
    page, guest = _open(browser, live_server, token, stay, width)
    try:
        _to_signature_step(page, guest, "Kid", CHILD)
        _send(page, stay, "Kid")
        page.goto(_new_url(live_server, token, stay))
        _to_signature_step(page, guest, "Grownup", ADULT)
        guest.sign()
        page.get_by_label(EN("sign_role_responsible")).check()
        guest.check_layout(f"adult signs for {width}")
        assert _state(page)["scroll"] <= 0
        gaps = page.evaluate(GAPS_JS)
        assert gaps["rows"] and min(gaps["rows"]) >= 12, gaps
        assert gaps["underPad"] >= 12, gaps
        _shot(page, f"adult-signs-for-{width}.png")
        assert not guest.problems, guest.problems
    finally:
        page.close()


def test_two_adults_are_two_named_groups(live_server, browser, monkeypatch):
    token, stay = _stay(monkeypatch, "two")
    page, guest = _open(browser, live_server, token, stay)
    try:
        saved = {}
        for first in ("Grownup", "Auntie"):
            _to_signature_step(page, guest, first, ADULT)
            guest.sign()
            saved[first] = _send(page, stay, first)
            page.goto(_new_url(live_server, token, stay))
        _to_signature_step(page, guest, "Kid", CHILD)
        groups = page.evaluate(
            """() => Array.from(document.querySelectorAll('#u15-block [role=radiogroup]')).map(g => ({
                 id: g.id, name: document.getElementById(g.getAttribute('aria-labelledby')).textContent,
                 radios: Array.from(g.querySelectorAll('input[type=radio]')).map(r => r.name) }))"""
        )
        assert [g["id"] for g in groups] == ["sign-for-who", "sign-for-role"], groups
        assert groups[0]["name"] == EN("sign_for_who") and groups[0]["radios"] == ["signed_by"] * 2
        assert groups[1]["name"] == EN("sign_for_child", names="Kid Testovic")
        assert groups[1]["radios"] == ["child_sign_role"] * 2
        gaps = page.evaluate(GAPS_JS)
        assert len(gaps["rows"]) == 3 and min(gaps["rows"]) >= 12, gaps
        assert gaps["groups"] >= 12, gaps
        guest.check_layout("two adults")
        assert not guest.problems, guest.problems
        assert _state(page)["scroll"] <= 0

        # A role with no adult chosen: the form comes back and asks, on this step.
        page.get_by_label(EN("sign_role_parent")).check()
        page.check("#legal_ack")
        with page.expect_navigation():
            page.locator("[data-guest-save]").click()
        assert _row(stay, "Kid") is None
        error = page.locator("#signed_by-error")
        assert error.is_visible() and error.inner_text() == EN("sign_for_who_missing")
        assert _state(page)["childRole"] == ["parent"]
        gaps = page.evaluate(GAPS_JS)
        assert min(gaps["rows"]) >= 12 and gaps["groups"] >= 12, gaps
        # The summary's link lands on the adult choice.
        page.locator('a[href="#signed_by"]').click()
        page.wait_for_timeout(600)
        assert page.evaluate("() => document.activeElement.name") == "signed_by"
        _shot(page, "child-two-adults-390.png")

        page.locator('#sign-for-who input[type=radio]').nth(1).check()
        chosen = int(page.locator('#sign-for-who input[type=radio]').nth(1).get_attribute("value"))
        assert chosen in {saved["Grownup"]["id"], saved["Auntie"]["id"]}
        child = _send(page, stay, "Kid")
        assert child["signed_for_guest_id"] == chosen
        assert child["signed_for_role"] == "parent"
    finally:
        page.close()
