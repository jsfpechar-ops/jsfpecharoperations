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
import secrets
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

from app import claim, db, guest_slug, i18n, mail, reporting  # noqa: E402
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
    gaps.push(Math.round(b.top - a.bottom));
  }
  const rhythm = gaps.filter(g => g > 2);
  if (rhythm.length > 1 && Math.max(...rhythm) - Math.min(...rhythm) > 2)
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
        if page.locator("#sig-block").is_hidden():
            # 1090: a guest under 15 gets a note instead of the pad.
            assert int(birth[4:]) > 2010, f"the pad is hidden for an adult born {birth[4:]}"
            assert page.locator("#u15-note").is_visible()
        else:
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


def _register_a_group_of_three(live_server, browser, width, token_prefix, readable, lang="en"):
    db.execute("DELETE FROM rate_limit_event")
    token = f"{token_prefix}-{secrets.token_hex(4)}"
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
        # 1089: Lena (born 2015) is under 15 on arrival, so no signature is kept for her.
        reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (stay,))
        for row in stored:
            kind = reporting.signature_record(row, reservation)["kind"]
            if reporting.guest_under_15(row, reservation):
                assert row["first_name"].upper() == "LENA"
                assert row["signature_png"] is None and row["signed_at"] is None
                assert kind in ("exempt", "signed_for")
            else:
                assert row["signature_png"].startswith("data:image/png;base64,")
                assert kind == "own"
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
    token = f"browser-e2e-cs-{secrets.token_hex(4)}"
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

import base64 as _b64

SIGNED_PNG = "data:image/png;base64," + _b64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001od7a1f0000000049454e44ae42"
        "6082".replace("od", "0d")
    )
).decode()


def _fee_seed(token: str, rate: int = 50, signed: bool = True, nationality: str = "CZE", declared: int = 1):
    """A stay whose property collects a fee, every enabled rail set up. With ``signed`` one
    adult has signed and the declared headcount is met, so the hub card shows."""
    stay = _seed(token)
    db.update("reservation", stay, {"declared_guests": declared})
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
        "nationality": nationality,
        "doc_number": "123456789",
        "res_street": "Hauptstrasse 1",
        "res_country": "DEU",
        "res_city": "Berlin",
        "purpose": "10",
        "signature_png": SIGNED_PNG,
        "created_at": now,
        "updated_at": now,
    })
    return stay


SHOTS_0958 = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0958"


def _shot_0958(page, name: str) -> None:
    """0958 evidence: written only when UBYHOST_0958_SHOTS=1 is set."""
    if os.environ.get("UBYHOST_0958_SHOTS") != "1":
        return
    SHOTS_0958.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS_0958 / name), full_page=True)


@pytest.mark.parametrize("width", [320, 390, 768, 1280])
def test_fee_card_shows_with_qr_rail_open_and_enabled_rails(live_server, browser, monkeypatch, width):
    from app import config

    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    monkeypatch.setattr(config, "GUEST_PIN_REQUIRED", False)  # the hub otherwise shows the PIN page
    from app import mail

    # The seeded guest never went through the claim mail, so the claim page would
    # show before the hub. Same switch test_0376_ai_gates.py uses.
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    token = f"browser-fee-card-{width}-{secrets.token_hex(4)}"
    stay = _fee_seed(token)
    page = browser.new_page(viewport={"width": width, "height": 800})
    try:
        page.goto(f"{live_server}/l/{token}/{stay}?lang=en")
        card = page.locator("#fee-pay")
        assert card.count() == 1, page.inner_text("body")[:400]
        assert card.is_visible()
        assert card.locator("div.g-fee-opt").filter(has=page.locator(".g-fee-rail")).count() == 3
        assert card.get_by_text("Please pay now.").is_visible()
        assert card.locator("details.g-fee-fold").count() == 2
        if width == 390:
            _shot_0958(page, "guest-hub-fee-card-390.png")
        if width == 768:
            _shot_0958(page, "guest-hub-fee-card-768.png")
        if width == 1280:
            _shot_0958(page, "guest-hub-fee-card-1280.png")
        assert card.locator(".g-fee-opt .g-fee-qr-img").count() == 1
        assert card.locator(".g-fee-qr-img").is_visible()
        qr_rail = card.locator("div.g-fee-opt").filter(has=page.locator(".g-fee-qr-img"))
        assert "Browser Test s.r.o." in qr_rail.locator(".g-fee-rail").inner_text()  # QR and who gets the money; nothing to type
        iban_rail = card.locator("div.g-fee-opt").filter(has_text="Bank transfer")
        iban_text = iban_rail.locator(".g-fee-rail").inner_text()
        assert "Variable symbol" in iban_text and str(int(stay)) in iban_text
        assert "Browser Test s.r.o." in iban_text
        assert "Message" not in iban_text
        assert f"{int(stay):010d}" not in card.inner_text()
        assert card.locator(".g-fee-opt-h", has_text="Revolut").is_visible()
        assert "Open your host" not in card.inner_text()
        assert card.get_by_role("link", name="Revolut", exact=False).count() == 1
        assert "0000000" not in card.inner_text()
        assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")
    finally:
        page.close()


def test_fee_card_hides_the_qr_for_guests_who_are_not_czech_or_slovak(live_server, browser, monkeypatch):
    from app import config, mail

    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    monkeypatch.setattr(config, "GUEST_PIN_REQUIRED", False)
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    token = "browser-fee-gbr"
    stay = _fee_seed(token, nationality="GBR")
    page = browser.new_page(viewport={"width": 390, "height": 800})
    try:
        page.goto(f"{live_server}/l/{token}/{stay}?lang=en")
        card = page.locator("#fee-pay")
        assert card.count() == 1, page.inner_text("body")[:400]
        assert card.locator(".g-fee-qr-img").count() == 0
        assert card.locator("div.g-fee-opt").filter(has=page.locator(".g-fee-rail")).count() == 3
    finally:
        page.close()


