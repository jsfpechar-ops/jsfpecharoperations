"""The guest flow, driven in a real browser the way a guest on a phone does it.

Every other guest test reads HTML. That is how three defects reached a guest on
30 Sep 2026 without one red test:

* the party-size box opened empty, so a family of three tapped "+" once and
  registered one person;
* the signature pad was sized while its wizard step was hidden. A phone fires
  a resize whenever the keyboard opens, so the canvas ended up 0 x 0: the pad
  said "Signed", saved nothing, and the form was refused;
* the date-of-birth boxes sat a line lower than the nationality beside them.

None of that is visible in markup. This file clicks through the real pages in
Chromium - pick the stay, set the group size, claim by
e-mail, then fill, sign and submit one form per person - and measures the
layout on every screen. It is skipped when Playwright or Chromium is missing;
the ``browser`` CI job installs both, so it always runs on a pull request.

Run it locally:
    pip install playwright==1.63.0 && python -m playwright install chromium
    python -m pytest tests/test_guest_browser_e2e.py -q
"""
import os
import re
import socket
import threading
import time
from datetime import timedelta
from pathlib import Path

import pytest

# In CI the browser job sets UBYHOST_REQUIRE_BROWSER, so a missing Playwright
# or Chromium fails the job instead of skipping these tests without a word.
REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import claim, db, guest_slug, i18n, mail  # noqa: E402
from tests.browser_support import chromium_launch_kwargs
from tests.v2_mockup import WIDTHS as GEOMETRY_WIDTHS, spacing_findings  # noqa: E402


# Layout rules every guest screen must meet. Each returns a sentence per
# breach, so a failure reads like a QA note rather than a stack of numbers.
LAYOUT_JS = r"""
() => {
  const out = [];
  const R = el => el.getBoundingClientRect();
  const vis = el => {
    const r = R(el);
    if (!r.width || !r.height) return false;
    for (let e = el; e; e = e.parentElement) {
      const cs = getComputedStyle(e);
      if (e.hidden || cs.display === 'none' || cs.visibility === 'hidden') return false;
    }
    return true;
  };
  const clipped = el => {
    const cs = getComputedStyle(el);
    return (cs.clip && cs.clip !== 'auto') || (cs.clipPath && cs.clipPath !== 'none') || R(el).width <= 2;
  };
  const name = el => el.id ? '#' + el.id : el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).join('.') : '');

  if (document.documentElement.scrollWidth > window.innerWidth + 1) {
    const wide = [...document.querySelectorAll('body *')].filter(e => R(e).right > window.innerWidth + 1 && R(e).width > 0 && getComputedStyle(e).position !== 'fixed');
    const culprit = wide.length ? name(wide[wide.length - 1]) : 'unknown';
    out.push(`the page scrolls sideways (${document.documentElement.scrollWidth}px on a ${window.innerWidth}px screen, widest: ${culprit})`);
  }

  document.querySelectorAll('label, button, a.g-btn, h2, summary').forEach(el => {
    if (!vis(el) || clipped(el) || el.closest('.g-checkin-steps')) return;
    if (el.scrollWidth > el.clientWidth + 1 && getComputedStyle(el).overflow !== 'visible')
      out.push(`text is cut off: ${name(el)} "${el.textContent.trim().slice(0, 40)}"`);
  });

  // Words meant only for screen readers must never be painted.
  document.querySelectorAll('.sr-only, .g-sr-only').forEach(el => {
    if (el.closest('.g-checkin-rail')) return;
    if (el.textContent.trim() && R(el).width > 2 && !clipped(el))
      out.push(`screen-reader text is visible: "${el.textContent.trim()}"`);
  });

  const scope = document.querySelector('[data-guest-step]:not([hidden])') || document.querySelector('main');
  const controls = [...scope.querySelectorAll('input[type=text], input[type=email], input:not([type]), select')]
    .filter(el => vis(el));
  const heights = [...new Set(controls.map(el => Math.round(R(el).height)))];
  if (heights.length > 1)
    out.push(`text boxes differ in height: ${controls.map(el => name(el) + '=' + Math.round(R(el).height)).join(', ')}`);

  scope.querySelectorAll('.g-row').forEach(row => {
    const fields = [...row.children].filter(vis);
    if (fields.length < 2) return;
    const tops = fields.map(f => R(f).top);
    if (Math.max(...tops) - Math.min(...tops) > 2) return;  // stacked on a phone
    const first = f => [...f.querySelectorAll('input:not([type=hidden]), select')].filter(el => vis(el))[0];
    const boxes = fields.map(first).filter(Boolean);
    const boxTops = boxes.map(el => Math.round(R(el).top));
    if (Math.max(...boxTops) - Math.min(...boxTops) > 2)
      out.push(`fields side by side are not level: ${boxes.map((el, i) => name(el) + ' at ' + boxTops[i]).join(' vs ')}`);
  });

  const fields = [...scope.querySelectorAll('.g-field')].filter(vis).filter(f => !f.parentElement.closest('.g-field'));
  const gaps = [];
  for (let i = 1; i < fields.length; i++) {
    const a = R(fields[i - 1]), b = R(fields[i]);
    if (Math.abs(a.top - b.top) < 2) continue;
    const row = fields[i - 1].closest('.g-row');
    if (row && row === fields[i].closest('.g-row')) continue;
    gaps.push(Math.round(b.top - a.bottom));
  }
  const rhythm = gaps.filter(g => g > 2);
  if (rhythm.length > 1 && Math.max(...rhythm) - Math.min(...rhythm) > 6)
    out.push(`the space between fields is uneven: ${gaps.join(', ')}px`);

  scope.querySelectorAll('button, a.g-btn').forEach(el => {
    if (!vis(el) || el.closest('.g-checkin-step')) return;
    const r = R(el);
    if (r.height < 44) out.push(`tap target under 44px: ${name(el)} "${el.textContent.trim().slice(0, 30)}" (${Math.round(r.height)}px)`);
  });
  return out;
}
"""

