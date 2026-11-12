# 1133: host dashboard redesign, part B of 3: greeting header, month tiles, "What needs you" cards (laptop and tablet)

Status: todo
Depends on: 1132 (merged, or this branch stacked on `task/1132-dashboard-redesign-a`) | Base commit: origin/main | Branch: task/1133-dashboard-redesign-b
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (4 steps of at most 6 calls)
Brief by Sonnet 5.5, 2026-11-12. Owner Josef approved the Figma frames "Laptop 1280 / Dashboard (chosen: B)" and "Tablet 820 / Dashboard (B)" (file `4POeO1dtcL5i2U5e0gdEoU`). Order: 1132, **1133 (this)**, 1134. Both 1133 and 1134 touch `dashboard.html` and `app2.css`: 1134's anchors are written for the file as this brief leaves it.

## 1. Objective

At 768 px and wider, `/` shows a new one-lane page: header (greeting, date, one primary "Add stay" pill), three month tiles, "What needs you" cards. 1134 adds Today and This week. Phone (below 768 px) keeps today's markup and look, untouched. Goals: simple, intuitive, not overwhelming, easy for old people, children and first-time visitors.

Out of scope: phone layout, other pages, door locks, invoices, admin, guest pages, the logic that builds the needs-you lines (`App/app/needs_you.py`, only read its output).

## 2. Context and rules

AGENTS rules 6, 7, 9 (one explanation in one place; write "no tracking cookies", never "no cookies"), 10; tokens only (1132 added `--coral-red*`, `--tile-*`, `--page-cream`, `--danger*`), no raw hex, no inline `style=`; 12 px minimum between neighbours; no truncated labels; SQL only through `App/app/db.py` helpers; no new dependency, outbound request or personal-data field; icons only from `_icons.html`.

Verified facts:
- Route: `dashboard()` in `App/app/routes/admin.py` line 470; context dict near lines 535-560 has `"month_summary": reporting.month_summary(owner_user_id, today)`, `rows`, `missing_report_rows`, `apartments`, `today`, `cal_view`, `demo_loaded`.
- `reporting.month_summary` (`App/app/reporting.py` line 1016) runs ONE query over stays overlapping the month and returns `{"guests","nights","reported"}`. Callers: `dashboard.html` line 89 and `routes/admin.py` lines 552 and 5272 (the latter a different `"month"` key, keep it working).
- `dashboard.html` (154 lines): the whole non-empty branch is `{% else %}` at line 36 to `{% endif %}` at line 153. Phone and desktop share markup via `ph-only` / `ph-hide` classes, and CSS applies phone rules up to 1023 px (`@media (max-width:1023px){body.v2 .ph-hide{display:none !important}}`, app2.css ~914). So the new layout cannot reuse that markup: add a separate block.
- Needs-you data: `needs_you = needs_you_build(rows, needs_you_queue, open_alerts, missing_report_rows, lang, today)`; `ny_lines` items have `kind` ("stay", ...), `tone` ("red"/"amber"), `subject` (stay name and dates), `text`, `action` (label, e.g. "Open the stay", "Review and send", "Send the guest link"), `href`, `stay_id`, `apartment_id`, `dismiss_id`. Existing macro `ny_row` renders them (keep it for the phone).
- Property colour dot: `property_identity(id, name, compact)` in `_components.html` line 301 (`.ui-pdot[data-property]`).
- `dashboard-calendar.js` line 970 replaces `[data-dashboard-refresh="stats"|"work"]` nodes after refresh; the new block must not reuse those attribute values (use `data-dash-*`).
- i18n: `App/app/host_i18n.py` (en and cs blocks) and `App/app/host_vi_i18n.py` (vi). Existing keys to reuse: `needs_you.title`, `needs_you.more` / `.one` ("Show %(count)s more"), `stays.add_stay`, `dashboard.month.guests*`, `needs_you.action.*`.

## 3. Files

