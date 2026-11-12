# 1134: host dashboard redesign, part C of 3: Today list, This week strip, cleanup and docs (laptop and tablet)

Status: todo
Depends on: 1133 (merged, or stacked on `task/1133-dashboard-redesign-b`) | Base commit: origin/main | Branch: task/1134-dashboard-redesign-c
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (4 steps of at most 6 calls)
Brief by Sonnet 5.5, 2026-11-12. Owner Josef approved Figma frames "Laptop 1280 / Dashboard (chosen: B)" and "Tablet 820 / Dashboard (B)" (file `4POeO1dtcL5i2U5e0gdEoU`). Order: 1132, 1133, **1134 (this)**.

## 1. Objective

Finish the 768+ dashboard inside `div.dash-wide` (added by 1133, ends with the comment `{#- 1134: Today and This week go here -#}`): "Today" list, "This week" strip, the moved "Clear demo data", docs. Phone is untouched.

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
| `App/app/templates/dashboard.html` | fill the 1134 slot in `dash-wide` |
| `App/app/templates/_icons.html` | add `log-in` if 1133 did not |
| `App/app/static/app2.css` | block `/* 1134 dashboard */` appended; base.html `?v=` to `20261112-1134a` |
| `App/app/templates/base.html` | cache bump |
| `App/app/host_i18n.py`, `App/app/host_vi_i18n.py` | keys (step 1), en, cs, vi |
| `App/tests/test_host_new_dashboard_1133.py` | extend with 1134 cases (or `test_host_new_dashboard_1134.py` if the file is over 200 lines) |
| `docs/design/MASTER.md` section 2 | token values: page background cream, coral-red tokens (check what 1132 already added; do not duplicate) |
| `docs/design/pages/dashboard.md` | rewrite to the new layout (step 4, at most 40 lines) |

No other file. Anchor not found: STOP.

## 4. Steps

### Step 1: i18n (at most 3 calls)
After the `dashboard.empty.see_stays` keys 1133 added: `dashboard.today.leaving`: "Leaving" / "Odjezd" / "Trả phòng"; `dashboard.today.arriving`: "Arriving" / "Příjezd" / "Nhận phòng"; `dashboard.week.title`: "This week" / "Tento týden" / "Tuần này"; `dashboard.week.booked`: "Booked" / "Obsazeno" / "Đã đặt". Reuse `dashboard.today.guests` / `dashboard.today.nights`, `dashboard.today.title`, `dashboard.calendar.full`. Run `.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py -q --tb=short -x 2>&1 | tail -30`. Commit `1134 step 1`.

### Step 2: Today and This week markup (at most 7 calls)
In `dashboard.html`, replace the 1134 comment slot with (inside `dash-wide`, after the needs-you section):
1. **Today** `<section class="dash-today" data-dash-today aria-labelledby="dash-today-title"><h2 id="dash-today-title">{{ t('dashboard.today.title') }}</h2>`; `{% if today_rows %}<ul class="dash-rows">` and per row `<li><a class="dash-row" href="/reservations/{{ reservation.id }}?return_to=/" data-dash-stay="{{ reservation.id }}">` (the WHOLE row is the link; no nested links, buttons or menus inside) containing: `<span class="dash-ic {{ 'is-out' if not arriving else 'is-in' }}">{{ icon('log-out' if not arriving else 'log-in', 24) }}</span>` (leaving = blue tint, arriving = green tint), `<div class="dash-row-copy"><strong>{{ property_identity(reservation.apartment_id, stay_label, true) }}</strong><span>{{ t('dashboard.today.arriving') if arriving else t('dashboard.today.leaving') }} · {{ guests tp('dashboard.today.guests', n) }}{% if arriving %} · {{ tp('dashboard.today.nights', row.nights) }}{% endif %}</span></div>`, then `{{ v2_status_pill(cell, progress, reservation) }}` (exactly ONE status badge), then `{{ icon('chevron-right', 22) }}`. Empty: `<p class="dash-none">{{ t('dashboard.today.empty') }}</p>`. Do not reuse `data-stay-id` or `.dashboard-row` here (the old row JS keys on them).
2. **This week** `<section class="dash-week" data-dash-week aria-labelledby="dash-week-title"><div class="dash-week-head"><h2 id="dash-week-title">{{ t('dashboard.week.title') }}</h2><a class="dash-link" href="/?cal_view=calendar">{{ t('dashboard.calendar.full') }}</a></div>`. Grid of 7 day columns from `cal_days[:7]` (header cells: weekday abbreviation using the same `wd` list the old grid uses, plus day number; the first (today) cell has class `is-today` = `--coral-red-soft` background). One row per entry in `cal_rows`: property name cell (with `ui-pdot`), then the bars clipped to columns 1-7: for each bar with `col_start <= 7`, `<span class="dash-pill {{ bar.css }}" data-c1="{{ bar.col_start }}" data-c2="{{ [bar.col_end, 8] | min }}">`. Use the same attribute-to-column technique the old `.cgrid .bar` uses (read `grep -n "data-c1" App/app/static/app2.css App/app/static/*.js | head -5` first; if CSS needs one rule per column index, write the seven rules `[data-c1="N"]{grid-column-start:N}` and `[data-c2="N"]{grid-column-end:N}` yourself with `grid-column` spans via the gap). The pill label is `t('dashboard.week.booked')` in the first cell of the stay only (a pill that starts before today still shows the label), soft tinted background in the property colour (reuse the colour tokens behind `bar.css`; if they are raw hex there, STOP and report which). No `title` text clipped: the pill is at least 28 px high; labels never ellipsised ("Booked" is short). Do not link pills (display only). No second calendar markup.
3. **Clear demo data**: inside `dash-head` do not add anything. Put it in an overflow `row_menu_begin()` ... `row_menu_end()` at the right end of the This week head (after the "Full calendar" link), wrapping the same form, only `{% if demo_loaded %}`. Item markup is the existing `row-menu-form` pattern; keep `data-confirm` and the confirm message key.
4. Remove from the new layout only (the phone block is untouched): nothing else to delete, because the old month grid, `?`, month line and banner live in `dash-phone`; verify with `grep -c "ov-cal-block" App/app/templates/dashboard.html` (unchanged count) and that none of `ov-cal-block`, `ov-month`, `ui-how` appears inside `dash-wide`.
Commit `1134 step 2`.

