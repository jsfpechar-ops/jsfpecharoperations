# 0910: Calendar toolbar stays still; guest details on the stay and stay-fee pages

Status: todo
Executor: Haiku 5.5. Read only AGENTS.md, docs/context/executor.md, this brief and the files named here.
Branch: `fix/0910-calendar-toolbar-stable`. One PR. Do not touch any other file.

Scope: Steps 1-3 (calendar toolbar), Part A (guest birth date, nationality, document number on the stay page),
Part B (birth date, age at check-in, nationality on the stay-fee detail page), Part C (Back-button test, no
history change). Files you may change: `App/app/templates/_dashboard_calendar.html`,
`App/app/static/dashboard-calendar.css`, `App/app/templates/reservation_detail.html`,
`App/app/templates/stay_fee_detail.html`, `App/app/routes/stay_fees.py`, `App/app/host_i18n.py`,
`App/app/host_vi_i18n.py`, `App/app/static/app2.css` (only if Part A step 3 needs it), the new test files named
below, `App/tests/test_stay_fee_detail.py`, `docs/tasks/0910-report.md`, `docs/tasks/screenshots-0910/`.

## Problem (reproduced 2026-11-04 in Chromium, `/?cal_view=calendar`)

The host calendar head (`[data-cal-head]`) at >= 768 px is one `display:flex; flex-wrap:wrap; justify-content:flex-end` row
(`App/app/static/dashboard-calendar.css`, block `@media (min-width:768px)` near line 775). `.cal-heading` and `.cal-toolbar`
are `display:contents`, so the period title `h3[data-cal-period]` (`flex:0 0 auto; white-space:nowrap`), the arrows,
the property select, the view segment, settings and the scale segment are all items of one wrapping row.
Where the row wraps depends on the **width of the period text**, which changes on every arrow click.

Measured (left px of `[data-cal-prev]` / `[data-cal-property]` / `[data-cal-scales]`):

| Width | Action | Before | After |
|---|---|---|---|
| 768 en | Week scale, Next (25 Jan -> 1 Feb -> 8 Feb) | 572 / 42 / 329 | 285 / 473 / 329, then back to 572 / 42 |
| 768 en | Month -> Week | 285 / 473 / 549 | 572 / 42 / 329 |
| 1024 en, cs | Month -> Week | 517 / 699 / 793 | 818 / 272 / 573 (property drops to row 2) |
| 1280 en | Month -> Week -> Year -> Month | 570 / 758 / 1045 (one row) | 781 / 969 / 825 (scales to row 2), 480 / 668 / 955, 570 / 758 / 1045 |

Month scale prev/next did not move controls in en or cs with the test data, but it only stays still because the month
names happen to fit; any wider label (week range, longer locale) re-wraps the row. Root cause: content-sized period
in a wrapping flex row. Also: `[data-cal-today]` sits between `[data-cal-prev]` and `[data-cal-next]` in
`App/app/templates/_dashboard_calendar.html` (`.cal-navigation`), which the owner finds confusing.

Fix: at >= 768 px the head becomes a fixed two-row grid. Row 1: period (flexible, truncates) | Today + arrows.
Row 2: property, view, settings on the left | scale or month/year on the right. Nothing in rows 1 and 2 depends
on the period text width. Today moves before the arrows with a wider gap (Airbnb/Google pattern: `Today   < >`).

Out of scope (do not fix, already noted in the report): after scrolling the month list, an arrow click scrolls to the
top (0891 design), so the sticky head returns from y=12 to its in-flow place; the week label mixes formats
("2 Nov – 8 November 2026").

## Step 1: template (`App/app/templates/_dashboard_calendar.html`)

1. In `.cal-navigation`, move the Today button **before** the Prev button and add class `cal-today`. The block becomes:
   ```html
   <div class="cal-navigation">
     <button type="button" class="btn soft cal-today" data-cal-today>{{ t('calendar.today') }}</button>
     <button type="button" class="btn soft cal-arrow" data-cal-prev ...unchanged...></button>
     <button type="button" class="btn soft cal-arrow" data-cal-next ...unchanged...></button>
   </div>
   ```
   Keep the existing i18n key `calendar.today` and both arrow `aria-label`s. No new i18n key. No JS change
   (`dashboard-calendar.js` finds the buttons by `data-` attribute).
