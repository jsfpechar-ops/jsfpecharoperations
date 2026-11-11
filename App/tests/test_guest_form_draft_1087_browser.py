"""Brief 1087: the guest form autosaves its draft and welcomes the guest back.

Browser tests; run with UBYHOST_REQUIRE_BROWSER=1 so a missing Chromium fails instead of skipping.
Test g writes docs/tasks/screenshots-1087/{fresh,welcome-back}-{390,768,1280}.png.
"""
from __future__ import annotations

import secrets
from pathlib import Path

import pytest

from app import db, i18n, mail
from tests.test_guest_browser_e2e import Guest, _fee_seed, browser, live_server  # noqa: F401
from tests.test_guest_form_input_browser import _fill_step_one, _fill_step_two

__all__ = ["browser", "live_server"]

SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-1087"
STEP_ONE = ("first_name", "surname", "birth_date", "nationality", "doc_number")
NEVER_POSTED = ("signature", "passport_photo", "legal_ack")
HIDE_JS = """() => {
  Object.defineProperty(document, "visibilityState", {configurable: true, get: () => "hidden"});
  document.dispatchEvent(new Event("visibilitychange"));
}"""
VALUES_JS = "(names) => names.map(n => document.getElementById('guest-form').elements[n].value)"
EMPTY_EXTRAS_JS = """() => {
  const sig = document.querySelector('#signature');
  const photo = document.querySelector('#passport_photo');
  return (!sig || sig.value === '') && (!photo || photo.files.length === 0);
}"""


def _open_url(live_server, monkeypatch, part, lang="en", declared=1):
    """As ``_open_url`` of test_guest_form_input_browser, with the headcount settable."""
    from app import config

    monkeypatch.setattr(config, "GUEST_PIN_REQUIRED", False)
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    token = f"browser-1087-{part}-{secrets.token_hex(4)}"
    stay = _fee_seed(token, signed=False)
    db.update("reservation", stay, {"declared_guests": declared})
    return f"{live_server}/l/{token}/{stay}/new?lang={lang}"


def _watch(page):
    """Every /draft request of the page, in order, with the other POSTs."""
    posts = []
    page.on("request", lambda r: posts.append(r) if r.method == "POST" else None)
    return posts


def _drafts(posts):
    return [r for r in posts if "/draft" in r.url]


def _typed_then_saved(page, guest, **names):
    """Fill step one and wait for the autosave to be answered."""
    with page.expect_response("**/draft*", timeout=10000) as answer:
        _fill_step_one(page, guest, **names)
    assert answer.value.status == 204
    return page.evaluate(VALUES_JS, list(STEP_ONE))


def _welcome(page):
    return page.locator("#draft-welcome")


def test_1087_close_and_return_brings_the_answers_back_only_on_this_device(live_server, browser, monkeypatch):
    url = _open_url(live_server, monkeypatch, "return")
    context = browser.new_context(viewport={"width": 390, "height": 812})
    other = browser.new_context(viewport={"width": 390, "height": 812})
    try:
        page = context.new_page()
        guest = Guest(page, 390)
        page.goto(url)
        assert _welcome(page).count() == 0
        first_step = guest.step()
        typed = _typed_then_saved(page, guest)
        assert typed[0] == "Synthetica" and typed[1] == "Testovic" and typed[4] == "SYN1109X", typed
        page.close()

        page = context.new_page()
        guest = Guest(page, 390)
        page.goto(url)
        assert _welcome(page).is_visible()
        assert _welcome(page).inner_text().strip() == "Welcome back. Continue where you left off."
        assert page.evaluate(VALUES_JS, list(STEP_ONE)) == typed
        assert page.evaluate(EMPTY_EXTRAS_JS), "the signature or the photo came back"
        assert guest.step() == first_step
        assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")
        guest.check_layout("welcome back 390")
        assert not guest.problems, guest.problems

        # b. another device
        stranger = other.new_page()
        stranger.goto(url)
        assert _welcome(stranger).count() == 0
        assert stranger.input_value("#first_name") == ""
        assert stranger.input_value("#surname") == ""
    finally:
        context.close()
        other.close()


