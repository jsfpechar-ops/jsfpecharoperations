# 0252: Open cue on every clickable row, no hidden tabs on phone, touch sweep test

Status: todo
Depends on: 0251 | Base commit: tip of claude/project-thread-cjz5cc after 0251 | Branch: claude/project-thread-cjz5cc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The owner asked for an app-wide sweep after iPad users missed that rows and cards open something. Every clickable table row gets a bordered "Open ›" cue, as do the Settings hub cards. On phones, tab and chip rows wrap instead of hiding items off-screen. The housebook row menu stays visible. Three stale navigation tests are fixed, and a permanent touch sweep test guards all of it on phone, iPad and desktop sizes.

## 2. Context

- `_components.html` line ~490 has `row_menu_begin`/`row_menu_end`. `app.css:1190`: `.row-menu { position: relative; display: inline-flex; }`.
- Clickable rows are `<tr class="... clickable-row" data-href=...>`. The whole row already opens on click/tap (app.js). The cue is decoration, so it is a `<span aria-hidden="true">`, never a second link.
- Phone (below 1024 px) renders these rows as cards (MASTER 7.3: a grid with the 44 px menu at the top right). The cue sits absolutely at the bottom right as a 32 px bordered circle with a chevron. Between 1024 and 1279 px it is the same circle inline. From 1280 px it shows the word.
- dashboard.html is excluded: another branch removes its stay table.
- The overview property cards already have `.host-property-card-open` (0250). The Settings hub cards are `a.host-property-card` in `settings.html` line 13 and reuse it.
- Stale tests in `tests/test_property_navigation_browser.py` (fail on base c1ebb74): `SETTINGS_NAMES` lacks `signature_drawn` and `signature_name` (fields added by 0209). Line ~527 clicks `.setup-wizard-skip .link-button`, but the wizard's skip is now `button[value='skip']`. The fit test fails because the property settings chips scroll off-screen at 360 px, which step 3 fixes.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/_components.html | edit | new macro `row_open()` |
| App/app/templates/{reservations,reservation_detail,apartments,submission_detail,entities,submissions,settings_archived,housebook,invoices,stay_fees}.html | edit | import + insert the cue |
| App/app/templates/settings.html | edit | Open pill on hub cards |
| App/app/static/host.css | edit | cue styles, settings chips wrap, housebook sticky actions |
| App/app/static/host2.css | edit | `.ui-tabs`/`.ui-chips` wrap on phone |
| App/app/templates/base.html (+ any template with these keys) | edit | `?v=` keys |
| App/tests/static_versions.json | regenerate | |
| App/tests/test_property_navigation_browser.py | edit | the two stale lines |
| App/tests/test_0252_touch_sweep_browser.py | create | sweep test (code below) |

No other file may change.

## 4. Steps

### Step 1: macro

In `_components.html`, right after the `row_menu_end` macro's `{% endmacro %}`, add:

```
{#- 0252: a visible "Open" cue for a row that opens on click; the row itself is the link. -#}
{% macro row_open() -%}
<span class="row-open" aria-hidden="true"><span class="row-open-text">{{ t('common.open') }}</span>{{ icon('chevron-right', 16) }}</span>
{%- endmacro %}
```

If `icon` is not available inside `_components.html` (`grep -n "import icon" App/app/templates/_components.html`), STOP.

### Step 2: insert the cue

In each template, add `row_open` to its existing `from "_components.html" import ...` list (invoices.html imports only `empty_state`, so add it there too). Then put `{{ row_open() }}` as the **first** content of the actions cell of every clickable row:

| File | Clickable `<tr>` line ≈ | Actions `<td>` line ≈ |
|---|---|---|
| reservations.html | 148 | 173 |
| reservation_detail.html | 399 | 403 |
| apartments.html | 29 | 43 |
| submission_detail.html | 111 | 134 |
| entities.html | 79 and 125 | 92 and 132 |
| submissions.html | 25 | 33 |
| settings_archived.html | 54, 94, 167 | 62, 100, 173 |
| housebook.html | 70 | 93 |
| invoices.html | 29 | 36 |
| stay_fees.html | 120 and 138 | 127 and 168 |

Example: `<td class="nowrap row-actions" data-label="">` followed by `{{ row_menu_begin() }}` becomes `<td class="nowrap row-actions" data-label="">{{ row_open() }}` followed by `{{ row_menu_begin() }}`. Find each `<td>` with `grep -n "row-actions\|ui-cell-acts" <file>` and check that the `<tr>` above it has `clickable-row`. A row that is not `clickable-row` gets nothing.