# 0885: the purpose "?" sits on the last line of its step title, small, with
# a 44 px tap target, 12 px or more from the title text.
HELP_BESIDE_TITLE_JS = """(marker) => {
  const help = document.querySelector(`[data-purpose-help="${marker}"]`);
  const range = document.createRange();
  range.selectNodeContents(help.closest('.g-step-head').querySelector('h2'));
  const lines = range.getClientRects();
  const line = lines[lines.length - 1];
  const tap = help.querySelector('summary').getBoundingClientRect();
  const dot = help.querySelector('.g-help-dot').getBoundingClientRect();
  return {title: (line.top + line.bottom) / 2, help: (dot.top + dot.bottom) / 2,
          gap: dot.left - line.right, dot: dot.width, tapW: tap.width, tapH: tap.height,
          lineBottom: line.bottom};
}"""

PEOPLE = [
    ("Anna", "Müller", "14031988", "C01X00T47"),
    ("Jonas", "Müller", "02111990", "C22Y11K08"),
    ("Lena", "Müller", "30062015", "C33Z22M19"),
]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def live_server():
    import uvicorn

    from app.main import app

    db.init_db()
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        pytest.fail("the test server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as playwright:
        try:
            chromium = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception as exc:  # the browser binary is not installed
            if REQUIRE_BROWSER:
                raise
            pytest.skip(f"Chromium is not available: {exc}")
        yield chromium
        chromium.close()


def _seed(token: str):
    """One property with a stay that starts today, like a guest's link."""
    now = db.utcnow()
    today = claim.prague_today()
    entity = db.insert(
        "legal_entity",
        {
            "name": "Browser Test s.r.o.",
            "contact_email": "host@example.test",
            "contact_phone": "+420 777 000 000",
            "created_at": now,
        },
    )
    apartment = db.insert(
        "apartment",
        {
            "legal_entity_id": entity,
            "internal_name": "Browser Loft",
            "guest_message": "Welcome! Your keys are in the example key safe. This complete host note is visible without opening anything.",
            "permalink_token": token,
            "permalink_window_days": 14,
            "default_purpose": "10",
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    return db.insert(
        "reservation",
        {
            "apartment_id": apartment,
            "source": "airbnb",
            "uid": f"{token}-stay",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=3)).isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )


def _claim_link(base: str, reservation_id: int) -> str:
    mail.drain(50)
    for message in mail.recent_console_messages(None, limit=50):
        found = re.search(r"(https?://\S+/%d/claim\S*#c=[\w\-]+)" % reservation_id, message["body_text"])
        if found:
            # The link carries the configured public host; the test server
            # listens on its own port.
            return base + found.group(1).split("/l/", 1)[1].join(["/l/", ""])
    raise AssertionError("no claim e-mail was sent")


SHOTS_0451 = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0451"


def _shot(page, name: str, full_page: bool = True) -> None:
    """0401/0451 evidence: keep a 390 px screenshot only when asked to."""
    if os.environ.get("UBYHOST_0451_SHOTS") != "1":
        return
    if page.viewport_size and page.viewport_size["width"] != 390:
        return
    SHOTS_0451.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS_0451 / name), full_page=full_page)


SHOTS_0885 = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0885"


def _shot_0885(page, name: str) -> None:
    """0885 evidence: person 2, step 1, only when asked to."""
    if os.environ.get("UBYHOST_0885_SHOTS") != "1":
        return
    SHOTS_0885.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS_0885 / name), full_page=True)


