# 0907: Geometry and design test pass: invoice buyer switch and guest step titles

Status: review
Depends on: 0885 and 0886 (merged in #734, bb01bb5) | Base commit: bb01bb5 | Branch: the orchestrator's branch (do not create one)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Length: about 480 lines. The read hook blocks whole-file reads over 350 lines: read this brief in ranges of 150 lines or fewer.
Number: 0887 is reserved for #725 and 0888 to 0895 are taken by open PRs #737, #739 and #740 (see `docs/tasks/0869-brief-renumbering.md` on #739), so this brief is 0907.

## 1. Objective

Josef's rules (owner, 2026-11-02) become browser tests on the two pages that #734 changed, at 320, 390, 768, 1024, 1280 and 1440 px:
- no page scroll sideways;
- text keeps 16 px or more from every edge of its card;
- no fine print: no text under 13 px (the "?" glyph in its ring is the one exception);
- neighbouring controls keep 12 px or more apart;
- a button never sits over text and keeps 12 px or more from it;
- a field keeps 12 px or more from text that is not its own label or hint;
- the help "?" is an 18 px ring (16 to 20) on the line of its label, with a 44 px tap area.

Pages: (a) the invoice form buyer block (`App/app/templates/invoice_form.html`, `.invoice-customer`) with **Guest** selected and with **Company** selected; (b) the guest form, person 2: step 1 (details), the address step and the signature step (`App/app/templates/guest/form.html`). The orchestrator ran every check below on bb01bb5 in Chromium. The CSS changes in steps 1 and 2 are the fixes for every finding of that run, so after them all tests should pass. Light mode only. No new dependency.

## 2. Context

- **First command** (must print nothing): `git diff --stat bb01bb5 -- App/app/static/host2.css App/app/static/guest.css App/app/templates/base.html App/app/templates/guest/base.html App/tests/v2_mockup.py App/tests/test_invoice_autofill.py App/tests/test_guest_browser_e2e.py 2>&1 | tail -30`. If it prints anything, or an anchor below is not found exactly once, STOP (section 8).
- **Do not commit, do not push, do not open a PR.** The orchestrator commits. This replaces the per-step commit in executor.md. Leave every change in the working tree.
- **Browser:** every browser command runs with `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium UBYHOST_REQUIRE_BROWSER=1` and `-rs`. Any skip is a failure.
- **Where the CSS lives:** `invoice_form.html` is **not** a v2 page (no `{% set v2 = true %}`), so it loads `host2.css` (via `App/app/templates/base.html` line 31), not `app2.css`. Do not edit `app2.css`. The guest form loads `guest.css` (via `App/app/templates/guest/base.html` line 14).
- **Lint:** `host2.css` is checked by `scripts/design_lint.py` (rule S2: no bare px in margin, padding, gap, border-radius or font-size; use `var(--space-*)` and `var(--size-*)`). `width`, `height` and `inset` may use px. `invoice_form.html` is an enforced template: a new class there fails rule T3, so add no class. `guest.css` is not linted; it uses px.
- **Reused helpers:** the six widths are `WIDTHS` in `App/tests/v2_mockup.py` (the shared geometry module, `geometry_findings` lives there). The new `spacing_findings` goes in the same module. Chromium starts through `_launch` and the session cookie comes from `_browser_session_cookie` in `App/tests/test_invoice_stay_browser.py` (the 0886 screenshot test already uses both). The guest checks go into the `Guest` class of `App/tests/test_guest_browser_e2e.py`, next to the 0885 `check_help_beside_title`, and report through `self.problems`, which the test asserts empty at the end.
- **Rules of the test:** never change a number in a check (16, 13, 12, 11.5, 15.5, 4, 16 to 20, 44), never add a selector to `skip`, `glyphs` or the pinned rule, and never drop a width. A finding is fixed in CSS, never in the test.
- What the CSS changes do, for the reviewer: the choice cards get 16 px padding (text was 15 px from the top edge); the label no longer stretches, so the "?" sits 12 px after "Company" instead of wrapping under it; the "?" ring is 18 px with a 44 px hit area on the whole invoice page (it was 24 px); the IČO field and the ARES button are 12 px apart (were 8) and the IČO label is 12 px above the button (was 10); the "Filled in from the guest" note is 14 px (was 12). On the guest form: the "Person 2" chip is 13 px (was 11.5); Back and Continue are 12 px apart (were 10); the review list rows and the "Change" buttons keep 12 px (were 9 and 10); the review block starts 18 px under the signature pad's Clear button (was 7); a two-field row keeps the 16 px field rhythm below it, so the next label is no longer 2 px under the input above ("Date of birth" under Surname, "Travel document number" under Nationality).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/static/host2.css` | edit | Step 1: invoice buyer block spacing |
| `App/app/static/guest.css` | edit | Step 2: chip size, wizard nav gap, row rhythm, review list spacing |
| `App/app/templates/base.html` | edit | Step 3: host2.css cache key |
| `App/app/templates/guest/base.html` | edit | Step 3: guest.css cache key |
| `App/tests/static_versions.json` | regenerate | Step 3 (`--write`) |
| `App/tests/v2_mockup.py` | edit | Step 4: `spacing_findings` helper |
| `App/tests/test_invoice_autofill.py` | edit | Step 5: buyer block test at six widths |
| `App/tests/test_guest_browser_e2e.py` | edit | Step 6: guest checks at six widths |
| `docs/tasks/screenshots-0907/` | new | 6 PNGs (step 7) |
| `docs/tasks/0907-report.md` | new | Report |

No other file may change. The two templates `invoice_form.html` and `guest/form.html` need no change; touch them only under section 8's last fix rule.

## 4. Steps

Find each anchor with `grep -nF "<text>" <file>`. Every anchor must match exactly once. Use the Edit tool.

### Step 1. `App/app/static/host2.css`

1a. Anchor (exact line):
```css
.host-workspace .invoice-lookup-row { display: flex; gap: var(--space-2); }
```
Replace with:
```css
.host-workspace .invoice-lookup-row { display: flex; gap: var(--space-3); }
```
1b. Anchor (exact line):
```css
.host-workspace .invoice-f-half { grid-column: span 3; }
```
Insert directly after it:
```css
/* 0907: Josef's spacing rules on the buyer switch: text 16 px inside the card, the "?" an 18 px ring right after "Company", no fine print */
.host-workspace .invoice-customer .ui-choice-card { padding: var(--space-4); }
.host-workspace .invoice-customer .ui-choice-card-label { flex: 0 1 auto; }
.host-workspace .invoice-customer .hint { font-size: var(--size-14); }
.host-workspace .invoice-lookup-ico > label { margin-bottom: var(--space-3); }
.host-workspace .invoice-form .help-tip-btn { width: 18px; height: 18px; }
.host-workspace .invoice-form .help-tip-btn::after { inset: -13px; }
```

### Step 2. `App/app/static/guest.css`

2a. Anchor (three exact lines):
```css
.g-wizard-nav {
  display: flex;
  gap: 10px;
```
Change only `gap: 10px;` to `gap: 12px;`.

2b. Anchor (two exact lines, inside `.g-chip {`):
```css
  margin-left: 7px;
  font-size: 11.5px;
```
Change only `font-size: 11.5px;` to `font-size: 13px;`.

2c. Anchor (two exact lines):
```css
.g-review-list { margin-bottom: 0; }
.g-review-list dd { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
```
Replace with:
```css
.g-review-list { margin-bottom: 0; row-gap: 12px; }
.g-review-list dd { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
/* 0907: 12 px or more between the signature pad's Clear button and the review title */
.g-review { margin-top: 18px; }
```

2d. Anchor (exact line):
```css
.g-row { display: grid; gap: 14px; grid-template-columns: 1fr 1fr; }
```
Insert directly after it:
```css
/* 0907: a row's last field has no bottom margin, so the row keeps the 16 px field rhythm itself */
.g-row { margin-bottom: 16px; }
.g-row:last-child { margin-bottom: 0; }
```

### Step 3. Cache keys

- `App/app/templates/base.html`: replace `/static/host2.css?v=20261102-0864` with `/static/host2.css?v=20261102-0907` (one hit).
- `App/app/templates/guest/base.html`: replace `/static/guest.css?v=20261102-1205` with `/static/guest.css?v=20261102-0907` (one hit). Do not touch `templates/guest/archive/`.
- From `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`

### Step 4. `App/tests/v2_mockup.py`: the helper

Anchor: the file's last two lines (exact):
```python
            out.append(f"{selector} {prop} at {width} px: app={app[prop]} mockup={mock[prop]}")
    return out
```
Append after them, at the end of the file (two blank lines first, as shown):
```python


# 0907: Josef's spacing rules inside one part of a page (owner, 2026-11-02):
# no page scroll sideways; text 16 px or more from the edges of its card; no
# text under 13 px (the "?" glyph excepted); controls 12 px or more apart;
# a button never over text and 12 px or more from it.
_SPACING_JS = r"""
(args) => {
  const out = [];
  const scope = document.querySelector(args.scope);
  if (!scope) return [`scope ${args.scope} not found`];
  const name = (el) => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '')
    + (typeof el.className === 'string' && el.className.trim() ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : '');
  const shown = (el) => {
    for (let e = el; e; e = e.parentElement) {
      const cs = getComputedStyle(e);
      if (e.hidden || cs.display === 'none' || cs.visibility === 'hidden') return false;
      const up = e.parentElement;
      if (up && up.tagName === 'DETAILS' && !up.open && e.tagName !== 'SUMMARY') return false;
    }
    const r = el.getBoundingClientRect();
    return r.width > 2 && r.height > 2;
  };
  // a pinned (fixed or sticky) bar rides over the content by design; it is not a neighbour
  const pinned = (el) => {
    for (let e = el; e && e !== document.body; e = e.parentElement) {
      const p = getComputedStyle(e).position;
      if (p === 'fixed' || p === 'sticky') return true;
    }
    return false;
  };
  const vw = window.innerWidth;
  if (document.documentElement.scrollWidth > vw + 1) {
    const wide = [...document.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().right > vw + 1 && getComputedStyle(e).position !== 'fixed');
    out.push(`page scrolls sideways (${document.documentElement.scrollWidth} px at ${vw} px), widest: ${wide.length ? name(wide[wide.length - 1]) : 'unknown'}`);
  }
  const texts = [];
  const walker = document.createTreeWalker(scope, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    const el = node.parentElement;
    if (!node.textContent.trim() || !el || el.closest('script, style, select, option, textarea, ' + args.skip)) continue;
    if (!shown(el)) continue;
    const range = document.createRange();
    range.selectNodeContents(node);
    for (const r of range.getClientRects()) {
      if (r.width > 0 && r.height > 0) texts.push({el, r, pinned: pinned(el), text: node.textContent.trim().slice(0, 30)});
    }
  }
  for (const t of texts) {
    const size = parseFloat(getComputedStyle(t.el).fontSize);
    if (size < 13 && !t.el.closest(args.glyphs)) out.push(`fine print ${size} px: ${name(t.el)} "${t.text}"`);
    const card = t.el.closest(args.cards);
    if (!card) continue;
    const c = card.getBoundingClientRect();
    const edge = Math.min(t.r.left - c.left, c.right - t.r.right, t.r.top - c.top, c.bottom - t.r.bottom);
    if (edge < 15.5) out.push(`text ${edge.toFixed(1)} px from the edge of ${name(card)} (min 16): "${t.text}"`);
  }
  const gapOf = (a, b) => {
    const v = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
    const h = Math.min(a.right, b.right) - Math.max(a.left, b.left);
    if (v > 0 && h > 0) return -Math.min(v, h);
    if (v > 0) return -h;
    if (h > 0) return -v;
    return null;
  };
  const found = [...scope.querySelectorAll(args.controls)].filter(el => shown(el) && !pinned(el));
  const controls = found.filter(x => !found.some(y => y !== x && x.contains(y)));
  for (let i = 0; i < controls.length; i++) {
    for (let j = i + 1; j < controls.length; j++) {
      const gap = gapOf(controls[i].getBoundingClientRect(), controls[j].getBoundingClientRect());
      if (gap !== null && gap < 11.5) out.push(`controls ${gap.toFixed(1)} px apart (min 12): ${name(controls[i])} / ${name(controls[j])}`);
    }
  }
  for (const b of [...scope.querySelectorAll(args.buttons)].filter(el => shown(el) && !pinned(el))) {
    const br = b.getBoundingClientRect();
    for (const t of texts) {
      if (b.contains(t.el) || t.pinned) continue;
      const gap = gapOf(br, t.r);
      if (gap !== null && gap < 11.5) out.push(`text ${gap.toFixed(1)} px from a button (min 12): ${name(b)} / "${t.text}"`);
    }
  }
  // a field keeps 12 px from text that is not its own label or hint
  for (const f of [...scope.querySelectorAll('input:not([type=hidden]):not([type=radio]):not([type=checkbox]), select, textarea')].filter(el => shown(el) && !pinned(el))) {
    const own = f.closest(args.fields);
    const fr = f.getBoundingClientRect();
    for (const t of texts) {
      if (t.pinned || (own && own.contains(t.el))) continue;
      const gap = gapOf(fr, t.r);
      if (gap !== null && gap < 11.5) out.push(`text ${gap.toFixed(1)} px from a field it does not belong to (min 12): ${name(f)} / "${t.text}"`);
    }
  }
  return out;
}
"""


def spacing_findings(page, scope: str, cards: str, controls: str, buttons: str, glyphs: str, skip: str, fields: str) -> list[str]:
    """0907: one string per spacing problem inside `scope`. Empty list means it passes."""
    return page.evaluate(_SPACING_JS, {
        "scope": scope, "cards": cards, "controls": controls,
        "buttons": buttons, "glyphs": glyphs, "skip": skip, "fields": fields,
    })
```
Check: `grep -c "def spacing_findings" tests/v2_mockup.py` prints `1`.

### Step 5. `App/tests/test_invoice_autofill.py`: the buyer block test

Anchor: the file ends with the 0886 test `test_invoice_buyer_kind_screenshots`, whose last two lines are `    server.should_exit = True` and `    thread.join(timeout=5)` (check with `tail -3 tests/test_invoice_autofill.py`). Append after them, at the end of the file:
```python


# 0907: the buyer block keeps Josef's spacing rules at every width, Guest and Company.
INVOICE_SPACING = {
    "scope": ".invoice-customer",
    "cards": ".invoice-customer, .ui-choice-card, .invoice-lookup",
    "controls": "input:not([type=hidden]), select, textarea, button, a.ui-btn",
    "buttons": "button, a.ui-btn",
    "glyphs": ".help-tip-btn",
    "skip": ".help-tip-body, .sr-only",
    "fields": ".ui-field",
}
# the "?" on the Company card: an 18 px ring on the label's line, 12 to 16 px after its last word, 44 px tap area
INVOICE_HELP_JS = """
() => [...document.querySelectorAll('.invoice-customer .help-tip-btn')].filter(b => b.getClientRects().length).map(btn => {
  const label = btn.closest('.help-tip').previousElementSibling;
  const range = document.createRange();
  range.selectNodeContents(label);
  const lines = [...range.getClientRects()].filter(r => r.width > 0 && r.height > 0);
  const line = lines[lines.length - 1];
  const b = btn.getBoundingClientRect();
  const hit = -parseFloat(getComputedStyle(btn, '::after').left);
  return {label: label.textContent.trim(), ring: b.width, tap: b.width + 2 * hit,
          gap: b.left - line.right, centre: Math.abs((b.top + b.bottom) / 2 - (line.top + line.bottom) / 2)};
})
"""


def test_invoice_buyer_block_spacing_0907():
    """0907: Guest and Company at 320 to 1440 px; Chromium is required."""
    import os
    import secrets
    import socket
    import threading
    import time
    from pathlib import Path

    import uvicorn

    sync_api = pytest.importorskip("playwright.sync_api")
    from tests.test_invoice_stay_browser import _browser_session_cookie, _launch
    from tests.v2_mockup import WIDTHS, spacing_findings

    shots = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0907"
    db.init_db()
    username = f"inv0907{secrets.token_hex(4)}"
    owner = auth.create_account(f"{username}@example.test", "Spacing 0907", username=username)
    entity = db.insert(
        "legal_entity",
        {
            "name": "Vivus Apartment with Balcony & Garage s.r.o.", "seat": "Praha 1", "ico": "04656679",
            "registry_entry": "Fyzická osoba zapsaná v živnostenském rejstříku",
            "vat_status": "non_payer", "invoice_due_days": 14,
            "owner_user_id": owner, "created_at": db.utcnow(),
        },
    )
    stay_id = make_stay(owner, entity_id=entity)
    _complete_guest(stay_id)

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    assert server.started, "the 0907 test server did not start"
    base = f"http://127.0.0.1:{port}"
    session = _browser_session_cookie(username)
    path = f"/invoices/new?reservation_id={stay_id}&entity={entity}&lang=en"
    problems = []
    try:
        with sync_api.sync_playwright() as playwright:
            browser = _launch(playwright)
            for width in WIDTHS:
                context = browser.new_context(viewport={"width": width, "height": 900})
                context.add_cookies([{"name": auth.SESSION_COOKIE, "value": session, "url": base + "/"}])
                page = context.new_page()
                page.goto(base + path)
                page.wait_for_load_state("networkidle")
                for kind in ("guest", "company"):
                    if kind == "company":
                        page.click('label.ui-choice-card-label:has(input[value="company"])')
                    assert page.is_checked(f'input[name="buyer_kind"][value="{kind}"]')
                    tag = f"{kind} at {width}px"
                    problems += [f"{tag}: {p}" for p in spacing_findings(page, **INVOICE_SPACING)]
                    for box in page.evaluate(INVOICE_HELP_JS):
                        if not (16 <= box["ring"] <= 20 and box["tap"] >= 44 and 12 <= box["gap"] <= 16 and box["centre"] <= 4):
                            problems.append(f"{tag}: the ? beside {box['label']!r} breaks the rule {box}")
                    if os.environ.get("UBYHOST_0907_SHOTS") == "1" and width in (390, 1280):
                        shots.mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(shots / f"invoice-{kind}-{width}.png"), full_page=True)
                context.close()
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=5)
    assert not problems, "\n".join(problems[:60])
```
Check: `grep -c "def test_invoice_buyer_block_spacing_0907" tests/test_invoice_autofill.py` prints `1`.

### Step 6. `App/tests/test_guest_browser_e2e.py`: the guest checks

6a. Anchor (exact line): `from tests.browser_support import chromium_launch_kwargs`. Insert directly after it:
```python
from tests.v2_mockup import WIDTHS as GEOMETRY_WIDTHS, spacing_findings  # noqa: E402
```
6b. Anchor: `grep -n '^class Guest:' tests/test_guest_browser_e2e.py` (one hit). Insert directly **before** that line (it ends with two blank lines before `class Guest:`):
```python
# 0907: Josef's spacing rules on the open step card (helper in tests/v2_mockup.py).
GUEST_SPACING = {
    "scope": "[data-guest-step]:not([hidden])",
    "cards": ".g-card",
    "controls": "input:not([type=hidden]), select, textarea, button, a.g-btn, summary:not(details.g-head-help > summary), .g-help-dot",
    "buttons": "button, a.g-btn, summary:not(details.g-head-help > summary), .g-help-dot",
    "glyphs": ".g-help-dot",
    "skip": ".sr-only, .g-sr-only",
    "fields": ".g-field",
}
SHOTS_0907 = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0907"


def _shot_0907(page, name: str) -> None:
    """0907 evidence: person 2, step 1, only when asked to."""
    if os.environ.get("UBYHOST_0907_SHOTS") != "1":
        return
    SHOTS_0907.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS_0907 / name), full_page=True)


```
6c. Anchor (exact line, the last line of `check_help_beside_title`): `        assert not help_.evaluate("el => el.open")`. Insert directly after it:
```python

    def check_spacing(self, where: str, widths=()):
        """0907: Josef's spacing rules on the open step, at each width."""
        page = self.page
        for width in widths or (self.width,):
            if widths:
                page.set_viewport_size({"width": width, "height": 812})
            for problem in spacing_findings(page, **GUEST_SPACING):
                self.problems.append(f"{where} at {width}px: {problem}")
        if widths:
            page.set_viewport_size({"width": self.width, "height": 812})
```
6d. Anchor (exact line): `        self.check_help_beside_title("identity", widths=(320, 390, 768))`. Replace it with:
```python
        self.check_help_beside_title("identity", widths=GEOMETRY_WIDTHS)
        all_widths = GEOMETRY_WIDTHS if (self.lang, self.width) == ("en", 390) else ()
        if number == 2:
            self.check_spacing("person 2, details", all_widths)
            if self.lang == "en" and self.width in (390, 1280):
                _shot_0907(page, f"person2-step1-{self.width}.png")
```
6e. Anchor (exact line): `        self.check_help_beside_title("address-stay")`. Replace it with:
```python
        self.check_help_beside_title("address-stay", widths=all_widths if number == 2 else ())
        if number == 2:
            self.check_spacing("person 2, home", all_widths)
```
6f. Anchor (exact line): `        self.check_help_beside_title("signature")`. Replace it with:
```python
        self.check_help_beside_title("signature", widths=all_widths if number == 2 else ())
        if number == 2:
            self.check_spacing("person 2, signature", all_widths)
```
(The signature checks run before `self.sign()`, as the anchor already is: resizing after drawing could clear the pad.)

What this covers: every run checks person 2 at its own width (en 320, 375, 390, 1280; de, es, fr 320, 360, 390; the readable-link test 320, 360, 390). The en-390 run checks person 2's three steps at all six widths, and the identity "?" at all six widths for every person. The passport-photo step is not in this flow (the test property has `passport_photo_policy` off); it is not covered here.

### Step 7. Run section 6, take the screenshots, look at each once

Run commands 1 to 8. Command 2 writes the invoice PNGs and command 3 the guest PNGs. Then `ls ../docs/tasks/screenshots-0907/ | tail -10` must list exactly: `invoice-guest-390.png`, `invoice-company-390.png`, `invoice-guest-1280.png`, `invoice-company-1280.png`, `person2-step1-390.png`, `person2-step1-1280.png`. Open each once. Check: the "?" is a small ring right after "Company" and right after the "Person 2" chip; nothing touches a card edge; no button sits on text. Note: a full-page screenshot draws the phone tab bar and the round help button in the middle of the invoice page; that is the screenshot tool, not the layout.

## 5. Do not touch

`App/app/static/app2.css`, `app.css`, `host.css`, every other `.css` file; `App/app/templates/guest/archive/`; routes, i18n files, `_components.html`; the 0885 `HELP_BESIDE_TITLE_JS` and `check_help_beside_title` body (only its call sites change in 6d to 6f); `LAYOUT_JS`; `geometry_findings` and `_GEOMETRY_JS`; any existing test's numbers; UbyPort code.

## 6. Commands

From `App/`. Put `B="UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium UBYHOST_REQUIRE_BROWSER=1"` in front of each command as `env $B ...` or write the two variables out. Allow up to 10 minutes for commands 3, 5 and 6.
1. Static and design row: `.venv/bin/python -m pytest tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py tests/test_design_*.py -q --tb=short -x -rs 2>&1 | tail -30` (with the browser variables)
2. Invoices row and the new test: `mkdir -p /tmp/shots-0907-extra && UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium UBYHOST_REQUIRE_BROWSER=1 UBYHOST_0907_SHOTS=1 UBYHOST_SHOTS_DIR=/tmp/shots-0907-extra .venv/bin/python -m pytest tests/test_invoice_*.py tests/test_stay_fee*.py -q --tb=short -x -rs 2>&1 | tail -30` (`UBYHOST_SHOTS_DIR` only stops the two 0836/0886 screenshot tests from skipping; their PNGs go to /tmp and are not part of this task)
3. Guest flow with screenshots: `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium UBYHOST_REQUIRE_BROWSER=1 UBYHOST_0907_SHOTS=1 .venv/bin/python -m pytest tests/test_guest_browser_e2e.py -q --tb=short -x -rs 2>&1 | tail -30`
4. (no command; the screenshot check of step 7)
5. Guest row: `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_*.py tests/test_host_geometry.py -q --tb=short -x -rs 2>&1 | tail -30`
6. Host row: `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py -q --tb=short -x -rs 2>&1 | tail -30`
7. Lint: `.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841 2>&1 | tail -30`, then from the repo root `python3 scripts/design_lint.py 2>&1 | tail -30`
8. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`

Expected: all pass, `0 skipped` in every pytest command, `All checks passed!`, `design lint: OK`, `context lint: OK`. In the orchestrator's run on bb01bb5 plus these changes, commands 1 and 2 passed (156 and 243 passed, 0 skipped), command 3 passed (17 passed), and ruff and design lint were clean. The 0886 report named failures in the host row that it did not prove pre-existing (`test_host_ux_acceptance.py::test_page_families_through_rail_cards_search_and_back`, `test_host_feedback_browser.py::test_host_copy_feedback_truth_and_geometry`, `test_host_i18n.py::test_language_endpoint_sets_cookie_and_rejects_open_redirects`). If command 6 fails only on those, rerun it without `-x`, report the counts and the failing names, and do not fix them.

## 7. Acceptance

- [ ] Invoice buyer block, Guest and Company, at 320, 390, 768, 1024, 1280 and 1440 px: no finding from `spacing_findings`; the Company "?" ring is 16 to 20 px, its tap area 44 px or more, 12 to 16 px after "Company", centred on its line within 4 px (command 2).
- [ ] Guest form, person 2, details, address and signature steps: no finding at every run width, and at all six widths in the en-390 run; the "?" check of 0885 passes at all six widths (command 3).
- [ ] No number in a check was changed and no selector was added to `skip`, `glyphs` or the pinned rule.
- [ ] `host2.css` and `guest.css` keys bumped to `20261102-0907`; `static_versions.json` regenerated.
- [ ] Commands 1 to 8 pass, 0 skipped (command 6: only the named failures, if any).
- [ ] The six PNGs in `docs/tasks/screenshots-0907/`, each opened once.
- [ ] Nothing committed or pushed.

## 8. Stop and ask

Stop and write the report (`Status: blocked`) if:
- the first command in section 2 prints anything, or an anchor is not found exactly once;
- a test fails twice after one fix;
- you reach 25 tool calls or about 50k tokens (see executor.md);
- a file outside section 3 needs a change, or section 5 would be touched;
- you would need to change a number, a selector list or a width in a test;
- you need to commit, push, merge, set secrets, use SSH or deploy.

**One fix round is allowed for a new finding** (for example a translated word that is longer than the English one). Rules for it: change only `host2.css` (invoice findings, selectors that start with `.host-workspace .invoice-customer` or `.host-workspace .invoice-lookup`, spacing only with `var(--space-*)` and sizes with `var(--size-*)`) or `guest.css` (guest findings, selectors scoped to `.g-step-head`, `.g-row`, `.g-field`, `.g-review`, `.g-wizard-nav` or `.g-sign`); make the smallest change that gives the missing pixels (raise a gap or padding to 12 or 16 px, or a font to 13 px or more); bump the same cache key again to `20261102-0907b` and run `--write` again. Change a template only if no CSS can fix it, never add a class to `invoice_form.html`, and name the change in the report. If the finding is in a part of the page outside the buyer block or the step card (for example "page scrolls sideways" with a culprit elsewhere), do not fix it: STOP and report the line.

## 9. Report

Write `docs/tasks/0907-report.md` (600 tokens at most) and set `Status: review`. Include: `git diff --stat bb01bb5`; each command with its last 5 lines; section 7 ticked; any fix round (the finding line and the CSS line you changed); deviations and questions; the six screenshot paths; owner steps left. Do not commit.

## Risk list (for the reviewer)

- `host2.css`: the "?" ring is now 18 px on the whole invoice form (items and due date too), smaller than the 24 px of other host pages; MASTER 7.12 says 16 px icon. If Josef wants 18 px everywhere, that is a separate host-wide brief.
- `guest.css`: `.g-wizard-nav`, `.g-chip`, `.g-row` and `.g-review-list` are shared by all guest steps and the claim page; the guest row (command 5) covers them.
- The spacing helper skips pinned (fixed or sticky) bars, text in closed `<details>`, and text inside the button being measured. A sticky submit bar over the review list is by design (the existing acknowledgement test checks what it must not cover).

## Owner steps

1. Open the six screenshots in `docs/tasks/screenshots-0907/`.
2. On your iPhone after the staging deploy: open an invoice from a stay, tap Company: the "?" sits right after the word, the IČO field and the ARES button do not touch. Open a guest link, add person 2: the "Person 2" chip is readable and Back and Continue do not touch.
3. Merge with `scripts/merge-pr-on-green.sh <pr>` when CI is green.
