#!/usr/bin/env python3
"""Count taps and typed fields for six host and guest flows at 390 px.

Owner use against a local dev server only, never production.

The script never clicks a police send button and never calls a submit route.
The save step of each flow is counted as one tap but is not pressed, so no
write reaches the database.

Usage (from App/):
  .venv/bin/python scripts/flow_taps.py --base http://127.0.0.1:8000 \
      --cookie "NAME=VALUE" --ids '{"apartment_id": "1", "entity_id": "1"}' \
      --out ../docs/tasks/screenshots-0841/flow-taps.json

ids keys (a flow whose key is missing is reported as not_measured):
  apartment_id, entity_id, stay_id, guest_path (path of the guest form),
  dashboard_path (default "/"), invoice_query (default ""), date_from,
  date_to, cal_arrival, cal_departure, buyer_name, surname, street.
"""

import argparse
import json

from playwright.sync_api import sync_playwright

VIEWPORT = {"width": 390, "height": 844}

DEFAULTS = {
    "date_from": "2027-03-10",
    "date_to": "2027-03-12",
    "cal_arrival": "2027-03-10",
    "cal_departure": "2027-03-12",
    "buyer_name": "Test Buyer",
    "surname": "Tester",
    "street": "Test Street 1",
}

CALENDAR_ACTIONS = [
    '[data-cal-event][draggable="true"]',
    "[data-cal-resize]",
    "[data-cal-move]",
    "[data-cal-extend]",
    "[data-cal-cancel]",
]

CLEANING_ACTIONS = [
    'form[action*="/cleaned"]',
    'form[action*="/assign"]',
    "[data-cleaning-assign]",
    "[data-cleaning-done]",
    'select[name*="assign"]',
]

# Read only: reports whether the first single-stay submit form asks for a confirm.
SUBMIT_CONFIRM_JS = """() => {
  const f = document.querySelector('form[action$="/submit"]');
  if (!f) return null;
  const guarded = f.hasAttribute('data-confirm') || !!f.querySelector('[data-confirm]')
    || !!f.closest('[data-confirm]');
  return guarded ? 'form[action$="/submit"] [data-confirm]' : 'form[action$="/submit"] (no confirm)';
}"""


class Recorder:
    """Counts what a person would do on the page. It never presses the save step."""

    def __init__(self, page):
        self.page = page
        self.taps = 0
        self.typed = 0
        self.prefilled = 0

    def tap(self, selector):
        self.page.click(selector)
        self.taps += 1

    def pick(self, selector, value):
        """Choose an option in a select: one tap, or prefilled when already right."""
        if self.page.eval_on_selector(selector, "el => el.value") == value:
            self.confirm(selector)
            return
        self.page.select_option(selector, value)
        self.taps += 1

    def type(self, selector, text):
        self.page.fill(selector, text)
        self.typed += 1

    def confirm(self, selector):
        if not self.page.is_visible(selector):
            raise RuntimeError(f"prefilled field not visible: {selector}")
        self.prefilled += 1

    def fill(self, selector, want):
        """Type only when the field does not already hold the wanted value."""
        if self.page.input_value(selector) == want:
            self.confirm(selector)
        else:
            self.type(selector, want)

    def save_unpressed(self):
        """The save tap is counted, never pressed."""
        self.taps += 1

    def result(self):
        return {"taps": self.taps, "typed": self.typed, "prefilled": self.prefilled}


def add_stay_panel(rec, base, ids):
    rec.page.goto(base + "/reservations")
    if not rec.page.is_visible("#add-stay-panel"):
        rec.tap('[data-toggle-panel="add-stay-panel"]')
    rec.pick("#new_apartment", ids["apartment_id"])
    rec.fill("#date_from", ids.get("date_from", DEFAULTS["date_from"]))
    rec.fill("#date_to", ids.get("date_to", DEFAULTS["date_to"]))
    rec.save_unpressed()


def add_stay_calendar(rec, base, ids):
    rec.page.goto(base + ids.get("dashboard_path", "/"))
    rec.tap("[data-cal-day]")
    rec.tap("[data-cal-day-add]")
    rec.fill("#cal-arrival", ids.get("cal_arrival", DEFAULTS["cal_arrival"]))
    rec.fill("#cal-departure", ids.get("cal_departure", DEFAULTS["cal_departure"]))
    rec.save_unpressed()


def copy_guest_link_row(rec, base, ids):
    rec.page.goto(base + "/reservations")
    rec.tap('[data-copy^="stay-link-"]')


