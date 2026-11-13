# 1293: host dashboard redesign, part C of 3: Today list, This week strip, cleanup and docs (laptop and tablet)

Status: todo
Depends on: 1292 (merged, or stacked on `task/1292-dashboard-redesign-b`) | Base commit: origin/main | Branch: task/1293-dashboard-redesign-c
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (5 steps, 26 calls plus PR and report; if over 30 stop after step 4 and report "Done: steps 1 to 4. Left: step 5")
Brief by Sonnet 5.5, 2026-11-12, revised 2026-11-13 (renumbered from 1134, Figma numbers verified with the Figma MCP, geometry tests). Owner Josef approved Figma frames "Laptop 1280 / Dashboard (chosen: B)" (12:30, same content as 33:98) and "Tablet 820 / Dashboard (B)" (14:82) (file `4POeO1dtcL5i2U5e0gdEoU`). Order: 1291, 1292, **1293 (this)**.

## 1. Objective

Finish the 768+ dashboard inside `div.dash-wide` (added by 1292, ends with the comment `{#- 1293: Today and This week go here -#}`): "Today" list, "This week" strip, the moved "Clear demo data", docs. Phone is untouched.

Out of scope: phone layout, other pages, door locks, invoices, admin, guest pages, the calendar page itself (`?cal_view=calendar`, `_dashboard_calendar.html` stay as they are and stay reachable).

## 2. Context and rules

AGENTS rules 6, 7, 9, 10; tokens only (`--tile-blue-*`, `--tile-done-*`, `--coral-red*`, `--warns/--warn`), no raw hex, no inline `style=`, 12 px between neighbours, no truncated labels, icons from `_icons.html` only, no new dependency/outbound request/personal-data field.

Verified facts:
- Data already in the dashboard context (`routes/admin.py` ~470-560): `today_rows` (rows with `reservation`, `progress`, `deadline_cell`, `nights`), `key_rows`, `next_arrival`, `cal_days` (14 days from today), `cal_rows` (one per property: `row.name`, `row.bars` with `col_start`, `col_end`, `css`, `title`; columns are 1-based over `cal_days`; check `_overview_calendar_rows` first), `apartments`, `demo_loaded`.
- Today rows in the old table (`dashboard.html`): stay label `reservation.summary if reservation.source == 'manual' and reservation.summary and reservation.summary.strip() else reservation.internal_name`; arriving test `(reservation.date_from | string)[:10] == today.isoformat()`; status badge `v2_status_pill(cell, progress, reservation)`; guests `progress.expected if progress.expected is not none else (progress.guests | length)`; i18n `dashboard.today.guests`, `dashboard.today.nights`, `dashboard.today.title`, `calendar.arrival`, `calendar.departure`, `dashboard.today.empty`, `dashboard.calendar.full` ("Full calendar →").
- Property colour: `property_identity(id, name, compact)` / `.ui-pdot[data-property]` (`App/app/templates/_components.html` line 301); `bar.css` carries the property colour class used by the old month grid.
- "Clear demo data": today `<form method="post" action="/demo/reset" ... data-confirm data-confirm-message="{{ t('confirm.clear_demo') }}">{{ ui_button(t('demo.clear'), 'quiet', type='submit') }}</form>` inside `.ov-links` of the phone header; "the existing overflow" = `row_menu_begin()` / `row_menu_end()` macros in `_components.html`.

## 3. Files

| Path | Action |
|---|---|
| `App/app/templates/dashboard.html` | fill the 1293 slot in `dash-wide` |
| `App/app/templates/_icons.html` | add `log-in` if 1292 did not |
| `App/app/static/app2.css` | block `/* 1293 dashboard */` appended; base.html `?v=` to `20261112-1293a` |
| `App/app/templates/base.html` | cache bump |
| `App/app/host_i18n.py`, `App/app/host_vi_i18n.py` | keys (step 1), en, cs, vi |
| `App/tests/test_host_new_dashboard_1292.py` | extend with 1293 cases (or `test_host_new_dashboard_1293.py` if the file is over 200 lines) |
| `docs/design/MASTER.md` section 2 | token values: page background cream, coral-red tokens (check what 1291 already added; do not duplicate) |
| `docs/design/pages/dashboard.md` | rewrite to the new layout (step 4, at most 40 lines) |
| `App/tests/test_1293_dashboard_today_week_geometry_browser.py` | new browser test (step 5); imports `App/tests/dash_geometry_support.py` made by 1291 (stop if missing) |

