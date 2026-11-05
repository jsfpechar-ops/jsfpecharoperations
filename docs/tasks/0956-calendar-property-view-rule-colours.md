# 0956: Calendar view rule (Gantt only for 3+ properties, never for one) and one colour per property; stay bars no longer cover cleaning chips

Status: todo
Depends on: 0955 (same files). Start only when `docs/tasks/0955-report.md` says `Status: review` and
`git status --short App/` lists no changed file from section 3. Otherwise stop and ask.
Branch: the current branch, on top of the 0955 commits (do not create one, do not rebase).
Executor: Haiku 5.5. Read only AGENTS.md, docs/context/executor.md, this brief and the files named here.
Fits one session: 30 tool calls, 60k tokens. If not done by then, commit, write the report with `Status: blocked`.

## 1. Objective

Josef's rule, global for the host calendar (`/?cal_view=calendar`) and the cleaning calendar (`/cleaning`), both
rendered by `App/app/static/dashboard-calendar.js` (`cleaningMode` = `root.dataset.cleaning === "true"`):

- **Part A1.** When one property is picked in the property select, only the calendar (tiles) view is shown and the
  Calendar/Gantt toggle (`.cal-view-segment`) is hidden.
- **Part A2.** Gantt is offered only to hosts with 3 or more active properties (and never while one is picked).
  Below 3 the toggle is hidden and a saved or URL `cal_view=gantt` falls back to the calendar.
- **Part A3.** Each property has its own colour, the same in stay bars (`.cal-pill`), tile chips and dots, list-view
  events, the property select (a colour dot when a property is picked) and Gantt row names.
- **Part B (bug).** In the month tiles of `/cleaning` at >= 768 px, stay bars cover the cleaning chips of the
  departure day (second chip hidden). Bars and chips get fixed vertical bands: bars on top, chips below, never overlapping.

## 2. Context (checked 2026-11-04, do not re-research)

### View logic today (`dashboard-calendar.js`)

- Line ~40: `function autoView(mode, propertyCount) { return mode === "auto" ? (propertyCount >= 3 ? "gantt" : "calendar") : mode; }`
- Line ~135: `function view() { return phoneDots() ? "calendar" : autoView(state.mode, state.property ? 1 : state.properties.length); }`
  So Auto already obeys the rule, but an explicit `state.mode === "gantt"` (button click, saved preference,
  `?cal_view=gantt`) shows Gantt for one property and for hosts with 1-2 properties. That is the bug to close.
- `syncControls()` (line ~189) sets `aria-pressed` on `[data-cal-view]` buttons and hides `[data-cal-scales]` in Gantt.
- Property select handler: line ~921 `$("[data-cal-property]").addEventListener("change", ...)`; view buttons: line ~932.
- `fillProperties(select, all)` (line ~171) fills the select from `state.properties` (from
  `<script data-cal-properties>` in `App/app/templates/_dashboard_calendar.html` line ~170: active apartments, `{id, name}`).
- Template: `.cal-view-segment` (line ~9) and the settings row `<label class="cal-setting">...<input data-cal-auto>` (line ~81).
  `.cal-segment` and `.cal-setting` have `display:inline-flex` / `display:flex` in CSS, so the `hidden`
  attribute alone does not hide them (Step A1.3 adds the rule).

### Colours today

- `dashboard-calendar.js` line ~224: `function propertyColor(id) { return ["teal", "blue", "purple"][Math.abs(Number(id)) % 3]; }`,
  used on list-view `.cal-event` (line ~250), tile dots and chips (~380, ~384) and Gantt names (~516).
  **Not** used on the month stay bars: `.cal-pill` is `background:#222` (`dashboard-calendar.css` line ~764).
- `dashboard-calendar.css` lines 48-50: `[data-cal-color="teal|blue|purple"] { --cal-ink:...; --cal-fill:...; }`.
  Gantt name dot: line ~74 `.cal-gantt-name[data-cal-color]::before { background:var(--cal-ink); }`.
- Tokens (`App/app/static/tokens.css` lines 39-44): `--teal #08736b`, `--blue #245cb5`, `--indigo #4f4aae`,
  `--purple #7840a2` (each with a `-bg` tint), `--amber #8a5200`, `--green #167044`; `--ink #20201e`; `--surface-2`.
  Cleaning chips are amber (`--status-action-bg` / `--status-action-ink`, css line ~718). Design system rule 9:
  coral is a signal only; badges: green = verified, amber = look. So the property palette uses **no coral, green, amber or red**.

### Palette decision (orchestrator, 2026-11-04)