def test_1087_autosave_waits_and_never_posts_the_tick_signature_or_photo(live_server, browser, monkeypatch):
    url = _open_url(live_server, monkeypatch, "debounce")
    context = browser.new_context(viewport={"width": 390, "height": 812})
    try:
        page = context.new_page()
        posts = _watch(page)
        page.goto(url)
        # The tick alone is not a draft field: nothing is posted.
        page.evaluate(
            "() => { const el = document.querySelector('#legal_ack'); el.checked = true;"
            " el.dispatchEvent(new Event('input', {bubbles: true}));"
            " el.dispatchEvent(new Event('change', {bubbles: true})); }"
        )
        page.wait_for_timeout(3000)
        assert _drafts(posts) == [], "the legal tick posted a draft"

        # Ten keystrokes inside three seconds: at most one write in that time.
        started = len(_drafts(posts))
        with page.expect_response("**/draft*", timeout=10000) as answer:
            page.type("#surname", "Testovicka", delay=250)
            page.wait_for_timeout(500)
            assert len(_drafts(posts)) - started <= 1
        assert answer.value.status == 204
        page.wait_for_timeout(3000)
        sent = _drafts(posts)
        assert len(sent) == 1, [r.url for r in sent]
        body = sent[0].post_data or ""
        assert 'name="surname"' in body and "Testovicka" in body
        assert 'name="draft_owned"' in body and 'name="_csrf"' in body
        for name in NEVER_POSTED:
            assert name not in body, name

        # Typing again straight away waits for the 15 second gap.
        page.type("#first_name", "Syn")
        page.wait_for_timeout(3500)
        assert len(_drafts(posts)) == 1, "a second write inside 15 seconds"
    finally:
        context.close()


@pytest.mark.parametrize("party", [False, True])
def test_1087_hiding_the_page_flushes_once(live_server, browser, monkeypatch, party):
    url = _open_url(live_server, monkeypatch, "hide", declared=None if party else 1)
    context = browser.new_context(viewport={"width": 390, "height": 812})
    try:
        page = context.new_page()
        posts = _watch(page)
        answers = []
        page.on("response", lambda r: answers.append(r.status) if "/draft" in r.url else None)
        page.goto(url)
        assert (page.locator("#party_size").count() == 1) is party
        page.fill("#first_name", "Synthetica")
        page.evaluate(HIDE_JS)
        page.wait_for_timeout(1200)
        sent = _drafts(posts)
        assert len(sent) == 1, [r.url for r in sent]
        assert answers == [204], answers
        body = sent[0].post_data or ""
        assert "Synthetica" in body
        assert ('name="party_size"' in body) is party
        # Hidden again with nothing typed in between: nothing to send.
        page.evaluate(HIDE_JS)
        page.wait_for_timeout(2500)
        assert len(_drafts(posts)) == 1
    finally:
        context.close()


def test_1087_a_language_switch_flushes_and_keeps_autosave_on(live_server, browser, monkeypatch):
    url = _open_url(live_server, monkeypatch, "lang")
    context = browser.new_context(viewport={"width": 390, "height": 812})
    try:
        page = context.new_page()
        posts = _watch(page)
        page.on("dialog", lambda dialog: dialog.accept())
        guest = Guest(page, 390)
        page.goto(url)
        _typed_then_saved(page, guest)
        before = len(_drafts(posts))
        page.fill("#surname", "Testovicova")
        page.locator("[data-lang-menu] summary").click()
        with page.expect_navigation():
            page.locator('[data-lang-draft][lang="cs"]').click()
        kinds = ["draft" if "/draft" in r.url else "relang" if "/relang" in r.url else "" for r in posts]
        assert "relang" in kinds, kinds
        flushed = [k for k in kinds[: kinds.index("relang")] if k == "draft"]
        assert len(flushed) == before + 1, kinds
        assert "Testovicova" in (_drafts(posts)[-1].post_data or "")

        assert page.get_attribute("html", "lang") == "cs"
        assert page.get_attribute("#guest-form", "data-draft-url")
        assert _welcome(page).count() == 0
        with page.expect_response("**/draft*", timeout=10000) as answer:
            page.fill("#first_name", "Syntheticka")
        assert answer.value.status == 204
        typed = page.evaluate(VALUES_JS, list(STEP_ONE))
        page.close()

        page = context.new_page()
        page.goto(url.replace("lang=en", "lang=cs"))
        assert _welcome(page).inner_text().strip() == i18n.translator("cs")("draft_welcome")
        assert page.evaluate(VALUES_JS, list(STEP_ONE)) == typed
        assert typed[0] == "Syntheticka" and typed[1] == "Testovicova"
    finally:
        context.close()


def test_1087_after_a_send_the_next_person_starts_empty(live_server, browser, monkeypatch):
    url = _open_url(live_server, monkeypatch, "sent", declared=2)
    context = browser.new_context(viewport={"width": 390, "height": 812})
    try:
        page = context.new_page()
        guest = Guest(page, 390)
        page.goto(url)
        _typed_then_saved(page, guest)
        guest.next()
        _fill_step_two(page, guest)
        guest.next()
        guest.sign()
        page.check("#legal_ack")
        page.press("#legal_ack", "Enter")
        # Person 1 of 2 is sent: the form opens again for the next person.
        page.wait_for_url("**/new?*saved=1*", timeout=10000)
        page.wait_for_load_state()

        page.goto(url)
        assert _welcome(page).count() == 0
        assert page.get_attribute("#guest-form", "data-draft-owned") == "1"
        # Nothing of person 1's draft: the given name, birth date and document
        # are empty. (The surname is the 0838 family prefill from the saved
        # guest, upper-cased as stored, not the draft.)
        assert page.evaluate(VALUES_JS, ["first_name", "birth_date", "doc_number"]) == ["", "", ""]

        guest = Guest(page, 390)
        with page.expect_response("**/draft*", timeout=10000) as answer:
            page.fill("#first_name", "Secunda")
            page.fill("#surname", "Druha")
            page.fill("#doc_number", "SYN1087Y")
        assert answer.value.status == 204
        page.close()

        page = context.new_page()
        page.goto(url)
        assert _welcome(page).is_visible()
        assert page.evaluate(VALUES_JS, ["first_name", "surname", "doc_number"]) == [
            "Secunda",
            "Druha",
            "SYN1087Y",
        ]
        assert page.input_value("#birth_date") == ""
        assert page.get_attribute("#guest-form", "data-draft-owned") == "1"
    finally:
        context.close()