def test_fee_card_waits_until_every_expected_guest_is_registered(live_server, browser, monkeypatch):
    from app import config, mail

    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    monkeypatch.setattr(config, "GUEST_PIN_REQUIRED", False)
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    token = "browser-fee-waits"
    stay = _fee_seed(token, declared=2)
    page = browser.new_page(viewport={"width": 390, "height": 800})
    try:
        page.goto(f"{live_server}/l/{token}/{stay}?lang=en")
        assert "Person 1" in page.inner_text("body"), page.inner_text("body")[:400]
        assert page.locator("#fee-pay").count() == 0
    finally:
        page.close()


def test_fee_card_opens_the_hosts_default_rail_first(live_server, browser, monkeypatch):
    from app import config, mail

    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    monkeypatch.setattr(config, "GUEST_PIN_REQUIRED", False)
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    token = "browser-fee-default-rail"
    stay = _fee_seed(token)
    row = db.query_one("SELECT apartment_id FROM reservation WHERE id = ?", (stay,))
    db.update("apartment", row["apartment_id"], {"stay_fee_guest_default_rail": "revolut"})
    page = browser.new_page(viewport={"width": 390, "height": 800})
    try:
        page.goto(f"{live_server}/l/{token}/{stay}?lang=en")
        first = page.locator("#fee-pay div.g-fee-opt").filter(has=page.locator(".g-fee-rail")).first
        assert "Revolut" in first.locator(".g-fee-opt-h").inner_text()
        assert first.locator(".g-fee-rail").is_visible()
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
    token = f"browser-fee-zero-{secrets.token_hex(4)}"
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


@pytest.mark.parametrize("width", [390, 768])
def test_form_estimate_line_shows_when_the_estimate_is_above_zero(live_server, browser, monkeypatch, width):
    """The estimate is computed from the entered values, so the form is posted with them
    (noValidate skips the browser's required checks; the server re-renders with the values)."""
    from app import config

    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    monkeypatch.setattr(config, "GUEST_PIN_REQUIRED", False)  # the hub otherwise shows the PIN page
    from app import mail

    # The seeded guest never went through the claim mail, so the claim page would
    # show before the hub. Same switch test_0376_ai_gates.py uses.
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    token = f"browser-fee-estimate-{secrets.token_hex(4)}"
    stay = _fee_seed(token, signed=False)
    page = browser.new_page(viewport={"width": width, "height": 800})
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
        assert page.locator("#legal-notice #fee-estimate").count() == 0
        assert page.evaluate("""() => document.getElementById('fee-estimate').compareDocumentPosition(document.getElementById('legal-notice')) & Node.DOCUMENT_POSITION_FOLLOWING""")
        assert page.get_by_text("You do not pay now.").is_visible()
        assert page.locator("#fee-estimate").count() == 1
        assert page.locator("#fee-estimate").is_visible()
        if width == 390:
            _shot_0958(page, "form-estimate-390.png")
        if width == 768:
            _shot_0958(page, "form-estimate-768.png")
    finally:
        page.close()


def test_1025_form_estimate_follows_the_typed_birth_date(live_server, browser, monkeypatch):
    """1025: the Check-step estimate is drawn before a birth date is typed. The script
    recomputes it by the engine's rules: a child pays nothing (box hidden), a guest who
    turns 18 during the stay pays only from the birthday, an adult pays every counted day."""
    from datetime import date as _date, timedelta as _td
    from app import config, mail
    from app.routes import guest as guest_routes

    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    monkeypatch.setattr(config, "GUEST_PIN_REQUIRED", False)
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    token = f"browser-fee-minor-{secrets.token_hex(4)}"
    stay = _fee_seed(token, signed=False)
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (stay,))
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (reservation["apartment_id"],))
    arrival = _date.fromisoformat(reservation["date_from"])
    turning = arrival + _td(days=2)
    turning_birth = turning.replace(year=turning.year - 18).strftime("%d.%m.%Y")
    page = browser.new_page(viewport={"width": 390, "height": 800})
    try:
        page.goto(f"{live_server}/l/{token}/{stay}/new?lang=en")
        assert page.locator("#fee-estimate").count() == 1

        def typed(birth):
            page.evaluate("""(birth) => {
                const input = document.querySelector('#birth_date');
                input.value = birth;
                input.dispatchEvent(new Event('input', {bubbles: true}));
                const form = document.querySelector('form[action*="/save"]');
                form.dispatchEvent(new CustomEvent('guest-wizard:shown'));
            }""", birth)
            # The box sits in the Check step, so read its own hidden flag, not visibility.
            return page.evaluate("""() => {
                const box = document.getElementById('fee-estimate');
                return [box.hidden, box.querySelector('.g-fee-amt').textContent.trim()];
            }""")

        for birth in ("01.01.1980", "01.01.2015", turning_birth):
            want = guest_routes._fee_estimate(apartment, reservation, {"birth_date": birth})
            hidden, amount = typed(birth)
            amount = "" if hidden else amount
            if want is None:
                assert hidden, birth
            else:
                assert not hidden and amount == f"{want['amount']} CZK", (birth, amount, want)
        assert guest_routes._fee_estimate(apartment, reservation, {"birth_date": turning_birth})["days"] \
            < guest_routes._fee_estimate(apartment, reservation, {"birth_date": "01.01.1980"})["days"]
    finally:
        page.close()