2. Line 2: bump the stylesheet version `?v=20261104-0908d` to `?v=20261104-0910`.

## Step 2: CSS (`App/app/static/dashboard-calendar.css`)

Find the block with `grep -n "@media (min-width:768px)" App/app/static/dashboard-calendar.css` (the one whose first
rule is `body.v2 #calendar.dashboard-calendar[data-readonly="false"] .cal-head { display:flex; flex-wrap:wrap; ...`).
Read only that range. Replace exactly these rules in that block (keep every other declaration in the block):

```css
  body.v2 #calendar.dashboard-calendar[data-readonly="false"] .cal-head { display:grid; grid-template-columns:minmax(0,1fr) auto; align-items:center; column-gap:12px; row-gap:12px; margin:0 0 16px; padding:12px 0 0; background:var(--bg, #f6f6f4); }
  body.v2 #calendar.dashboard-calendar[data-readonly="false"] .cal-head .cal-toolbar h3[data-cal-period] { grid-row:1; grid-column:1; min-width:0; margin:0; text-align:left; font-size:24px; line-height:32px; font-weight:700; letter-spacing:-0.02em; color:#222; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  body.v2 #calendar.dashboard-calendar[data-readonly="false"] .cal-head .cal-toolbar .cal-navigation { grid-row:1; grid-column:2; justify-self:end; display:flex; align-items:center; gap:12px; }
  body.v2 #calendar.dashboard-calendar[data-readonly="false"] .cal-head .cal-toolbar .cal-today { margin-right:12px; }
  body.v2 #calendar.dashboard-calendar[data-readonly="false"] .cal-head .cal-heading-actions:not([hidden]) { grid-row:2; grid-column:1 / -1; justify-self:start; display:flex; flex-wrap:nowrap; align-items:center; gap:12px; margin:0; }
  body.v2 #calendar.dashboard-calendar[data-readonly="false"] .cal-head .cal-toolbar-options { grid-row:2; grid-column:1 / -1; justify-self:end; display:flex; flex-wrap:nowrap; align-items:center; gap:12px; }
```

and in the `.cal-head > .cal-weekdays` rule of the same block replace `order:9; flex:1 1 100%;` with
`grid-row:3; grid-column:1 / -1;` (keep the rest of that rule). Remove the `order:` and `flex:` declarations from the
four replaced rules; they are not used by grid. Row-2 items span every column on purpose: an item that spans the
`1fr` track does not size the `auto` track, so the arrows never move when row 2 changes.

Do not change the `@media (min-width:1024px)` 32 px title rule, the phone rules (`max-width:767px`, Today stays
`display:none` there) or the cleaning-page rules. If `.cal-head` has any other visible child at 768 that is not
placed by the rules above (check in Step 4 screenshots), give it `grid-column:1 / -1` and report it.

## Step 3: new browser test `App/tests/test_0910_calendar_toolbar_stable_browser.py`

Reuse the fixtures and helpers; copy the import lines from the top of `App/tests/test_dashboard_calendar_browser.py`
and add `from tests.test_dashboard_calendar_browser import calendar_origin, launch, open_page, wait_loaded, shot, GEOMETRY_0893  # noqa: F401`.

```python
BOXES = """() => Object.fromEntries(['[data-cal-prev]','[data-cal-next]','[data-cal-today]','[data-cal-property]',
  '.cal-view-segment','[data-cal-settings]','[data-cal-scales]','[data-cal-month]','[data-cal-year]'].map(s => {
  const e = document.querySelector('#calendar ' + s); const r = e.getBoundingClientRect();
  return [s, [r.left, r.top, r.width, r.height].map(v => Math.round(v * 2) / 2)]; }))"""
```

Tests (each opens `f"{calendar_origin}/?lang={lang}&cal_view=calendar&cal_date=2026-01-01"`, waits for `.cal-month`
or `.cal-week`, then `wait_loaded(page)`):