GEOMETRY_JS = """() => {
  const card = document.querySelector('[data-guest-step]');
  const box = (el) => { const r = el.getBoundingClientRect(); return {top: r.top + scrollY, left: r.left, width: r.width, height: r.height}; };
  const line = document.querySelector('#draft-welcome');
  let lineSpace = 0, lineHeight = 0;
  if (line) {
    const style = getComputedStyle(line);
    lineHeight = line.getBoundingClientRect().height;
    lineSpace = lineHeight + parseFloat(style.marginTop) + parseFloat(style.marginBottom);
  }
  return {
    first: box(document.querySelector('#first_name')),
    card: box(card),
    fields: Array.from(card.querySelectorAll('.g-field')).map(box),
    lineSpace: lineSpace,
    lineHeight: lineHeight,
  };
}"""


@pytest.mark.parametrize("width", [390, 768, 1280])
def test_1087_the_form_design_is_the_same_apart_from_the_one_line(live_server, browser, monkeypatch, width):
    url = _open_url(live_server, monkeypatch, f"design{width}")
    context = browser.new_context(viewport={"width": width, "height": 812})
    other = browser.new_context(viewport={"width": width, "height": 812})
    SHOTS.mkdir(parents=True, exist_ok=True)
    try:
        fresh = other.new_page()
        fresh.goto(url)
        fresh.wait_for_load_state("networkidle")
        fresh.screenshot(path=str(SHOTS / f"fresh-{width}.png"), full_page=True)
        untouched = fresh.evaluate(GEOMETRY_JS)

        page = context.new_page()
        page.goto(url)
        _typed_then_saved(page, Guest(page, width))
        page.close()
        page = context.new_page()
        page.goto(url)
        page.wait_for_load_state("networkidle")
        assert _welcome(page).is_visible()
        page.screenshot(path=str(SHOTS / f"welcome-back-{width}.png"), full_page=True)
        assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")

        with_line = page.evaluate(GEOMETRY_JS)
        page.evaluate("() => document.querySelector('#draft-welcome').remove()")
        without = page.evaluate(GEOMETRY_JS)
        # The line sits above the first card: it pushes the card down and changes
        # nothing inside it. The push is measured, not summed from the line's
        # margins: those can collapse with the column's edge (1098).
        space = with_line["card"]["top"] - without["card"]["top"]
        assert with_line["lineHeight"] - 1 <= space <= with_line["lineSpace"] + 1, (with_line, without)
        assert abs((with_line["first"]["top"] - without["first"]["top"]) - space) <= 1, (with_line, without)
        assert abs(with_line["card"]["height"] - without["card"]["height"]) <= 1
        assert len(with_line["fields"]) == len(without["fields"]) > 0
        for a, b in zip(with_line["fields"], without["fields"]):
            assert abs(a["left"] - b["left"]) <= 0.5 and abs(a["width"] - b["width"]) <= 0.5, (a, b)

        # Without the line the restored page sits exactly where a fresh one does.
        assert abs(without["card"]["top"] - untouched["card"]["top"]) <= 1
        # (The card's height depends on the answers, a Czech guest has no visa
        # box, so only what the answers cannot move is compared.)
        for key in ("left", "width"):
            assert abs(without["first"][key] - untouched["first"][key]) <= 0.5, key
            assert abs(without["card"][key] - untouched["card"][key]) <= 0.5, key
    finally:
        context.close()
        other.close()


def test_1087_without_javascript_there_is_no_draft(live_server, browser, monkeypatch):
    url = _open_url(live_server, monkeypatch, "nojs")
    context = browser.new_context(java_script_enabled=False, viewport={"width": 390, "height": 812})
    try:
        page = context.new_page()
        posts = _watch(page)
        page.goto(url)
        assert page.locator("#guest-form").count() == 1
        page.fill("#first_name", "Synthetica")
        page.fill("#surname", "Testovic")
        page.wait_for_timeout(2500)
        assert _drafts(posts) == []
        assert _welcome(page).count() == 0
        assert "ubyhost_draft" not in [cookie["name"] for cookie in context.cookies()]
        page.goto(url)
        assert _welcome(page).count() == 0
        assert page.input_value("#first_name") == ""
    finally:
        context.close()