def test_0979_changing_language_keeps_the_draft_the_step_and_leaves_no_trace(
    live_server, browser, monkeypatch
):
    """G01: EN -> CS -> EN keeps what was typed and the step; a drawn signature
    asks first and Cancel keeps the draft; no answer reaches a URL or storage."""
    from app import config

    monkeypatch.setattr(config, "GUEST_PIN_REQUIRED", False)
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    token = f"browser-0959-lang-{secrets.token_hex(4)}"
    stay = _fee_seed(token, signed=False)
    page = browser.new_page(viewport={"width": 390, "height": 812})
    # Only page navigations and the language-switch request are checked for
    # typed values; the RUIAN address-suggest fetch is out of scope for 0979.
    urls = []
    page.on(
        "request",
        lambda request: urls.append(request.url)
        if request.is_navigation_request() or "/relang" in request.url
        else None,
    )
    sample = ["Synthetica", "Testovic", "SYN0959X", "Examplova 5", "Testov"]
    guest = Guest(page, 390)

    def progress():
        return [int(n) for n in re.findall(r"\d+", page.inner_text("[data-wizard-label]"))[:2]]

    def pick(lang):
        page.locator("[data-lang-menu] summary").click()
        page.locator(f'[data-lang-draft][lang="{lang}"]').click()

    try:
        page.goto(f"{live_server}/l/{token}/{stay}/new?lang=en")
        page.fill("#first_name", sample[0])
        page.fill("#surname", sample[1])
        page.click("#birth_date")
        page.keyboard.type("01011980")
        guest.pick_country("nationality", "CZE")
        page.fill("#doc_number", sample[2])
        guest.next()
        page.fill("#res_street", sample[3])
        page.fill("#res_city", sample[4])
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
        assert page.input_value("#first_name") == sample[0]
        assert page.eval_on_selector("#signature", "e => e.value").startswith("data:image/png")
        assert page.is_checked("#legal_ack")

        # Accept: Czech page, same answers, same step, signature and tick asked again.
        page.once("dialog", lambda dialog: dialog.accept())
        with page.expect_navigation():
            page.locator(f'[data-lang-draft][lang="cs"]').click()
        assert page.get_attribute("html", "lang") == "cs"
        assert progress() == before, (progress(), before)
        assert page.input_value("#first_name") == sample[0]
        assert page.input_value("#surname") == sample[1]
        assert page.input_value("#birth_date") == "01.01.1980"
        assert page.input_value("#nationality") == "CZE"
        assert page.input_value("#doc_number") == sample[2]
        assert page.input_value("#res_street") == sample[3]
        assert page.input_value("#res_city") == sample[4]
        assert page.eval_on_selector("#signature", "e => e.value") == ""
        assert not page.is_checked("#legal_ack")

        # Back to English with nothing to lose: no warning, still the same.
        shots = os.environ.get("UBYHOST_SHOTS_DIR")
        if shots:
            Path(shots).mkdir(parents=True, exist_ok=True)
            for width in (390, 768, 1280):
                page.set_viewport_size({"width": width, "height": 900})
                page.screenshot(path=str(Path(shots) / f"0979-review-cs-{width}.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 812})
        page.once("dialog", lambda dialog: pytest.fail("no warning expected"))
        with page.expect_navigation():
            pick("en")
        assert page.get_attribute("html", "lang") == "en"
        assert progress() == before
        assert page.input_value("#surname") == sample[1]
        assert page.input_value("#nationality") == "CZE"

        # Step 1 of a foreign nationality keeps its longer step count.
        page.locator("[data-guest-step]:not([hidden]) .g-wizard-nav button.secondary").first.click()
        page.locator("[data-guest-step]:not([hidden]) .g-wizard-nav button.secondary").first.click()
        guest.pick_country("nationality", "DEU")
        page.fill("#first_name", sample[0])
        pick("cs")
        page.wait_for_load_state()
        assert page.input_value("#nationality") == "DEU"
        assert page.input_value("#first_name") == sample[0]

        assert not [u for u in urls if any(s.lower() in u.lower() for s in sample)], urls
        assert "01.01.1980" not in " ".join(urls) and "01011980" not in " ".join(urls)
        assert page.evaluate("() => [localStorage.length, sessionStorage.length]") == [0, 0]
        assert not any(
            any(s in cookie["value"] for s in sample) for cookie in page.context.cookies()
        )
    finally:
        page.close()


def test_0979_language_switch_works_without_a_signature(live_server, browser, monkeypatch):
    """0979: with no signature and no tick, the language button still posts the
    open form back (the signature guard must not stop it) and asks nothing."""
    from app import config

    monkeypatch.setattr(config, "GUEST_PIN_REQUIRED", False)
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    token = f"browser-0959-nosig-{secrets.token_hex(4)}"
    stay = _fee_seed(token, signed=False)
    page = browser.new_page(viewport={"width": 390, "height": 812})
    sample = ["Synthetica", "Testovic", "SYN0959X", "Examplova 5", "Testov"]
    guest = Guest(page, 390, lang="cs")
    dialogs = []
    page.on("dialog", lambda dialog: (dialogs.append(dialog.message), dialog.dismiss()))

    def progress():
        return [int(n) for n in re.findall(r"\d+", page.inner_text("[data-wizard-label]"))[:2]]

    try:
        page.goto(f"{live_server}/l/{token}/{stay}/new?lang=cs")
        page.fill("#first_name", sample[0])
        page.fill("#surname", sample[1])
        page.click("#birth_date")
        page.keyboard.type("01011980")
        guest.pick_country("nationality", "CZE")
        page.fill("#doc_number", sample[2])
        guest.next()
        page.fill("#res_street", sample[3])
        page.fill("#res_city", sample[4])
        page.evaluate("() => { document.querySelector('#res_country').value = 'CZE'; }")
        guest.next()
        before = progress()
        assert before[0] == before[1], before  # on the last step, no signature, no tick
        assert page.eval_on_selector("#signature", "e => e.value") == ""
        assert not page.is_checked("#legal_ack")

        page.locator("[data-lang-menu] summary").click()
        with page.expect_navigation():
            page.locator('[data-lang-draft][lang="en"]').click()
        assert page.get_attribute("html", "lang") == "en"
        assert i18n.translator("en")("review_title") in page.inner_text("body")
        assert progress() == before, (progress(), before)
        assert page.input_value("#first_name") == sample[0]
        assert page.input_value("#surname") == sample[1]
        assert page.input_value("#birth_date") == "01.01.1980"
        assert page.input_value("#nationality") == "CZE"
        assert page.input_value("#doc_number") == sample[2]
        assert page.input_value("#res_street") == sample[3]
        assert page.input_value("#res_city") == sample[4]
        assert dialogs == [], dialogs
    finally:
        page.close()


def test_0979_discard_warning_cancel_keeps_draft(live_server, browser, monkeypatch):
    """0979: a drawn signature asks before a language switch; Cancel keeps the
    page as it was (same language, same answers, same URL, no navigation)."""
    from app import config

    monkeypatch.setattr(config, "GUEST_PIN_REQUIRED", False)
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    token = f"browser-0959-cancel-{secrets.token_hex(4)}"
    stay = _fee_seed(token, signed=False)
    page = browser.new_page(viewport={"width": 390, "height": 812})
    sample = ["Synthetica", "Testovic", "SYN0959X", "Examplova 5", "Testov"]
    guest = Guest(page, 390)

    def pick(lang):
        page.locator("[data-lang-menu] summary").click()
        page.locator(f'[data-lang-draft][lang="{lang}"]').click()

    try:
        page.goto(f"{live_server}/l/{token}/{stay}/new?lang=en")
        page.fill("#first_name", sample[0])
        page.fill("#surname", sample[1])
        page.click("#birth_date")
        page.keyboard.type("01011980")
        guest.pick_country("nationality", "CZE")
        page.fill("#doc_number", sample[2])
        guest.next()
        page.fill("#res_street", sample[3])
        page.fill("#res_city", sample[4])
        page.evaluate("() => { document.querySelector('#res_country').value = 'CZE'; }")
        guest.next()
        guest.sign()
        page.check("#legal_ack")

        # A drawn signature asks first; Accept moves to the Czech page.
        page.once("dialog", lambda dialog: dialog.accept())
        with page.expect_navigation():
            pick("cs")
        assert page.get_attribute("html", "lang") == "cs"
        assert page.input_value("#first_name") == sample[0]

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
        assert page.input_value("#first_name") == sample[0]
        assert page.input_value("#surname") == sample[1]
        assert page.input_value("#res_city") == sample[4]
        assert page.eval_on_selector("#signature", "e => e.value").startswith("data:image/png")
        assert page.is_checked("#legal_ack")
    finally:
        page.close()


# --- 0965 (B07): the review, the legal acknowledgement and the save action ---

_B07_LONG = {
    "first": "Maximiliana-Alexandra",
    "surname": "Hohenzollern-Sigmaringen-Vondrackova",
    "doc": "SYN0965LONGDOCUMENT27",
    "street": "Nábřeží Svobodného Československa 1234/56",
    "city": "Dolní Lhota u Dlouhého Města nad Labem",
}

_B07_GEOMETRY_JS = r"""
() => {
  const R = el => el.getBoundingClientRect();
  const step = document.querySelector('[data-guest-step]:not([hidden])');
  const rows = [...step.querySelectorAll('.g-review-row')].map(row => {
    const dt = row.querySelector('dt'), value = row.querySelector('.g-review-value');
    const edit = row.querySelector('.g-review-change'), r = R(row);
    return {
      label: dt.textContent.trim(), value: value.textContent.trim(),
      dtBottom: R(dt).bottom, dtLeft: R(dt).left,
      valueTop: R(value).top, valueLeft: R(value).left, valueRight: R(value).right,
      editLeft: R(edit).left, editRight: R(edit).right, editH: R(edit).height,
      rowRight: r.right,
    };
  });
  const legal = step.querySelector('.g-legal-notice'), review = step.querySelector('.g-review');
  const cs = getComputedStyle(legal);
  return {
    rows,
    overflow: document.documentElement.scrollWidth - window.innerWidth,
    legalBorders: [cs.borderLeftWidth, cs.borderRightWidth, cs.borderBottomWidth, cs.borderTopWidth],
    legalRadius: cs.borderTopLeftRadius, legalShadow: cs.boxShadow,
    reviewBottom: R(review).bottom, legalTop: R(legal).top,
    nestedCards: [...step.querySelectorAll('.g-card')].filter(c => !c.classList.contains('g-legal-notice')).length,
  };
}
"""

_B07_ACK_JS = r"""
() => {
  const rgb = value => {
    const nums = (value.match(/-?[\d.]+/g) || []).map(Number);
    return value.startsWith('color(') ? nums.slice(0, 3).map(n => n * 255) : nums.slice(0, 3);
  };
  const wrap = document.querySelector('.legal-ack');
  const cs = getComputedStyle(document.querySelector('#legal_ack').closest('.checkline'));
  return {
    border: rgb(cs.borderTopColor), background: rgb(cs.backgroundColor),
    outlineStyle: cs.outlineStyle, outlineWidth: parseFloat(cs.outlineWidth), outline: rgb(cs.outlineColor),
    invalidClass: wrap.classList.contains('is-invalid'),
    ariaInvalid: document.querySelector('#legal_ack').getAttribute('aria-invalid'),
  };
}
"""

_B07_STICKY_JS = r"""
() => {
  const R = el => el.getBoundingClientRect();
  const step = document.querySelector('[data-guest-step]:not([hidden])');
  const btn = step.querySelector(':scope > .g-btn[type=submit]');
  const rows = [...step.querySelectorAll('.g-review-row')];
  const legal = [...step.querySelectorAll('.g-legal-text > summary, .g-legal-text[open] p, .legal-ack .checkline')];
  const active = document.activeElement;
  return {
    position: getComputedStyle(btn).position, btnTop: R(btn).top, btnBottom: R(btn).bottom,
    btnHeight: R(btn).height, viewport: window.innerHeight,
    pad: parseFloat(getComputedStyle(document.documentElement).scrollPaddingBottom) || 0,
    lastRowBottom: R(rows[rows.length - 1]).bottom,
    legalBottoms: legal.map(e => R(e).bottom),
    activeTop: R(active).top, activeBottom: R(active).bottom, activeId: active.id || '',
  };
}
"""


def _b07_redder(color, margin):
    return color[0] - max(color[1], color[2]) >= margin


def _b07_greener(color, margin):
    return color[1] - max(color[0], color[2]) >= margin


# The acknowledgement colours ease over 0.14 s (guest.css). Read the settled colour,
# not the first frame of the transition (probe 0965 step 1: settled values are the
# brief's neutral, red and green; the first frame is the old colour).
_B07_SETTLE_JS = r"""
() => Promise.race([
  Promise.all(document.getAnimations().map(a => a.finished.catch(() => null))),
  new Promise(resolve => setTimeout(resolve, 1500)),
])
"""


def _b07_settle(page):
    page.evaluate(_B07_SETTLE_JS)


def _b07_shot(page, lang, width, name):
    shots = os.environ.get("UBYHOST_SHOTS_DIR")
    if not shots:
        return
    Path(shots).mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(Path(shots) / f"0965-{lang}-{width}-{name}.png"), full_page=False)


def _b07_open_review(live_server, browser, monkeypatch, token, lang, width):
    """Person 1 of 3, long synthetic answers, on the signature step with a drawn signature."""
    from app import config

    monkeypatch.setattr(config, "GUEST_PIN_REQUIRED", False)
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    stay = _seed(token)
    db.update("reservation", stay, {"expected_guests_override": 3})
    page = browser.new_page(viewport={"width": width, "height": 812})
    guest = Guest(page, width, lang)
    page.goto(f"{live_server}/l/{token}/{stay}/new?lang=en")
    page.fill("#first_name", _B07_LONG["first"])
    page.fill("#surname", _B07_LONG["surname"])
    page.click("#birth_date")
    page.keyboard.type("01011980")
    guest.pick_country("nationality", "DEU")
    page.fill("#doc_number", _B07_LONG["doc"])
    guest.next()
    page.fill("#res_street", _B07_LONG["street"])
    page.fill("#res_city", _B07_LONG["city"])
    guest.next()
    if lang != "en":
        # The language menu keeps the draft and the step (0979).
        page.locator("[data-lang-menu] summary").click()
        with page.expect_navigation():
            page.locator(f'[data-lang-draft][lang="{lang}"]').click()
        assert page.get_attribute("html", "lang") == lang
    assert guest.step() == i18n.translator(lang)("signature")
    guest.sign()
    return page, guest, stay


@pytest.mark.parametrize(("lang", "width"), [(l, w) for l in ("en", "cs") for w in (390, 768, 1280)])
def test_0965_review_is_one_surface_with_aligned_fact_rows(live_server, browser, monkeypatch, lang, width):
    """G04 + G03: one card, label / value / aligned Edit rows, a divider before the legal part,
    a short save action with the person progress apart, a quiet Back."""
    t = i18n.translator(lang)
    page, guest, _stay = _b07_open_review(live_server, browser, monkeypatch, f"b07-rows-{lang}-{width}", lang, width)
    try:
        page.locator(".g-review").scroll_into_view_if_needed()
        geo = page.evaluate(_B07_GEOMETRY_JS)
        rows = geo["rows"]
        assert len(rows) == 5, [r["label"] for r in rows]
        # The birth-date row missing at 390 px in Czech (seen in 0979) is an acceptance item here.
        birth = [r for r in rows if t("birth_date").strip() in r["label"]]
        # The review shows the date in the app's long format (base initBirthDate, Intl day/month/year).
        birth_value = "1 January 1980" if lang == "en" else "1. ledna 1980"
        assert len(birth) == 1 and birth[0]["value"] == birth_value, rows
        assert rows[0]["value"] == f"{_B07_LONG['first']} {_B07_LONG['surname']}"
        assert rows[-1]["value"].startswith(_B07_LONG["street"]) and _B07_LONG["city"] in rows[-1]["value"]
        assert geo["overflow"] <= 1, f"the page scrolls sideways by {geo['overflow']}px"
        for row in rows:
            assert row["dtBottom"] <= row["valueTop"] + 1, f"label is not above the value: {row['label']}"
            assert abs(row["dtLeft"] - row["valueLeft"]) <= 1, row["label"]
            assert row["valueRight"] <= row["editLeft"] + 0.5, f"value runs under Edit: {row['label']}"
            assert row["editRight"] <= row["rowRight"] + 0.5, row["label"]
            assert row["editH"] >= 44, row["label"]
        edges = [row["editRight"] for row in rows]
        assert max(edges) - min(edges) <= 1, f"Edit actions are not aligned: {edges}"
        # One outer surface: the legal part has no frame of its own, only a divider.
        assert geo["legalBorders"][:3] == ["0px", "0px", "0px"], geo["legalBorders"]
        assert geo["legalBorders"][3] == "1px", geo["legalBorders"]
        assert geo["legalRadius"] == "0px" and geo["legalShadow"] == "none"
        assert geo["reviewBottom"] <= geo["legalTop"] + 1
        assert geo["nestedCards"] == 0, "a card sits inside the step card"
        _b07_shot(page, lang, width, "review-legal-closed")

        # The short action and the person progress, apart.
        submit = page.locator("[data-guest-step]:not([hidden]) > .g-btn[type=submit]")
        assert submit.inner_text().strip() == t("save_continue_next")
        assert submit.evaluate("el => el.getBoundingClientRect().height") <= 64, "the action wraps"
        note = page.locator("[data-guest-step]:not([hidden]) > .g-save-note")
        assert note.inner_text().strip() == t("person_progress", current=1, total=3)
        back = page.locator("[data-guest-step]:not([hidden]) .g-wizard-nav .g-btn.secondary")
        assert back.count() == 1
        sizes = page.evaluate(
            "([b, s]) => [document.querySelector(b), document.querySelector(s)].map(e => e.getBoundingClientRect().width)",
            ["[data-guest-step]:not([hidden]) .g-wizard-nav .g-btn.secondary",
             "[data-guest-step]:not([hidden]) > .g-btn[type=submit]"],
        )
        assert sizes[0] < sizes[1] * 0.6, f"Back is as wide as the action: {sizes}"
        assert back.evaluate("el => getComputedStyle(el).backgroundColor") == "rgba(0, 0, 0, 0)"
        assert back.evaluate("el => el.getBoundingClientRect().height") >= 44

        # Legal open: still no frame, nothing sideways.
        page.locator(".g-legal-text > summary").click()
        assert page.locator(".g-legal-text").evaluate("el => el.open")
        assert page.evaluate(_B07_GEOMETRY_JS)["overflow"] <= 1
        _b07_shot(page, lang, width, "review-legal-open")
    finally:
        page.close()


@pytest.mark.parametrize(("lang", "width"), [(l, w) for l in ("en", "cs") for w in (390, 768, 1280)])
def test_0965_acknowledgement_is_neutral_then_positive_and_red_only_after_a_failed_submit(
    live_server, browser, monkeypatch, lang, width
):
    """G02: unchecked neutral, focus ring visible, attempted-invalid red, checked green, never red."""
    page, _guest, _stay = _b07_open_review(live_server, browser, monkeypatch, f"b07-ack-{lang}-{width}", lang, width)
    try:
        page.locator("#legal_ack").scroll_into_view_if_needed()
        idle = page.evaluate(_B07_ACK_JS)
        assert not idle["invalidClass"] and idle["ariaInvalid"] is None
        assert not _b07_redder(idle["border"], 30) and not _b07_greener(idle["border"], 8), idle
        assert not _b07_redder(idle["background"], 5) and not _b07_greener(idle["background"], 5), idle

        # Attempted submit with the box empty: the browser blocks it, the row turns red.
        page.locator("[data-guest-step]:not([hidden]) > .g-btn[type=submit]").click()
        assert "/save" not in page.url
        _b07_settle(page)
        bad = page.evaluate(_B07_ACK_JS)
        assert bad["invalidClass"] and bad["ariaInvalid"] == "true", bad
        assert _b07_redder(bad["border"], 30) and _b07_redder(bad["background"], 5), bad
        _b07_shot(page, lang, width, "ack-attempted-invalid")

        # Ticked: the error look is gone and the row is quietly positive.
        page.check("#legal_ack")
        page.mouse.move(2, 2)
        _b07_settle(page)
        ok = page.evaluate(_B07_ACK_JS)
        assert not ok["invalidClass"] and ok["ariaInvalid"] is None, ok
        assert _b07_greener(ok["border"], 8) and _b07_greener(ok["background"], 5), ok
        assert not _b07_redder(ok["border"], 30) and not _b07_redder(ok["background"], 5), ok
        page.locator(".g-legal-text > summary").click()
        _b07_settle(page)
        assert page.evaluate(_B07_ACK_JS)["border"] == ok["border"], "opening the legal text changed the tick"
        _b07_shot(page, lang, width, "ack-checked-legal-open")

        # Keyboard focus: a visible ring that is not the error colour, on a ticked and an empty box.
        for ticked in (True, False):
            if not ticked:
                page.uncheck("#legal_ack")
            page.focus(".g-review-change")
            for _ in range(24):
                page.keyboard.press("Tab")
                if page.evaluate("() => document.activeElement.id") == "legal_ack":
                    break
            assert page.evaluate("() => document.activeElement.id") == "legal_ack"
            _b07_settle(page)
            ring = page.evaluate(_B07_ACK_JS)
            assert ring["outlineStyle"] != "none" and ring["outlineWidth"] >= 2, ring
            assert not _b07_redder(ring["outline"], 30), ring
            if ticked:
                assert not _b07_redder(ring["border"], 30), ring
            _b07_shot(page, lang, width, f"ack-focus-{'checked' if ticked else 'empty'}")
        page.check("#legal_ack")

        # Success: the same synthetic data saves (disposable test database, manual mode, no filing).
        page.locator("[data-guest-step]:not([hidden]) > .g-btn[type=submit]").click()
        page.wait_for_load_state()
        assert "/save" not in page.url, page.inner_text(".g-err") if page.locator(".g-err").count() else page.url
        strip = page.locator(".g-saved-strip")
        assert strip.count() == 1 and i18n.translator(lang)("person_saved") in strip.inner_text()
        _b07_shot(page, lang, width, "saved")
    finally:
        page.close()


@pytest.mark.parametrize(("lang", "width"), [("en", 390), ("cs", 390), ("en", 768), ("en", 1280)])
def test_0965_sticky_action_never_covers_review_legal_text_or_focus(live_server, browser, monkeypatch, lang, width):
    """G03: measured with getBoundingClientRect at the bottom of the page and after Tab."""
    page, _guest, _stay = _b07_open_review(live_server, browser, monkeypatch, f"b07-sticky-{lang}-{width}", lang, width)
    try:
        for legal_open in (False, True):
            if legal_open:
                page.locator(".g-legal-text > summary").click()
            page.evaluate("() => window.scrollTo({top: document.documentElement.scrollHeight, behavior: 'instant'})")
            page.wait_for_timeout(250)
            m = page.evaluate(_B07_STICKY_JS)
            if width <= 560:
                assert m["position"] == "sticky", m
                assert m["pad"] >= 96, f"no scroll padding for the sticky action: {m['pad']}"
            assert m["btnBottom"] <= m["viewport"] + 1, "the action is cut off at the bottom"
            assert m["lastRowBottom"] <= m["btnTop"] + 1 or m["lastRowBottom"] < 0, "the action covers the last fact row"
            for bottom in m["legalBottoms"]:
                assert bottom <= m["btnTop"] + 1, f"the action covers legal text (legal_open={legal_open}): {m}"
            _b07_shot(page, lang, width, f"bottom-legal-{'open' if legal_open else 'closed'}")
        # Tab from the top of the review to the acknowledgement: the focused control stays clear of the bar.
        page.evaluate("() => document.querySelector('.g-review').scrollIntoView({block: 'start', behavior: 'instant'})")
        page.focus(".g-review-change")
        seen = []
        for _ in range(24):
            page.keyboard.press("Tab")
            page.wait_for_timeout(60)
            m = page.evaluate(_B07_STICKY_JS)
            seen.append(m["activeId"])
            overlap = m["activeTop"] < m["btnBottom"] and m["activeBottom"] > m["btnTop"]
            assert not overlap, f"the sticky action covers the focused control {m['activeId']!r}: {m}"
            if m["activeId"] == "legal_ack":
                break
        assert seen[-1] == "legal_ack", seen
    finally:
        page.close()


@pytest.mark.parametrize("lang", ["en", "cs"])
def test_0965_every_edit_returns_to_its_step_and_keeps_the_data(live_server, browser, monkeypatch, lang):
    """Edit from the review lands on the owning step, focus on the field, nothing typed is lost."""
    t = i18n.translator(lang)
    page, guest, _stay = _b07_open_review(live_server, browser, monkeypatch, f"b07-edit-{lang}", lang, 390)
    try:
        signature = page.eval_on_selector("#signature", "e => e.value")
        assert signature.startswith("data:image/png")
        before = page.evaluate("() => [...document.querySelectorAll('.g-review-row')].map(r => r.textContent)")
        owners = [t("your_details")] * 4 + [t("residence_title")]
        focus_ids = ["first_name", "birth_date", "", "doc_number", "res_street"]
        assert len(before) == 5
        for index in range(5):
            page.locator(".g-review-change").nth(index).scroll_into_view_if_needed()
            page.locator(".g-review-change").nth(index).click()
            page.wait_for_timeout(900)
            assert guest.step() == owners[index], (index, guest.step())
            if focus_ids[index]:
                assert page.evaluate("() => document.activeElement.id") == focus_ids[index], index
            assert page.input_value("#first_name") == _B07_LONG["first"]
            assert page.input_value("#surname") == _B07_LONG["surname"]
            assert page.input_value("#birth_date") == "01.01.1980"
            assert page.input_value("#nationality") == "DEU"
            assert page.input_value("#doc_number") == _B07_LONG["doc"]
            assert page.input_value("#res_street") == _B07_LONG["street"]
            assert page.input_value("#res_city") == _B07_LONG["city"]
            assert page.eval_on_selector("#signature", "e => e.value") == signature
            while guest.step() != t("signature"):
                guest.next()
            assert page.evaluate("() => [...document.querySelectorAll('.g-review-row')].map(r => r.textContent)") == before
    finally:
        page.close()


def test_0965_shortened_save_action_exists_in_all_six_guest_languages():
    """The one action key is short in every language and no longer says "continue to the next person"."""
    old = {
        "en": "Save and continue to the next person",
        "cs": "Uložit a pokračovat k další osobě",
        "de": "Speichern und mit der nächsten Person fortfahren",
        "es": "Guardar y continuar con la siguiente persona",
        "fr": "Enregistrer et continuer avec la personne suivante",
        "uk": "Зберегти й перейти до наступної особи",
    }
    assert set(old) == set(i18n.LANGUAGES)
    for lang, previous in old.items():
        label = i18n.STRINGS[lang]["save_continue_next"]
        assert label and label != previous, lang
        assert len(label) <= 26, (lang, label)
    assert len({i18n.STRINGS[lang]["save_continue_next"] for lang in old}) == 6

# --- 1031: the Check box follows every edit (minor, same town, other town) -----------------

SHOTS_1031 = Path("/mnt/project-files/ux-shots/stayfee-sametown")
_ADULT_1031, _MINOR_1031 = "15062001", "15062010"


def _open_1031(live_server, browser, monkeypatch, token, addr_obec, city, city_en=None):
    """A Czech guest on the Check step (signature step, signed), property in ``addr_obec``."""
    from app import config

    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    monkeypatch.setattr(config, "GUEST_PIN_REQUIRED", False)
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    stay = _fee_seed(token, signed=False)
    row = db.query_one("SELECT apartment_id FROM reservation WHERE id = ?", (stay,))
    db.update("apartment", row["apartment_id"], {"addr_obec": addr_obec, "city_en": city_en})
    page = browser.new_page(viewport={"width": 390, "height": 812})
    guest = Guest(page, 390, "en")
    page.goto(f"{live_server}/l/{token}/{stay}/new?lang=en")
    page.fill("#first_name", "Test")
    page.fill("#surname", "Sametown")
    page.click("#birth_date")
    page.keyboard.type(_ADULT_1031)
    guest.pick_country("nationality", "CZE")
    page.fill("#doc_number", "123456789")
    guest.next()
    page.fill("#res_street", "Testovaci 1")
    page.fill("#res_city", city)
    if page.input_value("#res_country") != "CZE":
        guest.pick_country("res_country", "CZE")
    guest.next()
    assert guest.step() == i18n.translator("en")("signature")
    guest.sign()
    return page, guest, stay


def _box_1031(page):
    """[hidden, amount text, data-fee-live, data-obec-rule] of the Check box."""
    page.wait_for_timeout(300)
    return page.evaluate("""() => {
        const b = document.getElementById('fee-estimate');
        if (!b) return [true, '', null, null];
        return [b.hidden, b.querySelector('.g-fee-amt').textContent.trim(),
                b.getAttribute('data-fee-live'), b.getAttribute('data-obec-rule')];
    }""")


def _change_1031(page, guest, row, field, value):
    """Change on Check row ``row`` (1 = birth date, 4 = home address), type, go back to Check."""
    sign = i18n.translator("en")("signature")
    page.locator(".g-review-change").nth(row).scroll_into_view_if_needed()
    page.locator(".g-review-change").nth(row).click()
    page.wait_for_timeout(900)
    page.fill(field, "")
    if field == "#birth_date":
        page.click(field)
        page.keyboard.type(value)
    else:
        page.fill(field, value)
    while guest.step() != sign:
        guest.next()


def test_1031_check_box_follows_every_change(live_server, browser, monkeypatch):
    """Owner's case: Prague flat, 3 nights x 50. Same town -> hidden; other town -> 150;
    minor -> hidden; every Change re-counts. Saved charge = last box."""
    from app import stay_fee

    token = f"browser-1031-{secrets.token_hex(4)}"
    page, guest, stay = _open_1031(live_server, browser, monkeypatch, token, "Praha", "Prague")
    try:
        steps = [
            (None, None, None, True),                      # adult, Prague: same town
            (4, "#res_city", "Brno", False),               # adult, other town: 150
            (1, "#birth_date", _MINOR_1031, True),         # minor, Brno
            (1, "#birth_date", _ADULT_1031, False),        # adult again, Brno: 150
            (4, "#res_city", "Praha 3 - Žižkov", True),    # district form of the same town
            (4, "#res_city", "Brno", False),
            (4, "#res_city", "Prague", True),              # back to the owner's case
        ]
        for row, field, value, want_hidden in steps:
            if row is not None:
                _change_1031(page, guest, row, field, value)
            hidden, amount, live, rule = _box_1031(page)
            seen = (row, value, hidden, amount, live, rule)
            assert hidden == want_hidden, seen
            if not want_hidden:
                assert amount == "150 CZK", seen
            if value == "Brno" and row == 4:
                SHOTS_1031.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(SHOTS_1031 / "check-othertown-390.png"), full_page=True)
        SHOTS_1031.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS_1031 / "check-sametown-390.png"), full_page=True)
        # Save with the last values (adult, Prague) and check the stored charge equals the box: 0.
        page.check("#legal_ack")
        page.locator("form[action*='/save'] button[type=submit]").last.click()
        page.wait_for_load_state("networkidle")
        res = db.query_one("SELECT * FROM reservation WHERE id = ?", (stay,))
        apt = db.query_one("SELECT * FROM apartment WHERE id = ?", (res["apartment_id"],))
        assert db.query_one("SELECT COUNT(*) AS n FROM guest WHERE reservation_id = ?", (stay,))["n"] == 1
        assert stay_fee.charge_for_reservation(apt, res)["total_czk"] == 0
    finally:
        page.close()
    row = db.query_one("SELECT * FROM reservation WHERE id = ?", (stay,))
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (row["apartment_id"],))
    assert stay_fee.same_obec_resident({"res_country": "CZE", "res_city": "Prague"}, apartment)