# 0896: Josef's spacing rules on the open step card (helper in tests/v2_mockup.py).
GUEST_SPACING = {
    "scope": "[data-guest-step]:not([hidden])",
    "cards": ".g-card",
    "controls": "input:not([type=hidden]), select, textarea, button, a.g-btn, summary:not(details.g-head-help > summary), .g-help-dot",
    "buttons": "button, a.g-btn, summary:not(details.g-head-help > summary), .g-help-dot",
    "glyphs": ".g-help-dot",
    "skip": ".sr-only, .g-sr-only",
    "fields": ".g-field",
}
SHOTS_0896 = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0896"


def _shot_0896(page, name: str) -> None:
    """0896 evidence: person 2, step 1, only when asked to."""
    if os.environ.get("UBYHOST_0896_SHOTS") != "1":
        return
    SHOTS_0896.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS_0896 / name), full_page=True)


class Guest:
    def __init__(self, page, width, lang="en"):
        self.page = page
        self.width = width
        self.lang = lang
        self.problems = []

    def check_layout(self, where: str):
        for problem in self.page.evaluate(LAYOUT_JS):
            self.problems.append(f"{where}: {problem}")

    def check_help_beside_title(self, marker: str, widths=()):
        """0885: the "?" is on the title line, and opens its panel under it."""
        page = self.page
        for width in widths or (self.width,):
            if widths:
                page.set_viewport_size({"width": width, "height": 812})
            box = page.evaluate(HELP_BESIDE_TITLE_JS, marker)
            where = f"{marker} at {width}px"
            assert abs(box["title"] - box["help"]) <= 4, f"{where}: the ? is not on the title line {box}"
            assert box["gap"] >= 12, f"{where}: the ? is closer than 12px to the title {box}"
            assert 16 <= box["dot"] <= 20, f"{where}: the ? is not small {box}"
            assert box["tapW"] >= 44 and box["tapH"] >= 44, f"{where}: tap target under 44px {box}"
        if widths:
            page.set_viewport_size({"width": self.width, "height": 812})
        help_ = page.locator(f'[data-purpose-help="{marker}"]')
        help_.locator("summary").click()
        assert help_.evaluate("el => el.open")
        panel_top = help_.locator(".g-intro").evaluate("el => el.getBoundingClientRect().top")
        line_bottom = page.evaluate(HELP_BESIDE_TITLE_JS, marker)["lineBottom"]
        assert panel_top >= line_bottom, f"{marker}: the panel does not open under the title"
        help_.locator("summary").click()
        assert not help_.evaluate("el => el.open")

    def check_spacing(self, where: str, widths=()):
        """0896: Josef's spacing rules on the open step, at each width."""
        page = self.page
        for width in widths or (self.width,):
            if widths:
                page.set_viewport_size({"width": width, "height": 812})
            for problem in spacing_findings(page, **GUEST_SPACING):
                self.problems.append(f"{where} at {width}px: {problem}")
        if widths:
            page.set_viewport_size({"width": self.width, "height": 812})

    def step(self) -> str:
        return self.page.evaluate(
            "() => { const s = document.querySelector('[data-guest-step]:not([hidden])');"
            " return s ? s.getAttribute('data-step-title') : '' }"
        )

    def pick_country(self, field: str, code: str):
        self.page.click(f"#{field}_search")
        self.page.keyboard.type(code)
        self.page.locator(f"#{field}_list [role=option]").first.click()

    def next(self):
        before = self.step()
        self.page.locator(
            "[data-guest-step]:not([hidden]) .g-wizard-nav button.g-btn[type=button]:not(.secondary)"
        ).first.click()
        self.page.wait_for_timeout(900)  # the step scrolls into view smoothly
        assert self.step() != before, f"Continue did not leave the step {before!r}"
        top, bar = self.page.evaluate(
            "() => [document.querySelector('[data-guest-step]:not([hidden])').getBoundingClientRect().top,"
            " document.querySelector('.g-head').getBoundingClientRect().bottom]"
        )
        assert top >= bar - 2, f"step {self.step()!r} opened under the app bar"

    def sign(self):
        pad = self.page.locator("#sig-canvas").bounding_box()
        self.page.mouse.move(pad["x"] + 30, pad["y"] + 80)
        self.page.mouse.down()
        for k in range(24):
            self.page.mouse.move(pad["x"] + 30 + k * 8, pad["y"] + 80 + (-1) ** k * 20)
        self.page.mouse.up()
        signature = self.page.eval_on_selector("#signature", "e => e.value")
        assert signature.startswith("data:image/png;base64,") and len(signature) > 500, (
            "drawing on the pad did not produce a signature"
        )

    def fill_form(self, number: int, total: int, person):
        first, surname, birth, document = person
        page = self.page
        t = i18n.translator(self.lang)
        self.check_layout(f"guest {number}, details (empty)")
        assert page.locator('[data-purpose-help="identity"]').is_visible()
        self.check_help_beside_title("identity", widths=GEOMETRY_WIDTHS)
        all_widths = GEOMETRY_WIDTHS if (self.lang, self.width) == ("en", 390) else ()
        if number == 2:
            self.check_spacing("person 2, details", all_widths)
            if self.lang == "en" and self.width in (390, 1280):
                _shot_0896(page, f"person2-step1-{self.width}.png")
        if number == 2 and self.lang == "en" and self.width in (390, 1280):
            _shot_0885(page, f"person2-step1-{self.width}.png")
            if self.width == 390:
                summary = page.locator('[data-purpose-help="identity"] summary')
                summary.click()
                _shot_0885(page, "person2-step1-open-390.png")
                summary.click()
        page.fill("#first_name", first)
        # A phone keyboard opening shrinks the viewport and fires resize while
        # the signature step is still hidden. That is what left the pad 0 x 0.
        page.set_viewport_size({"width": self.width, "height": 480})
        page.set_viewport_size({"width": self.width, "height": 812})
        page.fill("#surname", surname)
        page.click("#birth_date")
        page.keyboard.type(birth)
        self.pick_country("nationality", "DEU")
        assert page.eval_on_selector("#birth_date", "e => e.value") == f"{birth[:2]}.{birth[2:4]}.{birth[4:]}"
        assert page.eval_on_selector("#nationality", "e => e.value") == "DEU"
        page.fill("#doc_number", document)
        self.check_layout(f"guest {number}, details")
        self.next()
        assert page.locator('[data-purpose-help="address-stay"]').is_visible()
        self.check_help_beside_title("address-stay", widths=all_widths if number == 2 else ())
        if number == 2:
            self.check_spacing("person 2, home", all_widths)
        if not page.input_value("#res_street"):
            page.fill("#res_street", "Hauptstraße 12")
            page.fill("#res_city", "Berlin")
            self.pick_country("res_country", "DEU")
        self.check_layout(f"guest {number}, home")
        self.next()
        assert page.locator('[data-purpose-help="signature"]').is_visible()
        self.check_help_beside_title("signature", widths=all_widths if number == 2 else ())
        if number == 2:
            self.check_spacing("person 2, signature", all_widths)
        self.sign()
        self.check_layout(f"guest {number}, signature")
        # The legal notice moved onto the signature step and is collapsed by
        # default; the acknowledgement must stay visible outside that fold.
        legal = page.locator("details.g-legal-text")
        assert legal.count() == 1
        assert not legal.evaluate("el => el.open")
        page.locator("#legal_ack").scroll_into_view_if_needed()
        page.wait_for_timeout(100)
        ack_box = page.locator("#legal_ack").bounding_box()
        ack_center = (ack_box["x"] + ack_box["width"] / 2, ack_box["y"] + ack_box["height"] / 2)
        assert page.evaluate(
            """([x, y]) => {
                const el = document.elementFromPoint(x, y);
                return !!(el && (el.id === 'legal_ack'
                    || el.closest('label[for=legal_ack]')
                    || el.closest('.legal-ack')));
            }""",
            list(ack_center),
        ), "the sticky submit button overlaps the required acknowledgement"
        assert page.locator("label[for=legal_ack]").is_visible()
        assert page.locator("button[type=submit]").last.is_visible()
        self.check_layout(f"guest {number}, acknowledgement")
        # A viewport shot: the sticky submit button is pinned to the bottom of
        # the screen, so a full-page capture would draw it over the review list.
        _shot(page, "acknowledgement-390.png", full_page=False)
        ack = page.locator("#legal_ack")
        assert not ack.is_checked()
        # Native required keeps an unsigned acknowledgement on the page.
        page.locator("[data-guest-step]:not([hidden]) button[type=submit]").last.click()
        assert "/save" not in page.url
        ack.check()
        page.locator("[data-guest-step]:not([hidden]) button[type=submit]").last.click()
        page.wait_for_load_state()
        assert "/save" not in page.url, page.inner_text(".g-err") if page.locator(".g-err").count() else page.url
        if number < total:
            # Direct progression: the next person's empty form opens at once.
            assert page.url.split("?")[0].endswith("/new"), page.url
            strip = page.locator(".g-saved-strip")
            assert strip.count() == 1 and strip.is_visible()
            assert t("person_saved") in strip.inner_text()
            assert page.input_value("#first_name") == ""
            assert page.eval_on_selector("#signature", "e => e.value") == ""
            assert not page.locator("#legal_ack").is_checked()
            _shot(page, "next-guest-390.png")