No other file. Anchor not found: STOP.

## 4. Steps

### Step 1: i18n (at most 3 calls)
After the `dashboard.empty.see_stays` keys 1292 added: `dashboard.today.leaving`: "Leaving" / "Odjezd" / "Trả phòng"; `dashboard.today.arriving`: "Arriving" / "Příjezd" / "Nhận phòng"; `dashboard.week.title`: "This week" / "Tento týden" / "Tuần này"; `dashboard.week.booked`: "Booked" / "Obsazeno" / "Đã đặt". Reuse `dashboard.today.guests` / `dashboard.today.nights`, `dashboard.today.title`, `dashboard.calendar.full`. Run `.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py -q --tb=short -x 2>&1 | tail -30`. Commit `1293 step 1`.

### Step 2: Today and This week markup (at most 7 calls)
In `dashboard.html`, replace the 1293 comment slot with (inside `dash-wide`, after the needs-you section):
1. **Today** `<section class="dash-today" data-dash-today aria-labelledby="dash-today-title"><h2 id="dash-today-title">{{ t('dashboard.today.title') }}</h2>`; `{% if today_rows %}<ul class="dash-rows">` and per row `<li><a class="dash-row" href="/reservations/{{ reservation.id }}?return_to=/" data-dash-stay="{{ reservation.id }}">` (the WHOLE row is the link; no nested links, buttons or menus inside) containing: `<span class="dash-ic {{ 'is-out' if not arriving else 'is-in' }}">{{ icon('log-out' if not arriving else 'log-in', 22) }}</span>` (leaving = blue tint, arriving = green tint), `<div class="dash-row-copy"><strong>{{ property_identity(reservation.apartment_id, stay_label, true) }}</strong><span>{{ t('dashboard.today.arriving') if arriving else t('dashboard.today.leaving') }} · {{ guests tp('dashboard.today.guests', n) }}{% if arriving %} · {{ tp('dashboard.today.nights', row.nights) }}{% endif %}</span></div>`, then `{{ v2_status_pill(cell, progress, reservation) }}` (exactly ONE status badge), then `{{ icon('chevron-right', 20) }}`. Empty: `<p class="dash-none">{{ t('dashboard.today.empty') }}</p>`. Do not reuse `data-stay-id` or `.dashboard-row` here (the old row JS keys on them).
2. **This week** `<section class="dash-week" data-dash-week aria-labelledby="dash-week-title"><div class="dash-week-head"><h2 id="dash-week-title">{{ t('dashboard.week.title') }}</h2><a class="dash-link" href="/?cal_view=calendar">{{ t('dashboard.calendar.full') }}</a></div>` then ONE white card `div.dash-grid`. Grid of 7 day columns from `cal_days[:7]`: header cells show weekday abbreviation plus day number in ONE string ("Thu 12", same `wd` list the old grid uses); the first (today) cell has class `is-today`. One row per entry in `cal_rows`: a property name cell (with `ui-pdot`), then one `<span class="dash-cell {{ bar.css }}" data-c="{{ n }}">` per day in view of each bar: `{% for n in range(bar.col_start, [bar.col_end, 8] | min) %}` (columns are 1-based over `cal_days`, `col_end` exclusive; Figma shows booked days as separate tinted cells with a 6 px gap, not one long pill); the label `t('dashboard.week.booked')` only in the first emitted cell of each stay (`loop.first`, also for a stay that began before today). Column placement: write seven rules `.dash-cell[data-c="N"]{grid-column:N+1}` (N = 1..7, literal numbers 2..8, because column 1 is the name) yourself; check `grep -n "data-c1" App/app/static/app2.css App/app/static/*.js | head -5` first and reuse the old technique if it already exists. Tint = the property colour tokens behind `bar.css` (teal `--tile-teal-bg/ink` or blue `--tile-blue-bg/ink` in Figma); if they are raw hex there, STOP and report which. Cells are display only, no links, no `title`, label never ellipsised. No second calendar markup.
3. **Clear demo data**: inside `dash-head` do not add anything. Put it in an overflow `row_menu_begin()` ... `row_menu_end()` at the right end of the This week head (after the "Full calendar" link), wrapping the same form, only `{% if demo_loaded %}`. Item markup is the existing `row-menu-form` pattern; keep `data-confirm` and the confirm message key.
4. Remove from the new layout only (the phone block is untouched): nothing else to delete, because the old month grid, `?`, month line and banner live in `dash-phone`; verify with `grep -c "ov-cal-block" App/app/templates/dashboard.html` (unchanged count) and that none of `ov-cal-block`, `ov-month`, `ui-how` appears inside `dash-wide`.
Commit `1293 step 2`.