1. `test_0910_toolbar_still_across_12_arrow_clicks` parametrized `width` in `[768, 1024]`, `scale` in
   `["month", "week"]`, `lang` in `["en", "cs"]`. If scale is week click `[data-cal-scale="week"]` and wait.
   Take `base = page.evaluate(BOXES)`. Then 12 times: click `[data-cal-next]`, `wait_loaded(page)`,
   `assert page.evaluate(BOXES) == base, (i, page.locator("[data-cal-period]").inner_text())`. Then 12 times the same
   with `[data-cal-prev]`. Finally `assert not page.evaluate(GEOMETRY_0893)["touching"]` (12 px neighbour rule).
2. `test_0910_scale_switch_keeps_arrows_and_filters_still` parametrized `width` in `[768, 1024, 1280]`: record BOXES
   for `[data-cal-prev]`, `[data-cal-next]`, `[data-cal-today]`, `[data-cal-property]`, `.cal-view-segment`,
   `[data-cal-settings]`; click scale week, year, month in turn; after each, those six boxes equal the first record.
3. `test_0910_today_is_not_between_the_arrows` parametrized `width` in `[768, 1024, 1280]`: with rects `t`, `p`, `n`
   of Today, Prev, Next: `t.right + 20 <= p.left`; `12 <= n.left - p.right <= 16`; `abs(t.top + t.height/2 - (p.top + p.height/2)) <= 1`.
   Then click Today and assert `[data-cal-period]` text is the current month name (`page.evaluate` of the
   `data-today` month is enough: compare `[data-cal-month]` value to `root.dataset.today.slice(5,7)`).
   Call `shot(page, f"0910-{width}")`.

Use `context.close(); browser.close()` at the end of each test like the existing file.

## Part A: stay page shows birth date, nationality and document number

Owner request: the host sees who the guest is without opening the PDF form. Host-only page.

Facts (checked, do not re-research): the route `reservation_detail` in `App/app/routes/admin.py` (~line 3555)
builds `guest_rows` from `reporting.reservation_progress(reservation)["guests"]`, which reads
`SELECT * FROM guest`. The db helpers decrypt on read (`db._hydrate`): `guest.birth_date` (stored as `DDMMYYYY`)
and `guest.doc_number` are already plaintext in the template. **No route change.** Use the existing template
globals: `display_birth_date(value)` (gives `DD.MM.YYYY`, the format of the guest forms), `country_name(code, lang)`,
`guest_identifier(value, guest_id)` (masks the document number when the viewer may not see identity, e.g. support
impersonation) and `identity_visible(guest_id)`. Copy the pattern of `App/app/templates/submission_detail.html`
line ~126. Existing i18n key `stay.detail.guests.born` ("Date of birth" / "Datum narození" / "Ngày sinh"); no new key.

1. `App/app/templates/reservation_detail.html`, desktop table (`<div class="card guest-table">`, ~line 194). Directly
   after the line that starts `<b>{{ guest.first_name or '' }} {{ guest.surname or '—' }}</b>` insert:
   ```jinja
        {% set id_parts = [] %}
        {% if guest.birth_date and identity_visible(guest.id) %}{% set _ = id_parts.append(t('stay.detail.guests.born') ~ ' ' ~ display_birth_date(guest.birth_date)) %}{% endif %}
        {% if guest.nationality %}{% set _ = id_parts.append(country_name(guest.nationality, lang) or guest.nationality) %}{% endif %}
        {% if guest.doc_number %}{% set _ = id_parts.append(guest_identifier(guest.doc_number, guest.id)) %}{% endif %}
        {% if id_parts %}<small class="guest-id-line" data-guest-id-line>{{ id_parts | join(' · ') }}</small>{% endif %}
   ```
   It renders as the first `<small>` under the name (the table CSS `.host-stay-detail .guest-table small` is already
   `display:block; font-size:13px; color:var(--ink3)`).