# WP26: German, Spanish and French run the whole flow too, at the narrow
# phone widths where long words break a layout first (German is the longest).
# They arrive with no ?lang= at all: the browser's own locale is what sends
# Accept-Language, so this also proves the language is picked automatically.
_LOCALES = {"en": "en-GB", "de": "de-AT", "es": "es-MX", "fr": "fr-CA"}
_RUNS = [("en", width) for width in (320, 375, 390, 1280)] + [
    (lang, width) for lang in ("de", "es", "fr") for width in (320, 360, 390)
]


@pytest.mark.parametrize(("lang", "width"), _RUNS)
def test_a_group_of_three_registers_everyone_on_one_phone(live_server, browser, lang, width):
    _register_a_group_of_three(
        live_server, browser, width, f"browser-e2e-{lang}-{width}", readable=False, lang=lang
    )


@pytest.mark.parametrize("width", [320, 360, 390])
def test_the_readable_link_takes_the_group_through_the_same_flow(live_server, browser, width):
    """WP19: the guest opens /l/{slug}; the claim mail still carries the token
    link, so the flow also crosses from one link to the other mid-way."""
    _register_a_group_of_three(live_server, browser, width, f"browser-slug-{width}", readable=True)


def _register_a_group_of_three(live_server, browser, width, token, readable, lang="en"):
    db.execute("DELETE FROM rate_limit_event")
    stay = _seed(token)
    key = token
    if readable:
        apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (token,))
        key = guest_slug.ensure(apartment)
        assert key.startswith("browser-loft-")
    context = browser.new_context(viewport={"width": width, "height": 812}, locale=_LOCALES[lang])
    page = context.new_page()
    script_errors = []
    page.on("pageerror", lambda error: script_errors.append(str(error)))
    guest = Guest(page, width, lang)
    try:
        page.goto(f"{live_server}/l/{key}" + ("?lang=en" if lang == "en" else ""))
        assert page.get_attribute("html", "lang") == lang
        guest.check_layout("pick")
        note = page.locator(".g-arrival-message")
        assert note.is_visible()
        assert note.locator("summary").count() == 0
        assert "complete host note" in note.inner_text()
        assert page.locator(".g-why:not([data-purpose-help])").bounding_box()["y"] > page.locator(".g-arrival-choice").bounding_box()["y"]
        page.locator(f"a[href*='/l/{key}/{stay}']").first.click()
        page.wait_for_load_state()
        guest.check_layout("claim")
        _shot(page, "claim-390.png")
        assert page.locator('[data-purpose-help="guest-count"]').is_visible()
        email_help = page.locator("details.g-claim-help")
        assert email_help.count() == 1
        assert email_help.locator("summary").get_attribute("aria-label") == i18n.translator(lang)("email_help_label")
        assert email_help.locator("summary").inner_text().strip() == "?"
        assert email_help.locator("summary").evaluate(
            "el => getComputedStyle(el, '::before').content"
        ) in ("none", "normal")

        # The group size never starts empty on the claim screen.
        assert page.input_value("#party_size") == "1"
        page.fill("#party_size", "3")
        assert page.input_value("#party_size") == "3"
        page.fill("#guest_email", "family@example.test")
        page.locator("form button[type=submit]").first.click()
        page.wait_for_load_state()

        page.goto(_claim_link(live_server, stay))
        page.locator("form button[type=submit]").first.click()
        page.wait_for_load_state()

        assert page.locator(".g-host-message, .g-arrival-message").count() == 0
        why = page.locator(".g-why:not([data-purpose-help])")
        assert not why.evaluate("el => el.open")
        assert why.evaluate("el => el.getBoundingClientRect().top") >= page.locator("form[data-guest-wizard]").evaluate("el => el.getBoundingClientRect().bottom")
        assert why.locator(".g-why-summary").evaluate("el => getComputedStyle(el, '::after').content") == '"?"'
        why.locator("summary").click()
        assert why.evaluate("el => el.open")
        why.locator("summary").click()
        for number, person in enumerate(PEOPLE, start=1):
            if number > 1:
                # No Saved / Add a person page between people: the previous
                # save already opened this empty form.
                assert page.url.split("?")[0].endswith("/new"), page.url
                assert page.get_by_role("link", name=i18n.translator(lang)("add_person")).count() == 0
                guest.check_layout(f"next guest {number}")
            guest.fill_form(number, 3, person)

        stored = db.query("SELECT * FROM guest WHERE reservation_id = ?", (stay,))
        assert sorted(row["first_name"].upper() for row in stored) == ["ANNA", "JONAS", "LENA"]
        assert all(row["signature_png"].startswith("data:image/png;base64,") for row in stored)
        assert i18n.translator(lang)("all_done_title") in page.inner_text("body")
        guest.check_layout("done")
        _shot(page, "completion-summary-390.png")
        # The privacy notice is the longest text a guest gets; it must fit too.
        page.goto(f"{live_server}/l/{token}/privacy")
        assert page.get_attribute("html", "lang") == lang
        guest.check_layout("privacy")
        assert not script_errors, script_errors
        assert not guest.problems, "\n".join(guest.problems)
    finally:
        context.close()
        db.execute(
            "DELETE FROM guest WHERE reservation_id IN (SELECT r.id FROM reservation r "
            "JOIN apartment a ON a.id = r.apartment_id WHERE a.permalink_token = ?)",
            (token,),
        )