### Step 3: CSS (at most 4 calls)
Block `/* 1134 dashboard */`, all `body.v2 .dash-wide`: `.dash-today h2,.dash-week h2{font-size:22px;font-weight:700;margin:0 0 16px}`. `.dash-rows{list-style:none;padding:0;display:grid;gap:12px}`; `.dash-row`: white, 1px `--line`, radius 16, padding 16 20, `display:flex;align-items:center;gap:16px;min-height:72px;color:var(--ink)`; hover `--side2`; `:focus-visible` 2px `--coral-red`; copy: name 18/600, meta 14 `--ink2`; icon tile 52x52 radius 14, `.is-out` `--tile-blue-bg/--tile-blue-ink`, `.is-in` `--tile-done-bg/--tile-done-ink`; chevron `--ink3`. At 768-1023 the status pill may wrap under the copy (`flex-wrap:wrap`); nothing cut. `.dash-week`: white card, radius 16, padding 20, border 1px `--line`; grid `grid-template-columns:160px repeat(7,minmax(0,1fr))` (tablet `120px`), column gap 4, row gap 8, min row height 44; weekday head 14/600 `--ink2`; `.is-today` coral-soft with radius 8; `.dash-pill`: radius 999, height 32, padding 0 12, 14/600, tinted, `grid-column` from data attributes, label `white-space:nowrap`. `.dash-link{color:var(--coral-red-deep);font-size:16px;font-weight:600;min-height:44px;display:inline-flex;align-items:center}`; `.dash-week-head{display:flex;justify-content:space-between;align-items:center;gap:12px}`. If 7 columns plus the name column are too tight at 768 (names or "Booked" cut): make the name cell sit above its row (full width), do not truncate. Bump `base.html` `?v=`. Commit `1134 step 3`.

### Step 4: tests and docs (at most 8 calls)
1. Tests (reuse the 1133 file/fixtures): Today row is one `<a>` with no nested `<a>`/`<button>`, has `Leaving` or `Arriving`, exactly one status badge, href `/reservations/<id>?return_to=/`; This week has 7 day headers, the `is-today` cell is first, `Full calendar` links to `/?cal_view=calendar`, 1 pill per stay in view; `dash-wide` contains none of `ov-cal-block`, `ov-month`, `ui-how`; demo reset form only when `demo_loaded`; browser at 1280 and 820 (0 skipped): no horizontal scroll, `.dash-pill` and day cells inside `.dash-week` bounds, all `.dash-row` heights >= 64, no element in `dash-wide` with `scrollWidth > clientWidth` (no cut text); at 390 `dash-wide` hidden.
2. Docs: `docs/design/MASTER.md` section 2: make sure the semantic token list shows `--page-cream #faf6f0`, `--coral-red*`, `--tile-*`, `--danger*` and the rule "coral is a signal only"; `docs/design/pages/dashboard.md`: replace the desktop part with the new order (header, tiles, What needs you, Today, This week), the pixel values from 1133/1134 (30/28 px title, 48 px pill, 52 px icon tiles, 18/600 titles, gutters 40/28, section gap 32), the rule that tiles are display-only, and one line that phone keeps the Today/Upcoming layout. Do not touch status, decisions, known-issues.
3. Run section 5. Commit `1134 step 4`.