2. Phone/tablet list (`<div class="list guests guest-list">`, ~line 240; shown below 1024 px). Inside its `for`, put
   the first four lines of the block above (the `set` and three `if ... append` lines) directly above the
   `<a class="row" ...>` line, and change
   `<div class="t"><b>...</b><small>` to `<div class="t"><b>...</b>{% if id_parts %}<small class="guest-id-line" data-guest-id-line>{{ id_parts | join(' · ') }}</small>{% endif %}<small>`
   (keep `...` exactly as it is now).
3. Check in the screenshots (Part D) that the id line is on its own line, 13 px or larger, and does not touch the
   name or the state line (12 px neighbour rule from the layout lint). Only if the phone `.t small` lines run into each
   other, add to `App/app/static/app2.css` after line ~596:
   `.host-stay-detail .guest-list .t small{display:block}` and bump that stylesheet's `?v=` in the template that loads
   it (grep `app2.css?v=` in `App/app/templates/`). Otherwise do not touch CSS.

No fine print: the line is guest data, not a hint. Do not add labels for nationality or document; the document type
stays in its own column.

## Part B: stay-fee detail shows birth date, age at check-in and nationality

The fee depends on age (under 18 exempt), so the host checks it here. Route `stay_fee_detail` in
`App/app/routes/stay_fees.py` passes `"lines": _guest_lines(apartment, period)` (~line 447); `_guest_lines` is at
~line 489. **Do not add fields in `App/app/stay_fee.py`:** its `period["lines"]` are stored (encrypted) in the filing
snapshot by `stay_fee_filing`, so adding birth date there would create a new stored copy. Add them only in the route.

1. In `_guest_lines`, before `lines = []`, add one query for all the period's guests:
   ```python
   ids = [line["guest_id"] for line in period["lines"]]
   facts = {}
   if ids:
       marks = ",".join("?" for _ in ids)
       # Display only: birth date, age and nationality are read, never stored on the line.
       for row in db.query(
           "SELECT g.id, g.birth_date_enc, g.nationality, COALESCE(g.stay_from, r.date_from) AS check_in "
           f"FROM guest g JOIN reservation r ON r.id = g.reservation_id WHERE g.id IN ({marks})",
           tuple(ids),
       ):
           birth = validation.parse_birth_date(row["birth_date"] or "")
           check_in = validation.parse_iso_date(row["check_in"])
           facts[row["id"]] = {
               "birth_display": validation.display_birth_date(row["birth_date"]) if row["birth_date"] else "",
               "age_at_check_in": validation.age_on(birth, check_in) if birth and check_in else None,
               "nationality": row["nationality"] or "",
           }
   ```
   (`db.query` decrypts `birth_date_enc` into `row["birth_date"]`; `validation.parse_iso_date` exists, used by
   `validation.fmt_date`.) In the `lines.append({...})` dict add one line: `**facts.get(line["guest_id"], {"birth_display": "", "age_at_check_in": None, "nationality": ""}),`
   right after `**line,`.
2. New i18n key `stay_fees.guest.age`, added right after the `"stay_fees.nights.few"` line in each block (grep it):
   en `"Age %(age)s at check-in"`, cs `"Věk %(age)s při příjezdu"` (both in `App/app/host_i18n.py`), vi
   `"%(age)s tuổi khi nhận phòng"` (`App/app/host_vi_i18n.py`).
3. `App/app/templates/stay_fee_detail.html`, in `<li class="fee-line">` (~line 213), directly after the existing
   `<div class="ui-sub">{{ line.stay_from }} – ...</div>` line insert:
   ```jinja
            {% set fee_parts = [] %}
            {% if line.birth_display and identity_visible(line.guest_id) %}{% set _ = fee_parts.append(t('stay.detail.guests.born') ~ ' ' ~ line.birth_display) %}{% endif %}
            {% if line.age_at_check_in is not none %}{% set _ = fee_parts.append(t('stay_fees.guest.age', age=line.age_at_check_in)) %}{% endif %}
            {% if line.nationality %}{% set _ = fee_parts.append(country_name(line.nationality, lang) or line.nationality) %}{% endif %}
            {% if fee_parts %}<div class="ui-sub" data-fee-guest-facts>{{ fee_parts | join(' · ') }}</div>{% endif %}
   ```