def test_the_czech_pages_have_no_english_left(live_server, browser):
    token = "browser-e2e-cs"
    db.execute("DELETE FROM rate_limit_event")
    stay = _seed(token)
    context = browser.new_context(viewport={"width": 375, "height": 812}, locale="cs-CZ")
    page = context.new_page()
    try:
        page.goto(f"{live_server}/l/{token}?lang=cs")
        text = page.inner_text("body")
        assert "Check-in" not in text and "Check-out" not in text
        page.locator(f"a[href*='/l/{token}/{stay}']").first.click()
        page.wait_for_load_state()
        assert page.input_value("#party_size") == "1"
        page.fill("#guest_email", "rodina@example.test")
        page.locator("form button[type=submit]").first.click()
        page.wait_for_load_state()
        page.goto(_claim_link(live_server, stay))
        page.locator("form button[type=submit]").first.click()
        page.wait_for_load_state()
        text = page.inner_text("body")
        for english in ("Continue", "Guest 1", "Sign here", "Start typing"):
            assert english not in text, f"{english!r} on a Czech page"
        assert page.evaluate(
            "() => document.querySelector('[data-guest-step]:not([hidden])').getAttribute('data-step-title')"
        ) == "Vaše údaje"
    finally:
        context.close()


# --- stay-fee money card and form estimate (brief 0910) ----------------------