### Step 3: CSS (at most 4 calls)
Block `/* 1293 dashboard */`, all `body.v2 .dash-wide` (Figma-verified, Figma wins over the first draft; WIDE = 1200 px and up, COMPACT = 768-1199, as in 1292). `.dash-today h2,.dash-week h2{font-size:22px;line-height:31px;font-weight:700;margin:0 0 16px}` (14 px below 1024). TODAY is ONE white card: `.dash-rows{list-style:none;margin:0;padding:0;background:var(--s);border:1px solid var(--line);border-radius:16px;overflow:hidden}`, rows separated by a 1px `--line` hairline (`.dash-rows li+li{border-top:1px solid var(--line)}`), not separate cards. `.dash-row{display:flex;align-items:center;gap:16px;padding:14px 20px 14px 16px;min-height:64px;color:var(--ink)}` (COMPACT: gap 14, padding 12px 16px 12px 14px); hover `--side2`; `:focus-visible` 2px `--coral-red` outline, offset -2. Icon tile 44x44 radius 12 with 22 px svg: `.is-out` `--tile-blue-bg/--tile-blue-ink`, `.is-in` `--tile-done-bg/--tile-done-ink`. Copy `flex:1;min-width:0;overflow-wrap:anywhere`: name 17/600 line-height 24 `--ink`, meta 15/400 line-height 21 `--ink2`, 2 px apart. Status badge 22 px high (existing pill); chevron 20 px `--ink3`; expected row height 75 (COMPACT 71) with one status badge; the badge stays on the row at 768 (the copy shrinks first). THIS WEEK: `.dash-week-head{display:flex;align-items:center;gap:12px}` with h2 `flex:1`; `.dash-link{color:var(--coral-red-deep);font-size:16px;font-weight:600;min-height:44px;display:inline-flex;align-items:center}` (Figma uses `--coral-red`; the deep tone keeps contrast >= 4.5). `.dash-grid{background:var(--s);border:1px solid var(--line);border-radius:16px;padding:8px 16px;display:grid;grid-template-columns:150px repeat(7,minmax(0,1fr));column-gap:6px;row-gap:0}` (COMPACT: first column 104px). Day header cells: height 36, radius 10, text centred 14/500 line-height 20 `--ink3`; `.is-today` background `--coral-red-soft`, text 14/700 `--coral-red-deep`; header row has 8 px vertical padding. Property rows: 6 px padding top and bottom around a 44 px cell (row 56). Name cell 15/600 line-height 21 `--ink`, 44 high, text may wrap to two lines (`overflow-wrap:anywhere`), never ellipsised (COMPACT names such as "Vinohrady Studio" wrap in 104 px). `.dash-cell`: height 44, radius 10, padding 0 10px, label 14/600 line-height 20 in the tile ink, `white-space:nowrap`. At 768 a day cell is about 70 px wide, so "Booked" (cs "Obsazeno", vi "Đã đặt") fits at 14 px with 10 px padding; if a test proves a label is cut after 2 tries, STOP and report. Changes versus the first draft: rows are one card with hairlines (was cards with 12 px gaps); icon tile 52 to 44, radius 14 to 12; chevron 22 to 20; name column 160 to 150 (120 to 104); column gap 4 to 6; pills 32 px high radius 999 replaced by 44 px high radius 10 per-day cells; day header 36 high. Bump `base.html` `?v=`. Commit `1293 step 3`.