def test_1031_official_name_and_district_form_hide_the_box(live_server, browser, monkeypatch):
    token = f"browser-1031b-{secrets.token_hex(4)}"
    page, _guest, _stay = _open_1031(live_server, browser, monkeypatch, token,
                                     "Hlavní město Praha", "Praha 1 - Staré Město")
    try:
        assert _box_1031(page)[0] is True, _box_1031(page)
    finally:
        page.close()


def test_1031_unknown_property_town_shows_the_amount_and_says_why(live_server, browser, monkeypatch):
    token = f"browser-1031c-{secrets.token_hex(4)}"
    page, _guest, _stay = _open_1031(live_server, browser, monkeypatch, token, "", "Prague", city_en=None)
    try:
        hidden, amount, _live, rule = _box_1031(page)
        assert (hidden, amount, rule) == (False, "150 CZK", None)
        assert page.locator("#fee-obec-unknown").count() == 1
        page.locator("#fee-estimate").scroll_into_view_if_needed()
        SHOTS_1031.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS_1031 / "check-unknown-town-390.png"), full_page=True)
    finally:
        page.close()


# --- 1031b: every Prague spelling hides the Check box for a Prague flat; a minor too -------

_PRAGUE_1031B = [
    ("Praha", True), ("Prague", True), ("praha 1", True), ("Praha 22", True), ("PRAHA 17", True),
    ("Praha 17 - Řepy", True), ("praha 17 - repy", True), ("Praha-Řepy", True),
    ("praha 6 – Dejvice", True), ("Praha – Řepy", True), ("Hlavní město Praha", True),
    ("hl. m. praha", True), ("Hl. m. Praha", True),
    ("Řepy", False),   # owner 2026-11-09: a bare district name stays liable
    ("Brno", False),
]


