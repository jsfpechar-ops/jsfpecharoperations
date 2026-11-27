# 2090: Comfy Dashboard Refresh — phone per-property stay carousels and desktop 7-day tab

Status: done
Depends on: 2087, 2088, 2089 | Base commit: 43f2d0182 | Branch: task/2090-go-dashboard-property-carousels
Executor: medium | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Make the host Dashboard (`GET /`) calm, scannable, and comfortable for multi-property hosts on both phone and desktop, building on briefs 2087 (calm notifications), 2088 (4-step Stay Journey Status Strip), and 2089 (single-property calendar deep links).

Owner decisions (2026-11-26):
1. **Phone (`<768 px`) — Per-property compact horizontal stay carousels:**
   - Replace the current single `.hs` carousel of giant 250 px centered avatar cards (`app2.css:957`) with **one compact horizontal swipeable rail per active property**.
   - **Property rail header:** property color dot (`data-cal-color`), property name, and a quiet `Kalendář ›` link jumping straight to `/?cal_view=calendar&apartment_id={id}` (from brief 2089). Do NOT duplicate a separate property-list block on Dashboard.
   - **Compact stay card (~96 px tall, ~285 px wide so card #2 peeks on the right edge of a 390 px screen):**
     - No 72 px avatar circle.
     - Top row: guest name (or stay label / source) on left + compact timing tag (`Příjezd dnes`, `Odjezd dnes`, `Ubytován`, `Zítra`, or `Za N dní`) on right.
     - Middle row: date range · nights · guest count (`24.–27. 11. · 3 noci · 2 os.`).
     - Bottom row: the **4-step Stay Journey Status Strip** from brief 2088 (`Link · Form · Code · Police`).
   - **Volume guardrails:**
     - Cap each property's rail at **5 stays** (current in-house / departing today + next upcoming) plus a slim trailing `Další pobyty ›` card linking to `/reservations?apartment_id={id}` when more stays exist.
     - Sort properties by **soonest urgency / soonest arrival** (properties with an arrival/departure today or missing guest form float to the top; empty properties sort last).
     - Cap rendered property rails at **5 properties**; if the host has >5 active properties, show a quiet `Všechna ubytování (N) ›` link to `/apartments` below the 5th rail.
     - If a property has **0 current/upcoming stays**, show one quiet 1-line placeholder card (`Žádné nadcházející pobyty`) rather than an empty gap.
2. **Desktop (`>=1024 px`) & Tablet (`768–1023 px`):**
   - Keep the capped `Needs you` section (2087) and the **14-day multi-property Gantt** (`ov-cal-block`), making each property name in the Gantt a link to `/?cal_view=calendar&apartment_id={id}`.
   - Upgrade the Today table (`ov-table`) with two clean tabs/chips: **`Dnes`** and **`Příštích 7 dní`** (auto-defaulting to `Příštích 7 dní` when `Dnes` has 0 rows so quiet weekdays never look dead), including the **4-step Stay Journey Status Strip** column (2088).

## 2. Context

Plan: `docs/plans/host-ux-comfy-refresh.md`.
Rules: `docs/context/go-first.md`, `docs/design/design-system.md` (rules 1, 2, 3, 6, 8, 9, 10), `docs/design/pages/dashboard.md`, AGENTS.md rules 6, 7, 10, 11.

Exact excerpts (verify verbatim before editing; if not found, STOP per section 8):

- `go/internal/web/hostweb/templates/dashboard.tmpl:53-55`:
  `{{- range $d.CalRows}}`
  `<div class="cgrid crow"><div class="cn" title="{{.Name}}">{{.Name}}</div>...`
- `go/internal/web/hostweb/templates/dashboard.tmpl:60-88`:
  Phone `.hs` carousel block and desktop `.ov-table` Today table.
- `App/app/static/app2.css:279-285` and `:957-964`:
  Current `.hs` horizontal scroll carousel and giant 72 px `.av` centered card rules.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/hostweb/dashboard_data.go` | edit | add `PropertyRails []propertyRail` (sorted by urgency/arrival, max 5 rails, max 5 stays per rail + `HasMore`), `Next7Rows []todayRow`, `TotalActiveProperties`, and `DefaultDeskTab` (`"today"` or `"next7"`) |
| `go/internal/web/hostweb/dashboard.go` | edit | support optional `?window=today|next7` query param for no-JS desktop tab switching; add any small template helpers (`timingTag`, etc.) |
| `go/internal/web/hostweb/templates/dashboard.tmpl` | edit | replace phone `.hs` block with per-property `.prop-rail` carousels (with 4-step journey strip + `Kalendář ›` links); link desktop Gantt property names to `/?cal_view=calendar&apartment_id={id}`; add `Dnes / Příštích 7 dní` switcher on desktop `.ov-table` |
| `go/internal/web/hostweb/i18n.json` | edit | add CS, EN, VI keys for `Kalendář`, `Další pobyty`, `Všechna ubytování`, `Žádné nadcházející pobyty`, `Příštích 7 dní`, `Za %(days)s dní` |
| `go/internal/web/hostweb/dashboard_test.go` | edit | unit + HTTP tests: property rail sorting, 5-stay rail cap + `HasMore`, 5-property cap + `All properties` link, empty property placeholder, desktop `next7` auto-default when `today` empty |
| `App/app/static/app2.css` | edit | token-only styles for `.prop-rail`, `.prop-rail-head`, `.prop-rail-track`, `.prop-stay-card` (~285 px wide, compact height, horizontal scroll snap with zero page overflow), `.prop-stay-more`, `.ov-window-tabs` |
| `docs/design/pages/dashboard.md` | edit | update Dashboard spec for phone per-property carousels and desktop `Dnes / Příštích 7 dní` tabs |

No other file may change. Do not edit Python files.

## 4. Steps

1. **Build `PropertyRails` and `Next7Rows` in `dashboard_data.go`.**
   - From `out.Rows` (already enriched with `Progress` and `Journey` from brief 2088), group active stays with `date_to >= today` by `ApartmentID`, ordered by `date_from ASC, id ASC`.
   - For each active apartment:
     - Compute `ColorIdx` (consistent with brief 2089).
     - Assign each stay a compact `TimingKind` (`"leaves"` if `date_to == today`, `"today"` if `date_from == today`, `"in_house"` if `date_from < today && date_to > today`, `"tomorrow"` if `date_from == today+1d`, `"upcoming"` with `DaysUntil`).
     - Keep first 5 stays (`Stays`) and set `HasMore = len(all) > 5` with `MoreCount = len(all) - 5`.
     - Compute sort priority for the property: (0) has stay with red/amber journey or arriving/departing today, (1) has in-house stay, (2) has upcoming stay (earliest `date_from`), (3) 0 upcoming stays; tie-break by `Name`.
   - Slice `PropertyRails` to max 5 and store `TotalActiveProperties = len(activeApartments)`.
   - Compute `Next7Rows`: active stays arriving in `[today, today+7d]` or departing today or currently in-house, ordered by `date_from ASC`. Set `DefaultDeskTab = "today"` if `len(TodayRows) > 0` else `"next7"` (overridable via `?window=today` or `?window=next7`).
2. **Update `dashboard.tmpl` (Phone + Desktop).**
   - **Phone (`.ph-only`, hidden when `CalView`):**
     - Render `<section class="prop-rails">` iterating `$d.PropertyRails`:
       - Header `.prop-rail-head`: `<span class="cal-prop-swatch" data-cal-color="{{.ColorIdx}}"></span><h2 class="prop-rail-name">{{.Name}}</h2><a class="prop-rail-cal" href="/?cal_view=calendar&amp;apartment_id={{.ID}}">{{t "calendar.calendar"}} {{icon "chevron-right" 16}}</a>`.
       - Track `.prop-rail-track`:
         - If `.Stays` empty: `<div class="card prop-stay-empty">{{t "dashboard.rail.empty"}}</div>`.
         - Else: each stay is `<a class="card prop-stay-card" href="/reservations/{{.Row.Reservation.ID}}?return_to=/">` with top row (guest/source + timing badge), middle row (date range · nights · guests), bottom row (compact 4-step `.stay-journey` strip from brief 2088).
         - If `.HasMore`: trailing `<a class="card prop-stay-more" href="/reservations?apartment_id={{.ID}}"><span>{{t "dashboard.rail.more"}}</span>{{icon "chevron-right" 18}}</a>`.
     - If `gt $d.TotalActiveProperties 5`: render quiet link `<p class="prop-rails-all"><a href="/apartments">{{tp "dashboard.rail.all_properties" $d.TotalActiveProperties}}</a></p>`.
   - **Desktop/Tablet (`.ph-hide`, hidden when `CalView`):**
     - In `ov-cal-block` Gantt, wrap `.cn` property name in `<a href="/?cal_view=calendar&amp;apartment_id={{.ID}}">{{.Name}}</a>` (preserving truncation/title styling).
     - Above `.ov-table`, render `<nav class="ov-window-tabs" aria-label="...">` with two links (`/?window=today` and `/?window=next7`) styled with existing `.settings-pill` / tab classes, and render the active slice (`TodayRows` or `Next7Rows`) with the 4-step `.stay-journey` strip in the status cell.
3. **CSS (`App/app/static/app2.css`).**
   - Style `.prop-rail-track` as horizontal flex scroll (`overflow-x: auto; scroll-snap-type: x mandatory; gap: 12px; min-width: 0; max-width: 100%`) so the page NEVER scrolls sideways (design-system rule 10).
   - Size `.prop-stay-card` at `flex: 0 0 285px` (`flex: 1 1 auto` when `:only-child`), flat white card (`border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px`), >=12 px spacing between elements, no raw hex, no `<style>`/`style=""`.
   - Keep `<= 44 px` touch target compliance on `.prop-rail-cal` and tabs.
4. **i18n (CS, EN, VI together, no em dashes).** Add keys in `go/internal/web/hostweb/i18n.json`.
5. **Tests & UX gate.** Run Go tests, run the Go browser layout-lint harness (1668) on `/` at 390, 768, and 1280 px (with 1 property, 3 properties with multiple stays, and >5 properties), verify zero sideways page scroll and card-2 peek at 390 px, inspect screenshots, and run `python3 scripts/context_lint.py`.

## 5. Do not touch

Python files under `App/app/`, `App/migrations_pg/`, guest pages, UbyPort submission logic, `UBYHOST_GO_PATHS`, or `main`.

## 6. Commands

From `go/`: `go test ./internal/web/hostweb/... -count=1 2>&1 | tail -30`
From repo root: `python3 scripts/context_lint.py 2>&1 | tail -20`
Browser UX gate (brief 1668 harness): run layout-lint + capture 390/768/1280 screenshots of `/` (3 properties with multiple stays).

## 7. Acceptance

- [ ] On phone (`390 px`), Dashboard shows one compact swipeable stay carousel per property (no giant 72 px avatar cards, no duplicate property list), with card #2 peeking on the right and zero page-level horizontal scroll.
- [ ] Each property rail header links directly to `/?cal_view=calendar&apartment_id={id}`; each stay card displays the 4-step Stay Journey Status Strip.
- [ ] Rails cap at 5 stays (+ `More stays` card), properties sort by urgency/soonest arrival and cap at 5 rails (+ `All properties (N)` link), and empty properties show a quiet 1-line placeholder.
- [ ] On desktop (`1280 px`), Gantt property names link to single-property calendar; Today table supports `Dnes / Příštích 7 dní` (auto-defaulting to `Příštích 7 dní` when today is empty) with the 4-step strip.
- [ ] All Go tests + layout-lint pass with 0 skipped; 390/768/1280 screenshots inspected and described in PR.

## 8. Stop and ask

Stop and write the report if: briefs 2087, 2088, or 2089 are not merged yet; an excerpt in §2 is not found verbatim; a test fails twice; you reach 25 tool calls or ~50k tokens; or any file outside §3 needs editing.

## 9. Report

Write `docs/tasks/2090-report.md` (<=600 tokens), set `Status: review`, open one PR (include per-page 390/768/1280 screenshot notes and design-system checklist). Report: `git diff --stat`, command tails, §7 ticked, deviations, questions, owner steps.