SIGNED_PNG = "data:image/png;base64,iVBORw0KGgo="


def _fee_seed(token: str, rate: int = 50, signed: bool = True):
    """A stay whose property collects a fee, every enabled rail set up. With ``signed`` one
    foreign adult has signed; no headcount is declared, so the hub card shows."""
    stay = _seed(token)
    row = db.query_one("SELECT apartment_id FROM reservation WHERE id = ?", (stay,))
    apt = db.query_one("SELECT legal_entity_id FROM apartment WHERE id = ?", (row["apartment_id"],))
    db.update("apartment", row["apartment_id"], {
        "stay_fee_collect": 1,
        "stay_fee_rate_czk": rate,
        "stay_fee_guest_rails": "qr,iban,revolut,cash",
        "stay_fee_guest_revolut_link": "https://revolut.me/guest-e2e",
        "stay_fee_guest_cash_note": "",
    })
    db.update("legal_entity", apt["legal_entity_id"], {"iban": "CZ6508000000192000145399"})
    if not signed:
        return stay
    now = db.utcnow()
    db.insert("guest", {
        "reservation_id": stay,
        "first_name": "Ada",
        "surname": "Guest",
        "birth_date": "01011980",
        "nationality": "DEU",
        "res_country": "DEU",
        "res_city": "Berlin",
        "signature_png": SIGNED_PNG,
        "created_at": now,
        "updated_at": now,
    })
    return stay


@pytest.mark.parametrize("width", [320, 390, 768, 1280])
def test_fee_card_shows_with_qr_rail_open_and_enabled_rails(live_server, browser, monkeypatch, width):
    from app import config

    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    monkeypatch.setattr(config, "GUEST_PIN_REQUIRED", False)  # the hub otherwise shows the PIN page
    from app import mail

    # The seeded guest never went through the claim mail, so the claim page would
    # show before the hub. Same switch test_0376_ai_gates.py uses.
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    token = f"browser-fee-card-{width}"
    stay = _fee_seed(token)
    page = browser.new_page(viewport={"width": width, "height": 800})
    try:
        page.goto(f"{live_server}/l/{token}/{stay}?lang=en")
        card = page.locator("#fee-pay")
        assert card.count() == 1, page.inner_text("body")[:400]
        assert card.is_visible()
        assert card.locator("details.g-summary").filter(has=page.locator(".g-fee-rail")).count() == 4
        assert card.locator("details[open] .g-fee-qr-img").count() == 1
        assert card.locator(".g-fee-qr-img").is_visible()
        qr_rail = card.locator("details.g-summary").filter(has=page.locator(".g-fee-qr-img"))
        assert qr_rail.locator(".g-fee-rail").inner_text().strip() == ""  # QR only: nothing to type
        card.locator("summary.g-summary-fold", has_text="Bank transfer").click()
        iban_rail = card.locator("details.g-summary").filter(has_text="Bank transfer")
        iban_text = iban_rail.locator(".g-fee-rail").inner_text()
        assert "Variable symbol" in iban_text and str(int(stay)) in iban_text
        assert "Message" not in iban_text
        assert f"{int(stay):010d}" not in card.inner_text()
        card.locator("summary.g-summary-fold", has_text="Revolut").click()
        assert "Open your host" not in card.inner_text()
        assert card.get_by_role("link", name="Revolut", exact=False).count() == 1
        assert "0000000" not in card.inner_text()
        assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")
    finally:
        page.close()