`settings.html` line 13: change `<a class="host-property-card" href="{{ href }}"><strong>{{ t(key) }}</strong></a>` to

```
<a class="host-property-card" href="{{ href }}"><strong>{{ t(key) }}</strong><span class="host-property-card-open" aria-hidden="true"><span class="host-property-card-open-text">{{ t('common.open') }}</span>{{ icon('chevron-right', 16) }}</span></a>
```

(check `icon` is imported in settings.html; if not, add `{%- from "_icons.html" import icon with context -%}` at the top the way `_property_overview.html` line 2 does).

Commit `0252 step 2` (step 1 goes in the same commit).

### Step 3: CSS

3a. `host.css`, at the end of the file:

```
/* 0252: the Open cue on clickable rows (the row is the link). */
.row-open { display: inline-flex; align-items: center; justify-content: center; gap: 4px; min-height: 32px; padding: 0 10px 0 12px; border: 1px solid var(--border-strong); border-radius: 999px; font-size: 13px; font-weight: 600; color: var(--ink); background: white; vertical-align: middle; white-space: nowrap; }
.row-open + .row-menu { vertical-align: middle; margin-left: 6px; }
td:has(> .row-open) { white-space: nowrap; }
@media (hover: hover) { .clickable-row:hover .row-open { border-color: var(--ink); } }
@media (max-width: 1279px) {
  .row-open { width: 32px; padding: 0; }
  .row-open-text { display: none; }
}
@media (max-width: 1023px) {
  .table-cards tr.clickable-row { position: relative; }
  .table-cards tr.clickable-row .row-open { position: absolute; right: 12px; bottom: 12px; }
  .table-cards tr.clickable-row:has(.row-action-form) .row-open { display: none; }
}
/* 0252: the housebook is wider than the lane; its row actions stay in view. */
.scroll-x td.row-actions { position: sticky; right: 0; background: white; }
```

3b. `host.css`, inside `@container property-lane (max-width: 859px)` (anchor `grep -nF "flex-wrap: nowrap; overflow-x: auto; min-width: 0; max-width: 100%;" App/app/static/host.css`), replace that line with:

```
  .property-settings > .property-settings-nav { flex-wrap: wrap; min-width: 0; max-width: 100%; }
```

3c. `host2.css`: replace line 383 `  .host-workspace .ui-toolbar .ui-chips { flex-wrap: nowrap; overflow-x: auto; scrollbar-width: none; padding-bottom: 1px; }` with `  .host-workspace .ui-toolbar .ui-chips { flex-wrap: wrap; padding-bottom: 1px; }`. Inside the first `@media (max-width: 1023px) {` block that follows line 133, or if none fits, a new block right after line 133, add:

```
@media (max-width: 1023px) { .host-workspace .ui-tabs { flex-wrap: wrap; overflow-x: visible; row-gap: var(--space-1); } }
```

(place it as its own one-line block directly after line 133).

3d. Bump the `?v=` keys of `host.css` and `host2.css` everywhere (`grep -rn "host.css?v=\|host2.css?v=" App/app/templates`) to `20261022-0252`, then from `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`.

Commit `0252 step 3`.

### Step 4: stale tests

In `tests/test_property_navigation_browser.py`: add `"signature_drawn", "signature_name",` to the `SETTINGS_NAMES` set (first line of the set). Replace `page.locator(".setup-wizard-skip .link-button").click()` with `page.locator(".setup-wizard-skip button[value='skip']").click()`. Commit `0252 step 4`.

### Step 5: sweep test

Create `App/tests/test_0252_touch_sweep_browser.py` with exactly:

```python
"""0252: every host page, on phone, three iPad sizes (touch) and desktop.

Checks the owner's sweep rules: nothing important sits off-screen, every
clickable row or card shows an Open cue, and a tap in its middle lands on
something clickable. Set UBYHOST_SHOTS_DIR to keep a screenshot per page.
"""
from __future__ import annotations

import os
import secrets

from fastapi.testclient import TestClient

from app import auth, db, demo
from app.main import app
from tests.conftest import login_as
from tests.test_property_navigation_browser import base, chromium_launch_kwargs, sync_api  # noqa: F401

IPAD = "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
PHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
SIZES = [
    ("phone390", 390, 844, PHONE, True),
    ("ipad820", 820, 1180, IPAD, True),
    ("ipad1024", 1024, 1366, IPAD, True),
    ("ipad1180", 1180, 820, IPAD, True),
    ("desk1280", 1280, 900, None, False),
    ("desk2000", 2000, 1100, None, False),
]
PROBE = r"""() => {
  const vw = document.documentElement.clientWidth;
  const out = {overflow: document.documentElement.scrollWidth > vw + 1, outside: [], noCue: [], deadMiddle: []};
  const shown = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden'; };
  const main = document.querySelector('main') || document.body;
  const name = e => (e.querySelector('strong, .row-primary-link, td') || e).textContent.trim().replace(/\s+/g, ' ').slice(0, 40);
  for (const e of main.querySelectorAll('a, button, input, select, textarea, h1, h2, h3')) {
    if (!shown(e) || e.closest('.cal-scroll, [data-dashboard-calendar], .notification-stack')) continue;
    const r = e.getBoundingClientRect();
    if (r.right > vw + 1 || r.left < -1) {
      const box = e.closest('.scroll-x');
      if (box) { const b = box.getBoundingClientRect(); if (r.left >= b.left - 1 && r.right <= b.right + 1) continue; if (e.closest('td.row-actions') === null) continue; }
      out.outside.push((e.textContent || e.name || e.tagName).trim().slice(0, 30));
    }
  }
  for (const e of main.querySelectorAll('tr.clickable-row, a.host-property-card')) {
    if (!shown(e)) continue;
    if (!e.querySelector('.row-open, .host-property-card-open')) out.noCue.push(name(e));
    const r = e.getBoundingClientRect();
    const x = r.left + Math.min(r.width / 2, 120), y = r.top + Math.min(r.height / 2, 24);
    if (y > 0 && y < innerHeight && x < vw) {
      const hit = document.elementFromPoint(x, y);
      if (hit && !hit.closest('a, [data-href], button, label, input, summary')) out.deadMiddle.push(name(e));
    }
  }
  return out;
}"""


def test_every_host_page_on_phone_ipad_and_desktop(base):
    db.init_db()
    user = f"sweep-{secrets.token_hex(3)}"
    owner = auth.create_account(f"{user}@example.test", "Sweep Host", role="host", username=user)
    demo.seed(owner)
    client = TestClient(app)
    login_as(client, user, url="/login?lang=en")
    flats = db.query("SELECT id FROM apartment WHERE owner_user_id = ? ORDER BY id", (owner,))
    stay = db.query_one(
        "SELECT r.id FROM reservation r JOIN apartment a ON a.id = r.apartment_id WHERE a.owner_user_id = ? ORDER BY r.id",
        (owner,),
    )
    flat = flats[0]["id"]
    pages = [
        "/", "/reservations", f"/reservations/{stay['id']}", "/apartments",
        f"/apartments/{flat}?view=overview", f"/apartments/{flat}?view=bookings",
        f"/apartments/{flat}?view=settings&section=reporting", "/entities", "/submissions",
        "/housebook", "/invoices", "/invoices/new", "/stay-fees", "/cleaning", "/settings",
        "/settings/archived", "/guide", "/privacy-requests",
    ]
    shots = os.environ.get("UBYHOST_SHOTS_DIR")
    problems = []
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        for tag, width, height, agent, touch in SIZES:
            options = {"viewport": {"width": width, "height": height}, "has_touch": touch, "is_mobile": touch}
            if agent:
                options["user_agent"] = agent
            context = browser.new_context(**options)
            context.add_cookies([{"name": auth.SESSION_COOKIE, "value": client.cookies.get(auth.SESSION_COOKIE), "url": base + "/"}])
            page = context.new_page()
            for path in pages:
                response = page.goto(base + path + ("&" if "?" in path else "?") + "lang=en")
                assert response and response.status == 200, (tag, path, response and response.status)
                page.wait_for_timeout(200)
                found = {key: value for key, value in page.evaluate(PROBE).items() if value}
                if found:
                    problems.append((tag, path, found))
                if shots:
                    os.makedirs(shots, exist_ok=True)
                    slug = path.strip("/").replace("/", "-").replace("?", "-").replace("&", "-").replace("=", "-") or "dashboard"
                    page.screenshot(path=os.path.join(shots, f"{slug}-{tag}.png"), full_page=True)
            context.close()
        browser.close()
    assert not problems, problems
```

Run it (§6). If it fails, read the `problems` list. A problem caused by this brief's own CSS may be fixed once, inside the files of §3. Any other problem: STOP and list it in the report; do not chase it.

Commit `0252 step 5`.

## 5. Do not touch

dashboard.html, `_host_alerts.html`, `alerts.py`, the "Setup checklist" section of `_property_overview.html`, app.js. AGENTS.md hard rules 2, 3, 6, 7, 8.

## 6. Commands

From `App/`, with `export UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome UBYHOST_REQUIRE_BROWSER=1`. Before each commit, `git checkout -- ../docs/tasks && git clean -fdq ../docs/tasks/*-evidence` (browser tests rewrite evidence PNGs; never commit them):