Five tones, solid bar with white text (keeps today's Airbnb dark-bar look, just tinted). White text contrast on each:
teal 5.7:1, blue 6.4:1, purple 6.9:1, indigo 7.2:1, ink 16.3:1, all AA.

| Index | `data-cal-color` | `--cal-ink` (bar, dot) | `--cal-fill` (list-view tint) |
|---|---|---|---|
| 0 | `teal` | `var(--teal)` | `var(--teal-bg)` |
| 1 | `blue` | `var(--blue)` | `var(--blue-bg)` |
| 2 | `purple` | `var(--purple)` | `var(--purple-bg)` |
| 3 | `indigo` | `var(--indigo)` | `var(--indigo-bg)` |
| 4 | `ink` | `var(--ink)` | `var(--surface-2)` |

Index = position of the property in the active properties sorted by numeric id, modulo 5 (unique for up to 5
properties; a 6th repeats teal, the bar text still names it). A stay of a property not in the list falls back to
`Math.abs(Number(id)) % 5`. Native `<option>` elements cannot show a coloured dot on every platform, so the select
shows the dot only for the picked property (Step A3.4); the host learns the colours from the bars and Gantt names.

### Part B geometry today (cleaning page, >= 768 px, `.cal-week.is-dots`)

- Each week row is `position:relative`; the bars live in `.cal-pills` (`position:absolute; inset:0;
  grid-template-columns:repeat(14,...)`, `align-content:end; padding-bottom:12px; row-gap:12px`, pill 32 px high),
  css lines ~763 and ~798. So the bars sit at the **bottom** of the row.
- The cleaning chips (`.cal-tile-chips > .cal-tile-chip.cal-clean-chip`, 24 px high, css ~657 and ~805) flow inside
  the day button `.cal-day-number` (padding 12, after `.cal-num` 28 px), so they grow **down** from the top.
- Cell height: `App/app/static/app2.css` line ~2219, `.cal-week.is-dots .cal-day { min-height:calc(150px + (var(--pl,1) - 1) * 44px); }`
  where `--pl` = lanes in that week (set on the row by `pillRow()`, line ~395).
- Bars end at the middle of the departure cell minus g/2 (0930 rule: `docs/tasks/0930-calendar-pill-departure-day.md`
  sections 4 and 4b, `g = getComputedStyle(.cal-pills).columnGap`, 12 px at >= 768). That end point stays.
- With two lanes and two chips the bottom bands meet and the bars (z-index 1) cover the chips. Reproduce with the seed
  `_seed()` of `App/tests/test_0905_cleaning_calendar_stays_browser.py` (two flats, stays ending Sun 8 Nov 2026,
  one cleaning each on 8 Nov) at `/cleaning?lang=en&cal_date=2026-11-03`.

Desired geometry (>= 768 px, cleaning page only; the host dashboard hides chips, css line ~762):

```
+-------------------------+  tile top
|          8              |  number band: 52 px (12 padding + 28 number + 12)
| ==bar lane 1==)         |  lane band: --pl lanes x 44 px (32 bar + 12 gap); bar ends mid-tile - g/2 (0930)
| ==bar lane 2==)         |
| [clean chip 1        ]  |  chips band: starts 8 px under the last lane, 24 px chips, 4 px apart
| [clean chip 2        ]  |
+-------------------------+  tile bottom, >= 12 px under the last chip
```

## 3. Files

You may change only: `App/app/static/dashboard-calendar.js`, `App/app/static/dashboard-calendar.css`,
`App/app/templates/_dashboard_calendar.html` (cache keys only), `App/app/static/app2.css` (the one cleaning
min-height rule at line ~2219 and its cache key if the static-versions test asks), the template(s) that
`tests/test_static_versions.py` names for the bumped keys, its manifest (via `--write`),
`App/tests/test_dashboard_calendar_browser.py` (only the lines named in Step A4), the new
`App/tests/test_0956_calendar_rule_colours_browser.py`, `docs/tasks/0956-report.md`, `docs/tasks/screenshots-0956/`.

## 4. Steps

### Part A1 + A2: the view rule (`dashboard-calendar.js`)

1. Directly above `function view()` add:
   ```js
   // 0956: Gantt only for 3+ properties and never while one property is picked (Josef, 2026-11-04).
   function ganttAllowed() { return !state.property && state.properties.length >= 3; }
   ```
   and change `view()` to:
   ```js
   function view() { return phoneDots() || !ganttAllowed() ? "calendar" : autoView(state.mode, state.properties.length); }
   ```
   Keep `state.mode` unchanged when a property is picked: clearing the filter back to "All" brings back the
   view the host chose (Gantt if they chose Gantt or Auto with 3+). Do not change `autoView`.
2. In `syncControls()`, after the `[data-cal-scales]` line add:
   ```js
   $(".cal-view-segment").hidden = !ganttAllowed();
   $("[data-cal-auto]").closest(".cal-setting").hidden = !ganttAllowed();
   ```
   (Auto only switches between Calendar and Gantt, so it is pointless when Gantt is not offered.)
3. CSS (`dashboard-calendar.css`, end of file, new block with the comment `/* 0956: view rule */`):
   ```css
   .dashboard-calendar :is(.cal-view-segment, .cal-setting)[hidden] { display:none !important; }
   ```
   `!important` is needed because several width-specific rules set `display` on these elements.
4. No change to the URL code (`cal_view` stays whatever `state.mode` is), the scale buttons, or `range()`.

### Part A3: one colour per property

1. Replace `propertyColor` (line ~224) with:
   ```js
   // 0956: one tone per property, by position among the active properties sorted by id (design palette, no coral/green/amber).
   const PROPERTY_TONES = ["teal", "blue", "purple", "indigo", "ink"];
   const toneIndex = new Map(properties.map(item => Number(item.id)).sort((a, b) => a - b).map((id, index) => [String(id), index]));
   function propertyColor(id) { const index = toneIndex.get(String(Number(id))); return PROPERTY_TONES[(index === undefined ? Math.abs(Number(id)) : index) % PROPERTY_TONES.length]; }
   ```
   (`properties` is the parsed `data-cal-properties` const at line ~102, defined before this point; check it is.)
2. In `pillRow()`, after `pill.dataset.calEvent = ...` add
   `pill.dataset.calColor = propertyColor(event.propertyId); pill.dataset.calPropertyId = String(event.propertyId);`.
3. In `fillProperties(select, all)`, at the end, when `all` is true:
   `if (select.value) select.dataset.calColor = propertyColor(select.value); else delete select.dataset.calColor;`.
4. CSS (same `0956` block):
   ```css
   [data-cal-color="indigo"] { --cal-ink:var(--indigo); --cal-fill:var(--indigo-bg); }
   [data-cal-color="ink"] { --cal-ink:var(--ink); --cal-fill:var(--surface-2); }
   body.v2 #calendar.dashboard-calendar[data-readonly="false"] .cal-pill[data-cal-color] { background:var(--cal-ink); color:#fff; }
   body.v2 #calendar.dashboard-calendar[data-readonly="false"] .cal-pill[data-cal-color]:hover { background:var(--cal-ink); filter:brightness(.88); }
   body.v2 #calendar.dashboard-calendar[data-readonly="false"] .cal-pill[data-cal-color] .cal-pill-avatar { background:rgba(255,255,255,.24); }
   ```
   Put the two token lines next to lines 48-50 instead if you prefer; one place only. The phone thin bars of the
   cleaning page (`app2.css` ~2225) take the colour from the same `background` rule: check it is not overridden
   (grep `cal-pill` in `app2.css`; if a `background` is set there, report it, do not edit it).
5. Select dot: grep the select's existing `background-image` (`grep -n "select" App/app/static/app2.css App/app/static/tokens.css | grep -n "background-image\|appearance"`).
   Add to the 0956 block a rule for `.dashboard-calendar select[data-cal-property][data-cal-color]` with
   `padding-left:32px` and a 10 px dot drawn as the **first** background layer:
   `radial-gradient(circle at 16px 50%, var(--cal-ink) 0 5px, transparent 5.5px)`, followed by the existing chevron
   layer copied exactly (with matching comma lists for `background-position`, `background-size`, `background-repeat`).
   If the select has no background-image, use the gradient alone with `background-repeat:no-repeat`.
   Do not change the select's height, width or text.

### Part B: bars on top, chips below (cleaning page, >= 768 px only)

1. In `dashboard-calendar.css`, 0956 block, inside `@media (min-width:768px) { ... }`:
   ```css
   body.v2 #calendar.dashboard-calendar[data-readonly="false"][data-cleaning="true"] .cal-week.is-dots { --cal-num-band:52px; --cal-lane:44px; }
   body.v2 #calendar.dashboard-calendar[data-readonly="false"][data-cleaning="true"] .cal-pills { align-content:start; padding-top:var(--cal-num-band); padding-bottom:0; }
   body.v2 #calendar.dashboard-calendar[data-readonly="false"][data-cleaning="true"] .cal-tile-chips { margin-top:calc(var(--cal-num-band) + var(--pl,1) * var(--cal-lane) - 12px - 28px); }
   ```
   The chip offset is measured from the top of the chips' normal place (under `.cal-num`); `- 12px - 28px` removes
   the button padding and the number. If Step B3 shows the chips 8 px under the last lane is off by a few px, change
   only that `calc` (and say the final value in the report); do not move the bars.
2. `app2.css` line ~2219: change the cleaning tile rule to
   `min-height:calc(52px + var(--pl,1) * 44px + 2 * 24px + 4px + 8px + 12px);` (number band + lanes + two chips +
   gap + 8 px under the last lane + 12 px bottom). Keep the `@media (max-width:767px)` phone rule as it is.
   The "+N" text (`.cal-tile-more`) under two chips may add 16 px: if the B3 test shows it outside the tile, add
   `16px` to that calc and report it.
3. Keep `pillRow()` and the 0930 half-day columns untouched; the bar end point does not change.
4. Bump the `?v=` keys of every changed static file to `20261105-0956` (`_dashboard_calendar.html` lines 2 and
   ~173; app2.css where `tests/test_static_versions.py` says), then from `App/`:
   `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30`.

### Part A4: existing test (`App/tests/test_dashboard_calendar_browser.py`)

`test_auto_view_threshold_filter_and_manual_override` (line ~104) clicks Gantt while one property is picked
(lines ~111-116). Replace exactly those lines (from `page.locator('[data-cal-view="gantt"]').click()` through the
`wait_for_function(... length === 3")` line) with:
```python
        assert not page.locator(".cal-view-segment").is_visible()
        assert page.locator(".cal-gantt-row").count() == 0
        page.locator("[data-cal-property]").select_option("")
        page.wait_for_function("() => document.querySelectorAll('.cal-gantt-row').length === 3")
        assert page.locator(".cal-view-segment").is_visible()
```
Change nothing else in that file. If another existing test fails on the old Gantt-for-one behaviour or on the
`#222` bar colour, change only that assertion and list it in the report.

### Part C: new test `App/tests/test_0956_calendar_rule_colours_browser.py`

Imports: copy the top imports of `App/tests/test_dashboard_calendar_browser.py`; add
`from tests.test_dashboard_calendar_browser import calendar_origin, launch, open_page, wait_loaded, shot  # noqa: F401`,
`from tests.test_dashboard_calendar import calendar_workspace  # noqa: F401` (3 properties) and from
`tests.test_0905_cleaning_calendar_stays_browser` import `_seed`; from `tests.test_host_geometry` import
`_browser_session_cookie, base  # noqa: F401`. For the 2-property host open pages like the 0905 test does (cookie
for `_seed()`'s username, `base + path`). Every test ends with `context.close(); browser.close()`.

1. `test_0956_one_property_shows_only_the_calendar` parametrized `path` in `["/", "/cleaning"]`, `width` in `[768, 1280]`
   (3-property workspace): goto `f"{calendar_origin}{path}?lang=en&cal_view=gantt&cal_date=2026-10-01"`; assert
   `.cal-gantt-row` count 3 and `.cal-view-segment` visible. Select `properties[0]`: wait for `.cal-week`; assert
   `.cal-gantt-row` count 0, segment not visible. Reload with `&cal_property=<id>` added: `.cal-week`, segment hidden.
   Select `""`: Gantt rows 3 again, segment visible.
2. `test_0956_under_three_properties_never_offers_gantt` parametrized `path` in `["/", "/cleaning"]`, `width` in
   `[768, 1280]` (2-property `_seed()` host): goto `{path}?lang=en&cal_view=gantt&cal_date=2026-11-03`; assert
   `.cal-week` present, `.cal-gantt-row` count 0, `.cal-view-segment` not visible; open `[data-cal-settings]` and
   assert the `[data-cal-auto]` row is not visible.
3. `test_0956_each_property_has_one_colour_everywhere` width 1280, 3-property workspace, `/`:
   in Gantt read `{name: getComputedStyle(el, '::before').backgroundColor}` of `.cal-gantt-name[data-cal-color]`
   (rows only, not the header); assert 3 distinct colours and none equals amber `rgb(138, 82, 0)` or the cleaning
   chip background. Click `[data-cal-view="calendar"]`; for each `.cal-pill` assert its `backgroundColor` equals the
   Gantt colour of its property (map via `data-cal-property-id` and the property names in
   `[data-cal-properties]`) and its text colour is `rgb(255, 255, 255)`. Select `properties[1]`: assert the
   select's computed `backgroundImage` contains `radial-gradient` and that property's colour. `shot(page, "0956-colours-1280")`.
4. `test_0956_bars_never_cover_cleaning_chips` parametrized `width` in `[768, 1024, 1280]` (`_seed()` host,
   `/cleaning?lang=en&cal_date=2026-11-03`, wait `.cal-week`, `wait_loaded`). In the week row containing
   `[data-date="2026-11-08"]`: tile `t` = that day; chips = `t.locator(".cal-clean-chip")` (expect 2, both visible);
   pills = the row's `.cal-pill` (expect 2). With `g = parseFloat(getComputedStyle(row .cal-pills).columnGap)`:
   - each pill: `right <= t.x + t.width/2 - g/2 + 1` (0930 end) and `bottom <= row bottom`;
   - no pill box intersects any chip box; each chip `top >= max(pill bottoms) + 7`; each chip `bottom <= t bottom - 11`;
   - `document.elementFromPoint` at each chip's centre is the chip or inside it.
   `shot(page, f"0956-cleaning-{width}")`.
5. `test_0956_phone_cleaning_tiles_unchanged` width 390, same page: assert the two thin bars are visible, each
   `<= 10` px high, and none intersects a `.cal-clean-tag` box in the 8 Nov tile. `shot(page, "0956-cleaning-390")`.
   If it fails before any Part B change too, stop and ask (phone is out of scope).

## 5. Do not touch

- The 0955 toolbar grid rules, the 0930 half-day columns and lane logic in `pillRow()`, the "+N" button.
- The phone (`max-width:767px`) cleaning rules in `app2.css`, the dashboard phone dots' layout, the list view layout.
- `tokens.css` and `host2.css` `--property-*` tokens (used elsewhere; the calendar keeps its own `data-cal-color` map).
- i18n files: no new key and no copy change. URL handling, history, preferences format.
- No new dependency, migration, stored field or outbound request.

## 6. Commands

From `App/` (Chromium is at /opt/pw-browsers):
```
export PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1
.venv/bin/python -m pytest tests/test_0956_calendar_rule_colours_browser.py -q --tb=short -x -rs 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_dashboard_calendar_browser.py tests/test_0905_cleaning_calendar_stays_browser.py tests/test_0955_calendar_toolbar_stable_browser.py tests/test_0898_calendar_names_browser.py tests/test_cleaning_browser.py -q --tb=short -rs 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_dashboard_calendar.py tests/test_calendar_*.py tests/test_sample_calendar.py tests/test_cleaning.py tests/test_design_cleaning.py tests/test_static_versions.py -q --tb=short 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_layout_lint_browser.py -q --tb=short -rs 2>&1 | tail -30
```
All green, **0 skipped** in every browser file. Before Part B, run test 4 once and paste its failure (the
reproduction) into the report. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

Screenshots: rerun the new file with `UBYHOST_SHOTS_DIR=/tmp/0956-shots`, plus `-k "0891 and (390 or 768)"` from
`test_dashboard_calendar_browser.py` with the same variable for the dashboard at 390/768. Open every shot
(390, 768, 1024, 1280 for `/cleaning`; 390, 768, 1280 for `/`) and write per page and width what you saw: bar
colours differ per property and match the Gantt dots; no Gantt toggle when one property is picked; on 8 Nov both
cleaning chips readable under the bars, 12 px from neighbours; nothing clipped. Copy them to `docs/tasks/screenshots-0956/`.

Commit on the current branch: `0956: Gantt only for 3+ properties, one colour per property, chips under stay bars`.
Do not push, do not open a PR (the orchestrator does, after review).

## 7. Acceptance

- One property picked (dashboard and cleaning, 768 and 1280): calendar tiles only, Gantt toggle and Auto row hidden;
  back to "All" restores the host's view.
- Host with 2 properties: Gantt never shown, even with `?cal_view=gantt`; toggle and Auto row hidden.
- Host with 3 properties: three distinct non-amber, non-coral, non-green colours; each stay bar's colour equals its
  property's Gantt dot; white bar text; the select shows the picked property's dot.
- Cleaning page at 768, 1024, 1280: on 8 Nov two cleaning chips fully visible below both bars; bars end at the 0930
  point; nothing leaves its tile. Phone 390 unchanged.
- All commands in section 6 green, 0 skipped; screenshots and per-width notes in the report.

## 8. Stop and ask

Stop and ask (do not guess) when: 0955 is not committed (header); an anchor or line named here is not found; a
test fails twice after one fix; a browser test is skipped; a screenshot shows a layout problem this brief does not
cover; a change would touch a file not in section 3; the phone test fails before your change.

## 9. Report

Write `docs/tasks/0956-report.md` (600 tokens at most) as set out in `docs/context/executor.md`: what changed per
part, the Part B reproduction and final `calc` values, every existing assertion you changed, test output tails,
screenshot paths with one line each. Set `Status: review` or `Status: blocked`.