### Step 4: tests and docs (at most 6 calls)
1. Tests (reuse the 1292 file/fixtures): Today row is one `<a>` with no nested `<a>`/`<button>`, has `Leaving` or `Arriving`, exactly one status badge, href `/reservations/<id>?return_to=/`; This week has 7 day headers, the `is-today` cell is first, `Full calendar` links to `/?cal_view=calendar`, one "Booked" label per stay in view; `dash-wide` contains none of `ov-cal-block`, `ov-month`, `ui-how`; demo reset form only when `demo_loaded`; the browser checks live in step 5.
2. Docs: `docs/design/MASTER.md` section 2: make sure the semantic token list shows `--page-cream #faf6f0`, `--coral-red*`, `--tile-*`, `--danger*` and the rule "coral is a signal only"; `docs/design/pages/dashboard.md`: replace the desktop part with the new order (header, tiles, What needs you, Today, This week), the pixel values from 1292/1293 (30/28 px title, 48 px pill, 52 px icon tiles, 18/600 titles, gutters 40/28, section gap 32), the rule that tiles are display-only, and one line that phone keeps the Today/Upcoming layout. Do not touch status, decisions, known-issues.
3. Run section 5. Commit `1293 step 4`.

### Step 5: geometry and design tests (at most 6 calls)
1. Read `App/tests/dash_geometry_support.py` (from 1291: `WIDTHS`, `open_page`, `rect`, `css`, `near`, `contrast_failures`, `clipped_texts`, `small_targets`, `overlap`, `big_coral`, `focus_outline`, `shot`) and `App/tests/test_dashboard_rows_browser.py` lines 1-100 (fixtures `calendar_workspace`, `calendar_origin`, `launch`, `make_stay`, `seed(ws)`). Seed stays that leave today, arrive today and span the week for two properties.
2. Create `App/tests/test_1293_dashboard_today_week_geometry_browser.py` (module `REQUIRE_BROWSER` block as in the rows test), `@pytest.mark.parametrize("width", WIDTHS)` over `/` with demo data. Assert (±1 px):
   - 1440, 1280, 1024, 820, 768: no horizontal scroll; `.dash-title`, `.dash-tiles`, `.dash-needs`, `.dash-today`, `.dash-week` share one left x and one right x (the 1292 blocks stay unchanged); `contrast_failures`, `clipped_texts`, `small_targets`, `big_coral` empty for `.dash-today` and `.dash-week`; `focus_outline` >= 2 px on the first `.dash-row` and on `.dash-link`; demo-data overflow trigger >= 44x44.
   - Today: `.dash-rows` background white, border 1px rgb(235,235,231), radius 16; rows 75 high (COMPACT 71; never under 64), hairline 1 px between rows, no gap between rows; icon tile 44x44 radius 12 with 22 px svg (leaving rgb(232,240,251), arriving rgb(230,245,236)); name 17/600, meta 15/400 rgb(85,85,79), 2 px apart; chevron 20x20; exactly one badge, 22 high; row = one `a` with no nested `a` or `button`; copy and badge do not `overlap`; padding 16 left and 20 right (COMPACT 14 and 16).
   - This week: `.dash-grid` radius 16, 1px border, padding 8 16; name column 150 (COMPACT 104); 7 day header cells equal width (104.9 at 1280, 73.4 at 820), 36 high, radius 10, column gap 6; the first header cell is `is-today` with bg rgb(253,236,232), 14/700 rgb(184,61,40), the others 14/500 rgb(107,107,101); property row cells 44 high, radius 10, row 56 (a wrapped name may grow it); cell label 14/600; each stay shows exactly one label; cells stay inside `.dash-grid`; name cell 15/600; "Full calendar" link 16/600, >= 44 high, href `/?cal_view=calendar`.
   - 390 and 320: `.dash-wide` `display:none`, phone layout and tab bar visible, no horizontal scroll.
3. Content states in the same file: (a) no today rows: `.dash-none` shows, no overflow; (b) a property named with 45 or more characters: Today title and week name wrap, nothing clipped, no overlap with the badge or the first cell, no horizontal scroll at 1280, 820; (c) lang cs and vi at 1280 and 820: labels "Obsazeno", "Đã đặt", "Odjezd", "Příjezd" not clipped; (d) demo data present: the overflow menu holds "Clear demo data" and keeps `data-confirm`.
4. Run `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_1293_dashboard_today_week_geometry_browser.py -q --tb=short -x -rs 2>&1 | tail -30` (0 skipped). Fix CSS, never the numbers. A Figma number that needs a file outside section 3: stop and report.
5. `shot()` 390, 768, 820, 1280 of `/` with demo data; open each PNG with the Read tool and write one sentence per shot in the report (AGENTS rule 10). Commit `1293 step 5`.