def test_fee_card_absent_when_the_fee_is_zero(live_server, browser, monkeypatch):
    from app import config

    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    monkeypatch.setattr(config, "GUEST_PIN_REQUIRED", False)  # the hub otherwise shows the PIN page
    from app import mail

    # The seeded guest never went through the claim mail, so the claim page would
    # show before the hub. Same switch test_0376_ai_gates.py uses.
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    token = "browser-fee-zero"
    stay = _fee_seed(token, rate=0)
    page = browser.new_page(viewport={"width": 390, "height": 800})
    try:
        page.goto(f"{live_server}/l/{token}/{stay}?lang=en")
        # Not vacuous: the hub itself rendered (the seeded guest is listed, no redirect to the form).
        assert "/new" not in page.url, page.url
        assert "Person 1" in page.inner_text("body"), page.inner_text("body")[:400]
        assert page.locator("#fee-pay").count() == 0
    finally:
        page.close()


def test_form_estimate_line_shows_when_the_estimate_is_above_zero(live_server, browser, monkeypatch):
    """The estimate is computed from the entered values, so the form is posted with them
    (noValidate skips the browser's required checks; the server re-renders with the values)."""
    from app import config

    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    monkeypatch.setattr(config, "GUEST_PIN_REQUIRED", False)  # the hub otherwise shows the PIN page
    from app import mail

    # The seeded guest never went through the claim mail, so the claim page would
    # show before the hub. Same switch test_0376_ai_gates.py uses.
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    token = "browser-fee-estimate"
    stay = _fee_seed(token, signed=False)
    page = browser.new_page(viewport={"width": 390, "height": 800})
    try:
        page.goto(f"{live_server}/l/{token}/{stay}/new?lang=en")
        page.evaluate("""() => {
            const form = document.querySelector('form[action*="/save"]');
            form.noValidate = true;
            document.querySelector('#birth_date').value = '01.01.1980';
            document.querySelector('#res_country').value = 'DEU';
        }""")
        # The Save button sits in a later wizard step, so submit the form itself
        # (noValidate above keeps the browser's required checks out of the way).
        with page.expect_navigation():
            page.evaluate("() => document.querySelector('form[action*=\"/save\"]').requestSubmit()")
        assert page.locator("#fee-estimate").count() == 1
        assert page.locator("#fee-estimate").is_visible()
    finally:
        page.close()


