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
Chromium - pick the stay, set the group size with the stepper, claim by
e-mail, then fill, sign and submit one form per person - and measures the
layout on every screen. It is skipped when Playwright or Chromium is missing;
the ``guest-browser`` CI job installs both, so it always runs on a pull request.

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

import pytest

# In CI the browser job sets UBYHOST_REQUIRE_BROWSER, so a missing Playwright
# or Chromium fails the job instead of skipping these tests without a word.
REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import claim, db, mail  # noqa: E402


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

  document.querySelectorAll('label, button, a.g-btn, .tw-chip, h2, summary').forEach(el => {
    if (!vis(el) || clipped(el) || el.closest('.g-checkin-steps')) return;
    if (el.scrollWidth > el.clientWidth + 1 && getComputedStyle(el).overflow !== 'visible')
      out.push(`text is cut off: ${name(el)} "${el.textContent.trim().slice(0, 40)}"`);
  });

  // Words meant only for screen readers must never be painted.
  document.querySelectorAll('.sr-only, .g-sr-only').forEach(el => {
    if (el.textContent.trim() && R(el).width > 2 && !clipped(el))
      out.push(`screen-reader text is visible: "${el.textContent.trim()}"`);
  });

  const scope = document.querySelector('[data-guest-step]:not([hidden])') || document.querySelector('main');
  const controls = [...scope.querySelectorAll('input[type=text], input[type=email], input:not([type]), select, .tw-combo input')]
    .filter(el => vis(el) && !el.closest('.tw-pin') && !el.closest('.tw-stepper') && !el.classList.contains('tw-vh'));
  const heights = [...new Set(controls.map(el => Math.round(R(el).height)))];
  if (heights.length > 1)
    out.push(`text boxes differ in height: ${controls.map(el => name(el) + '=' + Math.round(R(el).height)).join(', ')}`);

  scope.querySelectorAll('.g-row').forEach(row => {
    const fields = [...row.children].filter(vis);
    if (fields.length < 2) return;
    const tops = fields.map(f => R(f).top);
    if (Math.max(...tops) - Math.min(...tops) > 2) return;  // stacked on a phone
    const first = f => [...f.querySelectorAll('input:not([type=hidden]), select')].filter(el => vis(el) && !el.classList.contains('tw-vh'))[0];
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
  if (gaps.length > 1 && Math.max(...gaps) - Math.min(...gaps) > 6)
    out.push(`the space between fields is uneven: ${gaps.join(', ')}px`);

  scope.querySelectorAll('button, a.g-btn, .tw-chip').forEach(el => {
    if (!vis(el) || el.closest('.g-checkin-step')) return;
    const r = R(el);
    if (r.height < 44) out.push(`tap target under 44px: ${name(el)} "${el.textContent.trim().slice(0, 30)}" (${Math.round(r.height)}px)`);
  });
  return out;
}
"""

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
            chromium = playwright.chromium.launch()
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


class Guest:
    def __init__(self, page, width):
        self.page = page
        self.width = width
        self.problems = []

    def check_layout(self, where: str):
        for problem in self.page.evaluate(LAYOUT_JS):
            self.problems.append(f"{where}: {problem}")

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
        self.check_layout(f"guest {number}, details (empty)")
        page.fill("#first_name", first)
        # A phone keyboard opening shrinks the viewport and fires resize while
        # the signature step is still hidden. That is what left the pad 0 x 0.
        page.set_viewport_size({"width": self.width, "height": 480})
        page.set_viewport_size({"width": self.width, "height": 812})
        page.fill("#surname", surname)
        page.click("#birth_date_d")
        page.keyboard.type(birth)
        self.pick_country("nationality", "DEU")
        assert page.eval_on_selector("#birth_date", "e => e.value") == f"{birth[:2]}.{birth[2:4]}.{birth[4:]}"
        assert page.eval_on_selector("#nationality", "e => e.value") == "DEU"
        self.check_layout(f"guest {number}, details")
        self.next()
        page.fill("#doc_number", document)
        self.check_layout(f"guest {number}, document")
        self.next()
        if not page.input_value("#res_street"):
            page.fill("#res_street", "Hauptstraße 12")
            page.fill("#res_city", "Berlin")
            self.pick_country("res_country", "DEU")
        self.check_layout(f"guest {number}, home")
        self.next()
        self.sign()
        self.check_layout(f"guest {number}, signature")
        self.next()
        self.check_layout(f"guest {number}, check")
        for box in page.locator("[data-guest-step]:not([hidden]) input[type=checkbox][required]").all():
            box.check()
        page.locator("[data-guest-step]:not([hidden]) button[type=submit]").last.click()
        page.wait_for_load_state()
        assert "/save" not in page.url, page.inner_text(".g-err") if page.locator(".g-err").count() else page.url


@pytest.mark.parametrize("width", [320, 375, 1280])
def test_a_group_of_three_registers_everyone_on_one_phone(live_server, browser, width):
    token = f"browser-e2e-{width}"
    db.execute("DELETE FROM rate_limit_event")
    stay = _seed(token)
    context = browser.new_context(viewport={"width": width, "height": 812}, locale="en-GB")
    page = context.new_page()
    script_errors = []
    page.on("pageerror", lambda error: script_errors.append(str(error)))
    guest = Guest(page, width)
    try:
        page.goto(f"{live_server}/l/{token}?lang=en")
        page.locator(f"a[href*='/l/{token}/{stay}']").first.click()
        page.wait_for_load_state()
        guest.check_layout("claim")

        # The group size never starts empty, and the stepper counts from it.
        assert page.input_value("#party_size") == "1"
        page.locator(".tw-step-btn").last.click()
        page.locator(".tw-step-btn").last.click()
        assert page.input_value("#party_size") == "3"
        page.fill("#guest_email", "family@example.test")
        page.locator("form button[type=submit]").first.click()
        page.wait_for_load_state()

        page.goto(_claim_link(live_server, stay))
        page.locator("form button[type=submit]").first.click()
        page.wait_for_load_state()

        for number, person in enumerate(PEOPLE, start=1):
            if number > 1:
                link = page.get_by_role("link", name="Add a person")
                assert link.count() == 1
                guest.check_layout(f"saved, before guest {number}")
                link.click()
                page.wait_for_load_state()
            guest.fill_form(number, 3, person)

        stored = db.query("SELECT * FROM guest WHERE reservation_id = ?", (stay,))
        assert sorted(row["first_name"].upper() for row in stored) == ["ANNA", "JONAS", "LENA"]
        assert all(row["signature_png"].startswith("data:image/png;base64,") for row in stored)
        assert page.locator(".tw-bp").count() == 3
        guest.check_layout("done")
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
        for english in ("Continue", "Guest 1", "Day", "Month", "Year", "Sign here", "Start typing"):
            assert english not in text, f"{english!r} on a Czech page"
        assert page.evaluate(
            "() => document.querySelector('[data-guest-step]:not([hidden])').getAttribute('data-step-title')"
        ) == "Vaše údaje"
    finally:
        context.close()