@pytest.mark.parametrize("addr_obec, city_en", [("Praha", None), ("", "Prague")])
def test_1031b_prague_spellings_and_minor(live_server, browser, monkeypatch, addr_obec, city_en):
    """Prague flat (addr_obec Praha, or only city_en Prague), 3 nights x 50, Czech adult guest."""
    token = f"browser-1031d-{secrets.token_hex(4)}"
    page, guest, _stay = _open_1031(live_server, browser, monkeypatch, token, addr_obec,
                                    "Praha 17 - Řepy", city_en=city_en)
    seen = []
    try:
        hidden, amount, _live, _rule = _box_1031(page)
        seen.append(("Praha 17 - Řepy", hidden, amount))
        for city, want_hidden in _PRAGUE_1031B:
            _change_1031(page, guest, 4, "#res_city", city)
            hidden, amount, _live, _rule = _box_1031(page)
            seen.append((city, hidden, amount))
        # Minor path: Brno resident (liable as adult), born 2010 -> exempt, back to adult -> 150.
        for birth in (_MINOR_1031, _ADULT_1031, _MINOR_1031):
            _change_1031(page, guest, 1, "#birth_date", birth)
            hidden, amount, _live, _rule = _box_1031(page)
            seen.append((f"Brno born {birth[-4:]}", hidden, amount))
        print("1031b", addr_obec or city_en, seen)
        want = ([True] + [w for _c, w in _PRAGUE_1031B] + [True, False, True])
        assert [s[1] for s in seen] == want, seen
        assert all(s[2] == "150 CZK" for s, w in zip(seen, want) if not w), seen
    finally:
        page.close()