| Path | Action |
|---|---|
| `App/app/reporting.py` | `month_summary`: add `stays` (count of rows from the same query) |
| `App/app/routes/admin.py` | context: `greeting_part`, `first_name` inputs, tile numbers (step 1) |
| `App/app/templates/dashboard.html` | wrap phone markup in `div.dash-phone`, add `div.dash-wide` with header, tiles, needs-you |
| `App/app/templates/_icons.html` | add icons the tiles/cards need if missing: `log-out`, `log-in`, `shield-check`, `calendar-days`, `triangle-alert`, `send`, `users` (copy exact paths from `npm pack lucide-static@0.552.0` in the scratchpad dir) |
| `App/app/static/app2.css` | new `/* 1133 dashboard */` block at the end; show/hide split at 768 px |
| `App/app/templates/base.html` | bump `app2.css?v=` to `20261112-1133a` |
| `App/app/host_i18n.py`, `App/app/host_vi_i18n.py` | new keys (step 2), en, cs, vi |
| `App/tests/test_host_new_dashboard_1133.py` | new test file (step 4) |
| `App/tests/test_0520_overview_today.py`, `test_host_quiet_dashboard*.py`, `test_dashboard_queue*.py`, `test_needs_you_dashboard_0241.py` | adjust only assertions broken by the wrapper split; never weaken |

No other file. An anchor not found: STOP.

## 4. Steps

### Step 1: data (at most 6 calls)
1. `reporting.month_summary`: after the loop's `guests = nights = reported = 0` add `stays = len(rows)` and return `{"guests": guests, "nights": nights, "reported": reported, "stays": len(rows)}` (rows already holds the stays that overlap the month; no new query). Update the docstring in one line.
2. Route context (`routes/admin.py`, next to `"month_summary"`): add `"greeting_part"`: `"morning"` for local hour < 12, `"afternoon"` < 18, else `"evening"`. Find the project's local-time helper with `grep -n "ZoneInfo\|Europe/Prague\|local_now" App/app/routes/admin.py App/app/config.py App/app/templating.py | head`; none exists: STOP and ask. Add `"stays_missing"`: `len(missing_report_rows)` (stays with missing police details; already computed) and `"reports_late"`: count of `needs_you.lines` is not available in the route, so compute it in the template instead (`ny_lines | selectattr('tone','equalto','red') | selectattr('kind','equalto','stay') | list | length`). Keep the tile numbers `reported` and `guests` from `month_summary`; "properties" for the first tile sub = `apartments | length`.
3. Run `.venv/bin/python -m pytest tests/test_0520_overview_today.py tests/test_host_quiet_dashboard.py -q --tb=short -x 2>&1 | tail -30`. Commit `1133 step 1`.

### Step 2: i18n keys (at most 4 calls)
Add after the `dashboard.calendar.full` key in each language block (grep `"dashboard.calendar.full"` to find en, cs and vi). Keys and values (en / cs / vi), plural forms follow how `needs_you.more` / `.one` are done (look at it, copy the pattern):
- `dashboard.greet.morning`: "Good morning, %(name)s" / "Dobré ráno, %(name)s" / "Chào buổi sáng, %(name)s"; `.afternoon`: "Good afternoon, %(name)s" / "Dobré odpoledne, %(name)s" / "Chào buổi chiều, %(name)s"; `.evening`: "Good evening, %(name)s" / "Dobrý večer, %(name)s" / "Chào buổi tối, %(name)s".
- `dashboard.tile.stays`: "stays this month" / "pobytů tento měsíc" / "lượt lưu trú tháng này"; sub `dashboard.tile.properties`: "%(count)s properties" (+ `.one` "1 property") / "%(count)s ubytování" / "%(count)s cơ sở lưu trú".
- `dashboard.tile.guests`: "guests registered" / "ubytovaných hostů" / "khách đã đăng ký"; subs `dashboard.tile.guests_ok`: "all details complete" / "všechny údaje vyplněny" / "đã đủ thông tin"; `dashboard.tile.guests_missing`: "%(count)s still missing" / "%(count)s ještě chybí" / "còn thiếu %(count)s".
- `dashboard.tile.reported`: "of %(total)s reported to the police" / "z %(total)s nahlášeno policii" / "trên %(total)s đã báo cho cảnh sát" (number shown before it); subs `dashboard.tile.reported_ok`: "all on time" / "vše včas" / "đúng hạn"; `dashboard.tile.reported_late`: "%(count)s late" / "%(count)s po termínu" / "%(count)s trễ hạn".
- `dashboard.empty.calm`: "Nothing needs you today" / "Dnes na vás nic nečeká" / "Hôm nay không có gì cần bạn xử lý"; `dashboard.empty.next_arrival`: "Next arrival: %(date)s" / "Další příjezd: %(date)s" / "Khách đến tiếp theo: %(date)s"; `dashboard.empty.see_stays`: "See all stays" / "Zobrazit všechny pobyty" / "Xem tất cả lưu trú".
No new copy beyond this (rule 9: no helper sentences). Run `.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py -q --tb=short -x 2>&1 | tail -30`. Commit `1133 step 2`.