def test_0959_changing_language_keeps_the_draft_the_step_and_leaves_no_trace(
    live_server, browser, monkeypatch
):
    """G01: EN -> CS -> EN keeps what was typed and the step; a drawn signature
    asks first and Cancel keeps the draft; no answer reaches a URL or storage."""
    from app import config

    monkeypatch.setattr(config, "GUEST_PIN_REQUIRED", False)
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    token = "browser-0959-lang"
    stay = _fee_seed(token, signed=False)
    page = browser.new_page(viewport={"width": 390, "height": 812})
    urls = []
    page.on("request", lambda request: urls.append(request.url))
    secrets = ["Synthetica", "Testovic", "SYN0959X", "Examplova 5", "Testov"]
    guest = Guest(page, 390)

    def progress():
        return [int(n) for n in re.findall(r"\d+", page.inner_text("[data-wizard-label]"))[:2]]

    def pick(lang):
        page.locator("[data-lang-menu] summary").click()
        page.locator(f'[data-lang-draft][lang="{lang}"]').click()

    try:
        page.goto(f"{live_server}/l/{token}/{stay}/new?lang=en")
        page.fill("#first_name", secrets[0])
        page.fill("#surname", secrets[1])
        page.click("#birth_date")
        page.keyboard.type("01011980")
        guest.pick_country("nationality", "CZE")
        page.fill("#doc_number", secrets[2])
        guest.next()
        page.fill("#res_street", secrets[3])
        page.fill("#res_city", secrets[4])
        page.evaluate("() => { document.querySelector('#res_country').value = 'CZE'; }")
        guest.next()
        before = progress()
        assert before[0] == before[1], before  # on the last step; Czech has no photo step
        guest.sign()
        page.check("#legal_ack")

        # Cancel: the warning appears, nothing is lost, no navigation happens.
        messages = []
        page.once("dialog", lambda dialog: (messages.append(dialog.message), dialog.dismiss()))
        pick("cs")
        page.wait_for_timeout(300)
        assert messages == [i18n.translator("en")("lang_draft_warning")], messages
        assert page.get_attribute("html", "lang") == "en"
        assert page.input_value("#first_name") == secrets[0]
        assert page.eval_on_selector("#signature", "e => e.value").startswith("data:image/png")
        assert page.is_checked("#legal_ack")

        # Accept: Czech page, same answers, same step, signature and tick asked again.
        page.once("dialog", lambda dialog: dialog.accept())
        with page.expect_navigation():
            page.locator(f'[data-lang-draft][lang="cs"]').click()
        assert page.get_attribute("html", "lang") == "cs"
        assert progress() == before, (progress(), before)
        assert page.input_value("#first_name") == secrets[0]
        assert page.input_value("#surname") == secrets[1]
        assert page.input_value("#birth_date") == "01.01.1980"
        assert page.input_value("#nationality") == "CZE"
        assert page.input_value("#doc_number") == secrets[2]
        assert page.input_value("#res_street") == secrets[3]
        assert page.input_value("#res_city") == secrets[4]
        assert page.eval_on_selector("#signature", "e => e.value") == ""
        assert not page.is_checked("#legal_ack")

        # Back to English with nothing to lose: no warning, still the same.
        shots = os.environ.get("UBYHOST_SHOTS_DIR")
        if shots:
            Path(shots).mkdir(parents=True, exist_ok=True)
            for width in (390, 768, 1280):
                page.set_viewport_size({"width": width, "height": 900})
                page.screenshot(path=str(Path(shots) / f"0959-review-cs-{width}.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 812})
        page.once("dialog", lambda dialog: pytest.fail("no warning expected"))
        with page.expect_navigation():
            pick("en")
        assert page.get_attribute("html", "lang") == "en"
        assert progress() == before
        assert page.input_value("#surname") == secrets[1]
        assert page.input_value("#nationality") == "CZE"

        # Step 1 of a foreign nationality keeps its longer step count.
        page.locator("[data-guest-step]:not([hidden]) .g-wizard-nav button.secondary").first.click()
        page.locator("[data-guest-step]:not([hidden]) .g-wizard-nav button.secondary").first.click()
        guest.pick_country("nationality", "DEU")
        page.fill("#first_name", secrets[0])
        pick("cs")
        page.wait_for_load_state()
        assert page.input_value("#nationality") == "DEU"
        assert page.input_value("#first_name") == secrets[0]

        assert not [u for u in urls if any(s.lower() in u.lower() for s in secrets)], urls
        assert "01.01.1980" not in " ".join(urls) and "01011980" not in " ".join(urls)
        assert page.evaluate("() => [localStorage.length, sessionStorage.length]") == [0, 0]
        assert not any(
            any(s in cookie["value"] for s in secrets) for cookie in page.context.cookies()
        )
    finally:
        page.close()


def test_0959_discard_warning_cancel_keeps_draft(live_server, browser, monkeypatch):
    """0959: a drawn signature asks before a language switch; Cancel keeps the
    page as it was (same language, same answers, same URL, no navigation)."""
    from app import config

    monkeypatch.setattr(config, "GUEST_PIN_REQUIRED", False)
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    token = "browser-0959-cancel"
    stay = _fee_seed(token, signed=False)
    page = browser.new_page(viewport={"width": 390, "height": 812})
    secrets = ["Synthetica", "Testovic", "SYN0959X", "Examplova 5", "Testov"]
    guest = Guest(page, 390)

    def pick(lang):
        page.locator("[data-lang-menu] summary").click()
        page.locator(f'[data-lang-draft][lang="{lang}"]').click()

    try:
        page.goto(f"{live_server}/l/{token}/{stay}/new?lang=en")
        page.fill("#first_name", secrets[0])
        page.fill("#surname", secrets[1])
        page.click("#birth_date")
        page.keyboard.type("01011980")
        guest.pick_country("nationality", "CZE")
        page.fill("#doc_number", secrets[2])
        guest.next()
        page.fill("#res_street", secrets[3])
        page.fill("#res_city", secrets[4])
        page.evaluate("() => { document.querySelector('#res_country').value = 'CZE'; }")
        guest.next()
        guest.sign()
        page.check("#legal_ack")

        # A drawn signature asks first; Accept moves to the Czech page.
        page.once("dialog", lambda dialog: dialog.accept())
        with page.expect_navigation():
            pick("cs")
        assert page.get_attribute("html", "lang") == "cs"
        assert page.input_value("#first_name") == secrets[0]

        # Draw again on the Czech page, then Cancel the switch back.
        guest.sign()
        page.check("#legal_ack")
        messages = []
        page.once("dialog", lambda dialog: (messages.append(dialog.message), dialog.dismiss()))
        pick("en")
        page.wait_for_timeout(300)
        assert messages == [i18n.translator("cs")("lang_draft_warning")], messages
        assert page.url.endswith("/relang?lang=cs"), page.url
        assert page.get_attribute("html", "lang") == "cs"
        assert page.input_value("#first_name") == secrets[0]
        assert page.input_value("#surname") == secrets[1]
        assert page.input_value("#res_city") == secrets[4]
        assert page.eval_on_selector("#signature", "e => e.value").startswith("data:image/png")
        assert page.is_checked("#legal_ack")
    finally:
        page.close()