## 5. Do not touch

- The phone layout (`dash-phone` markup and `ph-*` rules), the sidebar (1291) and the header, tiles and needs-you cards (1292).
- Calendar page logic and `dashboard-calendar.js` behaviour beyond the refresh guard named in section 4.
- Migrations, SQL, any new dependency or outbound request, guest pages, admin.
- Anything not listed in section 3 Files.

## 6. Commands (from `App/`, each ends `| tail -30`)

```
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_1293_dashboard_today_week_geometry_browser.py -q --tb=short -x -rs 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_host_new_dashboard_1292.py tests/test_dashboard_*.py tests/test_0520_overview_today.py tests/test_host_quiet_dashboard*.py tests/test_dashboard_calendar_browser.py -q --tb=short -x -rs 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py tests/test_0710_v2_mockup_match_browser.py tests/test_0729_phone_today_geometry_browser.py -q --tb=short -x -rs 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py tests/test_design_*.py tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py -q --tb=short -x 2>&1 | tail -30
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x -rs 2>&1 | tail -30
python3 scripts/context_lint.py 2>&1 | tail -30
```
(last line from the repo root). Rows used (test-map): host pages/CSS/templates, calendar, copy and translations, static files, design system, v2 pages. 0 skipped on browser files. No full suite.

## 7. Acceptance

- `test_1293_dashboard_today_week_geometry_browser.py` green with 0 skipped at 1440, 1280, 1024, 820, 768, 390, 320 (pixel values in step 3, contrast >= 4.5, targets >= 44, focus ring >= 2 px, no clipped text, shared left and right edges with the 1292 blocks). At 1280 and 820: Today as one white card of rows (icon tile blue = leaving, green = arriving; property; "Leaving · 2 guests" / "Arriving · 3 guests · 1 night"; one status badge; chevron; whole row is the link); This week card (7 columns, today coral-soft, one row per property, tinted per-day cells with one "Booked" label per stay, "Full calendar" link works); Clear demo data only in the overflow; no month calendar block, no `?`, no month line in the new layout; calm state from 1292 still shown.
- Phone unchanged; calendar page (`/?cal_view=calendar`) unchanged.
- UX gate (AGENTS rule 10, you do it, never ask the owner): `test_layout_lint_browser.py` green, open the 390/768/1280 shots of `/` (with demo data), write per page what you saw in the PR, tick the [design-system checklist](../design/design-system.md), never silence a finding.
- Section 5 green, 0 skipped; context lint green.

## 8. Stop and ask

Stop and report if: 1292 is not in the base; `cal_rows` bars carry raw hex colours or no column data; the week grid cannot fit at 768 without cutting a label after 2 tries; JS in `dashboard-calendar.js` rewires `.dashboard-row` or `data-stay-id` in a way that touches the new block; a Figma number cannot be met without changing a file outside section 3: stop and report; more than 25 tool calls (30 hard cap).

## 9. Report (branch, PR and what to report)

Branch `task/1293-dashboard-redesign-c`, one **draft** PR (stacked on 1292), never push to `main`; merge only with `scripts/merge-pr-on-green.sh` (owner step: merge 1291, 1292, 1293 in order; green merges auto-deploy; the redesign ships complete only after 1293). Report `docs/tasks/1293-report.md` (600 tokens at most): files changed, commands with last 5 lines, section 6 ticked, per-page screenshot notes, Deviations (`Done: steps 1 to k. Left: steps k+1 to 4.`), Questions, owner steps.

## Orchestrator end-of-session (not the executor)

After the review of all three reports, the orchestrator: appends to `docs/context/decisions.md`: `[design] 2026-11-12: host dashboard redesign (Figma 4POeO1dtcL5i2U5e0gdEoU, laptop B and tablet B): cream page background #faf6f0, coral-red tokens (#d0452d / #b83d28 / #fdece8, signal only), new sidebar (no account box, no Smart locks or Invoices in the sidebar, both in the account menu), tablet 768-1023 icon rail replaces the bottom tab bar, new icons brush-cleaning, coins, wallet, nav label "Dashboard" stays. Briefs 1291-1293.`; adds a status line (5 lines at most); records any known issue; runs `python3 scripts/context_lint.py`; and, per `workflow.md`, notes it as `[workflow]` only if the workflow changed (it did not).