### Step 3: template and CSS (at most 8 calls)
1. In `dashboard.html`, inside the `{% else %}` branch (line 36), compute once at its top (after `ny_lines`): `{% set shown_name = (workspace_user.display_name or workspace_user.username).split(' ')[0] %}` and `{% set late_n = ny_lines | selectattr('tone','equalto','red') | selectattr('kind','equalto','stay') | list | length %}`. Wrap everything from `<div class="ph-top ...` to the end of that branch in `<div class="dash-phone">...</div>`, unchanged inside. Then add BEFORE it `<div class="dash-wide" data-dash-wide>` containing, in order:
 - Env line: `{% if ubyport_env != 'prod' %}<p class="dash-env" role="status">{{ t('env.where_reports_go') }}</p>{% endif %}` (one slim line above the greeting; if the existing `_env_banner.html` already renders MOCK on this page, leave that include as is and add nothing; check with `grep -n "env_banner" App/app/templates/host_page.html App/app/templates/base.html | head -3`).
 - Header `<header class="dash-head"><div><h1 class="dash-title">{{ t('dashboard.greet.' ~ greeting_part, name=shown_name) }}</h1><p class="dash-date">{{ today.isoformat() | date_long(lang) }}</p></div><a class="dash-add" href="/reservations?new=1" data-calendar-add data-cal-create-type="stay">{{ icon('plus', 22) }}{{ t('stays.add_stay') }}</a></header>`. This h1 is the page's only visible h1 at 768+. No help `?`.
 - Tiles `<ul class="dash-tiles" data-dash-tiles>` with 3 `<li class="dash-tile">`, display-only (no links, no buttons): blue (`calendar-days`, `month_summary.stays`, `dashboard.tile.stays`, sub `tp('dashboard.tile.properties', apartments|length)`), teal (`users`, `month_summary.guests`, sub `guests_ok` when `stays_missing == 0` else `guests_missing` with count), reported (`shield-check`, number `month_summary.reported`, text `dashboard.tile.reported` with total = `month_summary.guests`, class `is-done` when `reported == guests` and `late_n == 0` else `is-warn`; sub `reported_ok` or `reported_late` with `late_n`). Hide the whole tiles list when `month_summary` is falsy.
 - Needs-you `<section class="dash-needs" aria-labelledby="dash-needs-title"><h2 id="dash-needs-title">{{ t('needs_you.title') }}{% if ny_lines %}<span class="dash-count">{{ ny_lines|length }}</span>{% endif %}</h2>`; when `ny_lines`: `<ul class="dash-cards">`, for the first 4 lines a macro `dash_card(line, first)`: `<li class="dash-card" data-tone="{{ line.tone }}" data-dash-need="{{ line.kind }}"{% if line.stay_id %} data-dash-need-stay="{{ line.stay_id }}"{% endif %}><span class="dash-ic is-red|is-amber">` (red tone: `is-red`, otherwise `is-amber`) holding `{{ icon(NAME, 26) }}`; NAME rule: red tone `triangle-alert`; amber tone `send` when `line.action == t('needs_you.action.send')`, `users` when it is `t('needs_you.action.send_link')`, else `send`. Then `<div class="dash-card-copy"><strong>{{ line.text or line.subject }}</strong><span>{{ property dot via property_identity(line.apartment_id, line.subject, true) if line.apartment_id else line.subject }}</span></div>` and, if `line.href`, `<a class="dash-btn{{ ' is-primary' if first }}" href="{{ line.href }}" data-needs-you-go>{{ line.action }}</a>`. Dismiss form only if `line.dismiss_id` (copy the existing form from `ny_row`, small ghost `×`). Beyond 4: `<details class="dash-more"><summary>{{ tp('needs_you.more', ny_lines|length - 4) }}</summary><ul class="dash-cards">...rest...</ul></details>`.
 - Empty (no `ny_lines`): `<div class="dash-calm">{{ icon('check', 26) }}<strong>{{ t('dashboard.empty.calm') }}</strong>{% if next_arrival %}<span>{{ t('dashboard.empty.next_arrival', date=next_arrival.reservation.date_from | date_long(lang)) }}</span>{% endif %}<a class="dash-btn" href="/reservations">{{ t('dashboard.empty.see_stays') }}</a></div>`.
 Leave a comment `{#- 1134: Today and This week go here -#}` right before `</div>` closing `dash-wide`.