## 5. Do not touch

- The phone layout (`dash-phone` markup and `ph-*` rules), the sidebar (1132) and the header, tiles and needs-you cards (1133).
- Calendar page logic and `dashboard-calendar.js` behaviour beyond the refresh guard named in section 4.
- Migrations, SQL, any new dependency or outbound request, guest pages, admin.
- Anything not listed in section 3 Files.

## 6. Commands (from `App/`, each ends `| tail -30`)

```
.venv/bin/python -m pytest tests/test_host_new_dashboard_1133.py tests/test_dashboard_*.py tests/test_0520_overview_today.py tests/test_host_quiet_dashboard*.py tests/test_dashboard_calendar_browser.py -q --tb=short -x -rs 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py tests/test_0710_v2_mockup_match_browser.py tests/test_0729_phone_today_geometry_browser.py -q --tb=short -x -rs 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py tests/test_design_*.py tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py -q --tb=short -x 2>&1 | tail -30
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x -rs 2>&1 | tail -30
python3 scripts/context_lint.py 2>&1 | tail -30
```
(last line from the repo root). Rows used (test-map): host pages/CSS/templates, calendar, copy and translations, static files, design system, v2 pages. 0 skipped on browser files. No full suite.

## 7. Acceptance

- At 1280 and 820: Today rows (icon tile blue = leaving, green = arriving; property; "Leaving · 2 guests" / "Arriving · 3 guests · 1 night"; one status badge; chevron; whole row is the link); This week strip (7 columns, today coral-soft, one row per property, tinted "Booked" pills, "Full calendar" link works); Clear demo data only in the overflow; no month calendar block, no `?`, no month line in the new layout; calm state from 1133 still shown.
- Phone unchanged; calendar page (`/?cal_view=calendar`) unchanged.
- UX gate (AGENTS rule 10, you do it, never ask the owner): `test_layout_lint_browser.py` green, open the 390/768/1280 shots of `/` (with demo data), write per page what you saw in the PR, tick the [design-system checklist](../design/design-system.md), never silence a finding.
- Section 5 green, 0 skipped; context lint green.

## 8. Stop and ask

Stop and report if: 1133 is not in the base; `cal_rows` bars carry raw hex colours or no column data; the week grid cannot fit at 768 without cutting a label after 2 tries; JS in `dashboard-calendar.js` rewires `.dashboard-row` or `data-stay-id` in a way that touches the new block; more than 25 tool calls.

## 9. Report (branch, PR and what to report)

Branch `task/1134-dashboard-redesign-c`, one **draft** PR (stacked on 1133), never push to `main`; merge only with `scripts/merge-pr-on-green.sh` (owner step: merge 1132, 1133, 1134 in order; green merges auto-deploy; the redesign ships complete only after 1134). Report `docs/tasks/1134-report.md` (600 tokens at most): files changed, commands with last 5 lines, section 6 ticked, per-page screenshot notes, Deviations (`Done: steps 1 to k. Left: steps k+1 to 4.`), Questions, owner steps.

## Orchestrator end-of-session (not the executor)

After the review of all three reports, the orchestrator: appends to `docs/context/decisions.md`: `[design] 2026-11-12: host dashboard redesign (Figma 4POeO1dtcL5i2U5e0gdEoU, laptop B and tablet B): cream page background #faf6f0, coral-red tokens (#d0452d / #b83d28 / #fdece8, signal only), new sidebar (no account box, no Smart locks or Invoices in the sidebar, both in the account menu), tablet 768-1023 icon rail replaces the bottom tab bar, new icons brush-cleaning, coins, wallet, nav label "Dashboard" stays. Briefs 1132-1134.`; adds a status line (5 lines at most); records any known issue; runs `python3 scripts/context_lint.py`; and, per `workflow.md`, notes it as `[workflow]` only if the workflow changed (it did not).