def guest_second_person(rec, base, ids):
    rec.page.goto(base + ids["guest_path"])
    rec.fill("#surname", ids.get("surname", DEFAULTS["surname"]))
    rec.fill("#res_street", ids.get("street", DEFAULTS["street"]))
    rec.save_unpressed()


def invoice_for_stay(rec, base, ids):
    rec.page.goto(base + "/invoices/new" + ids.get("invoice_query", ""))
    rec.tap('button[name="fill_from_guest"]')
    rec.fill("#buyer_name", ids.get("buyer_name", DEFAULTS["buyer_name"]))
    rec.save_unpressed()


def property_quick_create(rec, base, ids):
    rec.page.goto(base + "/apartments/new")
    rec.pick("#legal_entity_id", ids["entity_id"])
    rec.save_unpressed()


FLOWS = {
    "add_stay_panel": add_stay_panel,
    "add_stay_calendar": add_stay_calendar,
    "copy_guest_link_row": copy_guest_link_row,
    "guest_second_person": guest_second_person,
    "invoice_for_stay": invoice_for_stay,
    "property_quick_create": property_quick_create,
}


def _first_match(page, selectors):
    for selector in selectors:
        if page.locator(selector).count() > 0:
            return selector
    return None


def inspect_open_items(page, base, ids):
    """Read the DOM only. Never clicks, never calls a submit route."""
    page.goto(base + ids.get("dashboard_path", "/"))
    cal = _first_match(page, CALENDAR_ACTIONS)
    page.goto(base + "/cleaning")
    clean = _first_match(page, CLEANING_ACTIONS)
    page.goto(base + "/reservations/" + str(ids["stay_id"]))
    submit = page.evaluate(SUBMIT_CONFIRM_JS)
    return {
        "calendar_move_extend_cancel": {
            "present": cal is not None,
            "evidence": cal or "no drag, resize or cancel control on the dashboard calendar",
        },
        "cleaning_mark_assign": {
            "present": clean is not None,
            "evidence": clean or "no mark-cleaned or assign control on /cleaning",
        },
        "single_send_confirm": {
            "present": bool(submit and "[data-confirm]" in submit),
            "evidence": submit or "no submit form on the stay page",
        },
    }


def _context(browser, base, cookie):
    context = browser.new_context(
        viewport=VIEWPORT, device_scale_factor=1, is_mobile=True, has_touch=True
    )
    if cookie:
        name, _, value = cookie.partition("=")
        context.add_cookies([{"name": name, "value": value, "url": base}])
    return context


def run_flow(browser, name, base, ids, cookie=None, shot_path=None, on_request=None):
    """Run one flow in a fresh 390 px context. Returns its result dict."""
    context = _context(browser, base, cookie)
    page = context.new_page()
    if on_request:
        page.on("request", on_request)
    rec = Recorder(page)
    try:
        FLOWS[name](rec, base, ids)
        result = rec.result()
    except Exception as exc:
        first_line = str(exc).splitlines()[0][:200] if str(exc) else ""
        result = {**rec.result(), "not_measured": f"{type(exc).__name__}: {first_line}"}
    if shot_path:
        page.screenshot(path=shot_path)
    context.close()
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Count taps and typed fields per flow at 390 px.")
    parser.add_argument("--base", required=True, help="local dev server, e.g. http://127.0.0.1:8000")
    parser.add_argument("--cookie", help='session cookie as "NAME=VALUE"')
    parser.add_argument("--ids", default="{}", help="JSON object of seeded ids (see module docstring)")
    parser.add_argument("--out", required=True, help="JSON file to write")
    parser.add_argument("--chromium", help="optional Chromium executable path")
    args = parser.parse_args(argv)

    ids = json.loads(args.ids)
    base = args.base.rstrip("/")
    flows = {}
    open_items = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, executable_path=args.chromium or None)
        for name in FLOWS:
            flows[name] = run_flow(browser, name, base, ids, args.cookie)
        context = _context(browser, base, args.cookie)
        try:
            open_items = inspect_open_items(context.new_page(), base, ids)
        except Exception as exc:
            open_items = {"error": f"{type(exc).__name__}: {str(exc).splitlines()[0][:200]}"}
        context.close()
        browser.close()

    data = {"flows": flows, "open_items": open_items}
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    print(json.dumps(flows, indent=2))


if __name__ == "__main__":
    main()