2. CSS block `/* 1133 dashboard */` (all `body.v2`): `.dash-phone{display:block}.dash-wide{display:none}` and `@media (min-width:768px){.dash-phone{display:none}.dash-wide{display:block}}`. Laptop (1024+): `.dash-wide{padding:0 40px}`; tablet 768-1023: padding `0 28px`. Section gap 32 px (`.dash-wide>*+*{margin-top:32px}`). `.dash-head{display:flex;align-items:flex-start;justify-content:space-between;gap:24px}`; `.dash-title{font-size:30px;font-weight:700;margin:0}` (28 px at tablet); `.dash-date{color:var(--ink2);font-size:16px;margin:4px 0 0}`; `.dash-add{display:inline-flex;align-items:center;gap:8px;height:48px;padding:0 24px;border-radius:999px;background:var(--coral-red);color:#fff;font-size:16px;font-weight:600}` (use `var(--on-brand)` for the text, not hex). `.dash-tiles{list-style:none;display:grid;grid-template-columns:repeat(3,1fr);gap:16px;padding:0}`; `.dash-tile`: white, 1px `--line`, radius 16, padding 20; icon tile 48 px circle-radius 12 tinted: blue `--tile-blue-bg/--tile-blue-ink`, teal `--tile-teal-*`, reported `is-done` `--tile-done-*` or `is-warn` `--warns/--warn`; number 30/700, label 16/500, sub 14 `--ink2`; at tablet the icon sits above the text (stacked). `.dash-needs h2{font-size:22px;font-weight:700;display:flex;align-items:center;gap:12px}`; `.dash-count`: pill `--coral-red-soft` bg, `--coral-red-deep` text, 14/700, min 28 px. `.dash-cards{list-style:none;padding:0;display:grid;gap:12px}`; `.dash-card`: white, 1px `--line`, radius 16, padding 16 20, `display:flex;align-items:center;gap:16px`; `.dash-ic` 52x52 radius 14: `.is-red` bg `--danger-bg` ink `--danger`; `.is-amber` bg `--warns` ink `--warn`. Title 18/600; meta 14 `--ink2` with the property dot. `.dash-btn`: height 48, radius 999, padding 0 24, border 1px `--line`, white, ink, 16/600, `white-space:nowrap`; `.dash-btn.is-primary` coral-red bg, `--on-brand` text. Below 1024 px the card wraps: button on its own full-width row under the copy (`flex-wrap:wrap`, button `width:100%`). Focus: `:focus-visible` 2px `--coral-red` outline. Bump `base.html` `?v=`.
3. Run once: `.venv/bin/python -m pytest tests/test_dashboard_phone_browser.py tests/test_0729_phone_today_geometry_browser.py -q --tb=short -x -rs 2>&1 | tail -30` (phone must be unchanged, 0 skipped). Commit `1133 step 3`.