```
.venv/bin/python -m pytest tests/test_static_versions.py tests/test_0250_property_cards.py -q --tb=short -x 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_0252_touch_sweep_browser.py -q --tb=short -x -rs 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_property_navigation_browser.py tests/test_0251_tablet_browser.py -q --tb=short -rs 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_host_wide_geometry_browser.py tests/test_0199_phone_geometry_browser.py tests/test_host_list_layouts_browser.py tests/test_host_list_page_layout_browser.py tests/test_onboarding_wizard_browser.py -q --tb=short -rs 2>&1 | tail -30
```

Expected: all pass, 0 skipped. A failure in the last command that also fails on the base commit is pre-existing: list it in the report and do not fix it.

## 7. Acceptance

- [ ] Every clickable row in the 10 list templates and every Settings hub card shows the Open cue.
- [ ] Phone: property settings chips, stay page jump tabs and stays filter chips wrap (nothing off-screen).
- [ ] The 3 stale navigation tests pass.
- [ ] The sweep test passes at all 6 sizes, 0 skipped.
- [ ] Keys bumped, manifest regenerated.

## 8. Stop and ask

As in TEMPLATE.md §8.

## 9. Report

`docs/tasks/0252-report.md`, as in TEMPLATE.md §9. Do not push; do not open a PR.

## Addendum (orchestrator, after the first run): step 6

6a. `App/tests/test_0252_touch_sweep_browser.py`: in `PROBE`, change the selector `'tr.clickable-row, a.host-property-card'` to `'tr.clickable-row:not(.dashboard-row), a.host-property-card'`. The dashboard stay table is being removed on another branch.

6b. `App/app/templates/apartments.html`, the summary row (`grep -nF 'data-summary-row="{{ apartment.id }}"'`): in its first `<td>`, right after `<a class="row-primary-link" href="{{ base_url }}">{{ property_identity(apartment.id, apartment.internal_name) }}</a>`, add ` {{ row_open() }}`. In `host.css`, at the end, add:

```
.row-primary-link + .row-open { margin-left: 8px; }
```

Do not bump the host.css key again: 20261022-0252 has not been released. Just rerun `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`.

6c. Run the sweep test again. Then run §6 commands 3 and 4. Commit `0252 step 6` and update the report.

## Addendum 2 (orchestrator review): step 7

Review found that the row cue's width pushes four wide tables into sideways scrolling (`test_design_guardrails_browser.py`: properties summary, businesses, stay fees). The sticky housebook cell also breaks `cell-not-under-header`. On rows the cue becomes a slim bordered chevron button at every width; the cards keep the word "Open".

7a. `App/app/static/host.css`, in the 0252 block at the end of the file:
- replace the `.row-open { ... }` line with
  `.row-open { display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; box-sizing: border-box; border: 1px solid var(--border-strong); border-radius: 999px; color: var(--ink); background: white; vertical-align: middle; flex: 0 0 auto; }`
  `.row-open-text { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }`
- `.row-open + .row-menu { vertical-align: middle; margin-left: 6px; }`: change `6px` to `4px`.
- delete the line `td:has(> .row-open) { white-space: nowrap; }`
- delete the whole `@media (max-width: 1279px) { ... }` block (3 lines plus the closing brace)
- delete the comment `/* 0252: the housebook is wider than the lane; its row actions stay in view. */` and the `.scroll-x td.row-actions { ... }` line
- `.row-primary-link + .row-open { margin-left: 8px; }`: change `8px` to `6px`.

Bump the host.css key to `20261022-0252c` in every template and run `--write`.

7b. `App/tests/test_0252_touch_sweep_browser.py`, in `PROBE`: replace the whole `const box = e.closest('.scroll-x'); if (box) { ... }` line with `if (e.closest('.scroll-x')) continue;`. Wide registers scroll inside their own labelled region by design.

7c. `App/tests/test_0199_phone_geometry_browser.py` line ~118: the owner asked that phone chip rows wrap instead of hiding chips off-screen (0252), which replaces 0199 E's single scrolling row. Change `m["E"]["rows"] == 1` to `m["E"]["rows"] <= 3 and m["E"]["scrollW"] <= m["E"]["clientW"] + 1`, and the message text `E chips not on one row` to `E chips hidden off-screen`.

7d. Rerun §6 commands 2, 3 and 4. Expected: everything passes except the pre-existing `test_0199_phone_geometry_browser.py::test_stay` ("A panel content offset 118"). Commit `0252 step 7` and update the report.