## Privacy (Parts A and B)

Host-only pages behind `auth.require_login` and the owner checks already there. No new stored field, no new column,
no migration, no new outbound request, no new dependency. `App/app/retention.py` is unaffected: birth date,
nationality and document number are existing guest fields with existing retention lines; this change only displays
them. Doc numbers go through `guest_identifier` and birth dates through `identity_visible`, so the existing masking
still applies. Say this in the PR body in two sentences.

## Part C: browser Back after three month clicks (test only)

`App/app/static/dashboard-calendar.js` `rememberURL()` uses `history.replaceState`, so arrow clicks add no history
entries. Expected: Back leaves the calendar for the previous page; Forward (or reopening) returns to the month the
user was on, because the URL carries `cal_date`. **Do not change history handling.**

Add to `App/tests/test_0910_calendar_toolbar_stable_browser.py`:

4. `test_0910_back_after_three_month_clicks` (width 1280, `lang=en`). Read `open_page` in
   `App/tests/test_dashboard_calendar_browser.py` (lines ~60-91) to get the page; then `page.goto(f"{calendar_origin}/reservations")`,
   then `page.goto(f"{calendar_origin}/?lang=en&cal_view=calendar&cal_date=2026-01-01")`, wait for `.cal-month`,
   `wait_loaded(page)`. Click `[data-cal-next]` 3 times with `wait_loaded(page)` after each; record
   `after = page.url` and `month = page.locator("[data-cal-month]").input_value()`; assert `"cal_date=2026-04"` in
   `after`. `page.go_back()`; assert `"/reservations"` in `page.url`. `page.go_forward()`, wait for `.cal-month`,
   `wait_loaded(page)`; assert `page.locator("[data-cal-month]").input_value() == month`.
   If an assertion fails, change it to match what actually happens, print the observed URL and month, and report
   it in the PR under "Back button". If Forward lands on a month other than April 2026 (the user's place is lost),
   do not fix it: write it in the report as follow-up "0910 follow-up: calendar loses place on Forward/Back".

## Part D: tests for Parts A and B

5. New file `App/tests/test_0910_guest_details_browser.py`. Copy the imports of
   `App/tests/test_0766_phone_stays_browser.py` (fixtures `base`, `dashboard_rich_host`, helpers `_launch`, `_open_app`,
   `_cookie`; copy `_cookie` too). That fixture's `ready` stay has guest TOMAS NOVAK, birth `01011990`, nationality
   `GBR`, doc `P1234567`. Test `test_0910_stay_page_shows_guest_details` parametrized `width` in `[390, 768, 1280]`:
   open `f"/reservations/{dashboard_rich_host['ready']}"`; `line = page.locator("[data-guest-id-line]:visible").first`;
   assert `"01.01.1990"` in its text, and `"P1234567"` in it; assert its computed `font-size` >= 13 px; assert its
   box does not overlap the `b` name box above it. Call `shot(page, f"0910-stay-{width}")` (import `shot` from
   `tests.test_dashboard_calendar_browser`).
6. In `App/tests/test_stay_fee_detail.py` add (reuse `host`, `_property`, `_stay`):
   `test_guest_line_shows_birth_date_age_and_nationality`: `_stay(apartment_id, "2026-08-10", "2026-08-14", [{"first_name": "Adult"}, {"first_name": "Kid", "birth_date": "01012015"}])`;
   GET `/stay-fees/{apartment_id}?month=2026-08&lang=en`; assert `"01.01.1990"`, `"Age 36 at check-in"`,
   `"01.01.2015"`, `"Age 11 at check-in"` and `"Germany"` in the text. Then grep the stored filing payload is
   unaffected: assert `"birth_display"` not in `str(stay_fee.property_period(apartment, date(2026, 8, 1))["lines"])`
   (import `stay_fee`; load `apartment` with `db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))`).
7. Screenshot of the fee page: if `App/tests/test_stay_fee_pay_steps_browser.py` has a fixture that opens
   `/stay-fees/<id>` in Chromium, add `test_0910_fee_page_shot` there-alike in the new file
   `test_0910_guest_details_browser.py` using that fixture, with a guest that has a birth date, at 390/768/1280 and
   `shot(page, f"0910-fee-{width}")`, asserting `[data-fee-guest-facts]` is visible. If no such fixture exists, say
   so in the report and skip the fee screenshots (do not build a new fixture).

## Step 4: run (from `App/`, Chromium is at /opt/pw-browsers)

```
export PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1
.venv/bin/python -m pytest tests/test_0910_calendar_toolbar_stable_browser.py -q --tb=short -x 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_dashboard_calendar_browser.py tests/test_0905_cleaning_calendar_stays_browser.py tests/test_0898_calendar_names_browser.py -q --tb=short 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_dashboard_calendar.py tests/test_calendar_*.py tests/test_sample_calendar.py -q --tb=short 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_0910_guest_details_browser.py -q --tb=short -x 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_stay_fee*.py -q --tb=short -x 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py -q --tb=short 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_*_i18n.py tests/test_no_em_dashes.py -q --tb=short 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_layout_lint_browser.py -q --tb=short 2>&1 | tail -30
```

All green with **0 skipped** in the browser files. If an existing test asserts the old Today position (grep
`data-cal-today` in `App/tests/`), update only that assertion and say so in the report. From the repo root:
`python3 scripts/context_lint.py`.

Screenshots: rerun test 3 with `UBYHOST_SHOTS_DIR=/tmp/0910-shots`, plus one 390 px shot (any existing 390 calendar
test with the same env var, e.g. `-k "0891 and 390"`). Open the 390, 768, 1024 and 1280 shots and write per width
in the PR what you saw (Today left of the arrows with a clear gap; arrows side by side; filters on row 2; title not
clipped in Month). Copy them into `docs/tasks/screenshots-0910/`.
Also rerun `tests/test_0910_guest_details_browser.py` with the same env var and open the `0910-stay-*` and
`0910-fee-*` shots (390, 768, 1280): per page and width, write in the PR whether the id line sits under the name on
its own line, is readable, and keeps 12 px from its neighbours.

## Step 5: PR

PR body: link this brief, the per-width UX notes, and the ticked checklist from `docs/design/design-system.md`
(copy its checklist lines; only the items this change touches need prose). Merge only with
`scripts/merge-pr-on-green.sh`. Write `docs/tasks/0910-report.md` (what changed, test output tails, screenshot paths).

## Done when

- 12 next + 12 prev clicks at 768 and 1024 (Month and Week, en and cs) move no toolbar control by even 0.5 px.
- Scale switch does not move the arrows, Today, property, view or settings at 768, 1024, 1280.
- Today sits left of the arrow pair, at least 20 px away; no control pair closer than 12 px.
- Phone (< 768) unchanged: Today hidden, arrows right of the title.
- Stay page at 390, 768 and 1280: each guest shows birth date, nationality and (masked when required) document
  number on one line under the name.
- Stay-fee detail: each guest line shows birth date, "Age N at check-in" and nationality; nothing new in the stored
  period lines.
- Back-button test passes and the PR states the observed Back/Forward behaviour (and the follow-up if the place is lost).
- Layout lint green, 0 skipped in every browser file, PR has the privacy note and the per-page UX notes.

## 7. Acceptance

The "Done when" list above is the acceptance list. Each item is ticked in `docs/tasks/0910-report.md` with the command output that proves it.

## 8. Stop and ask

Stop and ask the owner (do not guess) when: a step's anchor text is not found; a test fails twice after one fix; a browser test is skipped; a screenshot shows a layout problem the brief does not cover; a change would touch a file the brief does not name; or the work needs a new dependency, migration, secret or deploy.

## 9. Report

Write `docs/tasks/0910-report.md` (600 tokens at most) as set out in `docs/context/executor.md`. Set `Status: review` or `Status: blocked`.