### Step 4: tests (at most 5 calls)
New `App/tests/test_host_new_dashboard_1133.py`, following the fixtures in `test_dashboard_queue.py` (grep its first 40 lines for the client/login/seed helpers): (a) `dash-wide` contains the greeting with the user's first name and `class="dash-add"` once; (b) three `dash-tile` items, none inside an `<a>` or `<button>`; (c) tile numbers equal `reporting.month_summary` values (`stays` key present); (d) with 6 needs-you lines: 4 `dash-card`, `Show 2 more`, the first card's button has `is-primary`, others do not; (e) no lines: `dash-calm` with `See all stays`; (f) browser (copy the style of `test_dashboard_rows_browser.py`, 0 skipped): at 1280 and 820 the tiles are in one row, no horizontal scroll, `.dash-add` height 48, the phone block is hidden; at 390 `.dash-wide` is `display:none`. No real guest data. Commit `1133 step 4`.

## 5. Do not touch

- The phone layout (`dash-phone` markup and `ph-*` rules) and the sidebar from brief 1132.
- Needs-you data logic and action handlers (reuse them, do not change them).
- Migrations, `db.py` helpers other than reading one existing count, any new dependency or outbound request.
- The Today list and the This week strip (brief 1134).
- Anything not listed in section 3 Files.

## 6. Commands (from `App/`, each ends `| tail -30`)

```
.venv/bin/python -m pytest tests/test_host_new_dashboard_1133.py tests/test_dashboard_*.py tests/test_0520_overview_today.py tests/test_needs_you*.py tests/test_0375_needs_you_and_open.py tests/test_host_quiet_dashboard*.py -q --tb=short -x -rs 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py tests/test_0710_v2_mockup_match_browser.py -q --tb=short -x -rs 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_static_versions.py tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py tests/test_privacy_first.py -q --tb=short -x 2>&1 | tail -30
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x -rs 2>&1 | tail -30
```
Rows used (test-map): host pages/CSS/templates, alerts and needs-you, calendar (dashboard calendar), copy and translations, static cache keys. 0 skipped on every browser file. No full suite.

## 7. Acceptance

- At 1280 and 820: greeting with first name by time of day (30 px / 28 px, bold), date line, ONE coral "Add stay" pill 48 px high on the right; three display-only tiles in one row at 1280, stacked icon-over-text at 820; "What needs you" with count chip, cards with 52 px icon tile, 18/600 title, meta line with property dot, one 48 px secondary pill (first card coral), "Show N more" after 4; calm state shows the next arrival and "See all stays".
- No help `?` next to the title on this layout; no sentence the button already says; no raw hex or inline style added to templates (`git diff -U0 App/app/templates | grep -nE "#[0-9a-fA-F]{3,6}|style=" | tail -30` shows none that you added).
- Phone (390) is pixel-identical in structure: `dash-phone` unchanged inside; phone tests green.
- UX gate (AGENTS rule 10, you do it, never ask the owner): screenshots 390/768/1280 of `/` with demo data and with an empty needs-you state; per page "390: ...; 768: ...; 1280: ..." in the PR; tick the [design-system checklist](../design/design-system.md); never silence a lint finding.
- Section 5 green, 0 skipped.

## 8. Stop and ask

Stop and report if: 1132 is not in the base; an anchor is missing; no local-time helper exists; `dashboard-calendar.js` refresh would duplicate or break the new block; more than one existing test asserts markup you cannot keep without weakening it; the layout lint flags something not fixable in 2 tries; more than 25 tool calls.

## 9. Report (branch, PR and what to report)

Branch `task/1133-dashboard-redesign-b`, one **draft** PR, never push to `main`, merge only with `scripts/merge-pr-on-green.sh` (owner), keep the draft until the owner says it may ship (a half-built dashboard must not deploy before 1134). Do not edit status, decisions or known-issues. Report `docs/tasks/1133-report.md` (600 tokens at most): files changed, commands with last 5 lines, section 6 ticked, per-page notes, Deviations (`Done: steps 1 to k. Left: steps k+1 to 4.`), Questions, owner steps.

## Assumptions the orchestrator should confirm

"N still missing" uses the count of stays with missing police details (`missing_report_rows`); "N late" uses red stay lines in the needs-you list. Both are existing data; no new query except `stays` from the existing one.
