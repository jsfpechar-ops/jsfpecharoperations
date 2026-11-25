# 2089: Mobile Calendar Property Index and Single-Property Month View

Status: todo
Depends on: 2088 | Base commit: 43f2d0182 | Branch: task/2089-go-mobile-calendar-property-index
Executor: medium | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Fix the broken mobile multi-property calendar (`/?cal_view=calendar` at `<768 px`), where `PILL_LANES = 1` hides 2 of 3 stays on the same day. Replace the multi-property mobile month grid with an Airbnb-minimal **Property Index -> Single-Property Month Calendar** flow in Go.

Owner decisions (2026-11-26, Option 2A simplified):
1. **Phone (`<768 px`), 2+ active properties, no `apartment_id` query param:**
   - Render a clean vertical **Property Calendar Index** (`Kalendáře` / `Calendars`):
     - One card per active property linking to `/?cal_view=calendar&apartment_id={id}`.
     - **Left side:** colored property badge (matching existing `data-cal-color` / `property_identity` color palette, NO empty photo placeholder) + property name (`internal_name`). **NO operational subtitle line** (no "Occupied until..." / "Arrival today..." text; keep it calm and airy).
     - **Right side:** server-rendered **5-week mini-month dot/bar SVG** (Monday-Sunday, starting on the Monday of the current week or first Monday of the current month covering today + next ~34 days): free days as light dots, booked stays as rounded horizontal pill bars spanning the booked nights (amber tint if stay needs action, neutral ink/grey otherwise), today marked with a small coral ring (`--acc`).
   - **No** cross-property timeline toggle on mobile calendar.
2. **Phone (`<768 px`), 1 active property OR `apartment_id` selected (`/?cal_view=calendar&apartment_id={id}`):**
   - Auto-skip the property picker when the host has only 1 active property.
   - Render the interactive **Single-Property Month Calendar** locked to that property (since 1 property has at most 1 stay per night, every stay fits cleanly as a full bar with zero hidden lanes).
   - Top bar: when 2+ properties exist, show a `<- Všechny byty` back link (`/?cal_view=calendar`) + compact property switcher `<select>` so the host can jump between flats without going back.
   - Tapping an empty day opens Add Stay with that `apartment_id` pre-selected.
3. **Desktop & tablet (`>=768 px`):**
   - Keep the full interactive calendar (`GET /?cal_view=calendar` mounts the calendar partial in Go `dashboard.tmpl` matching `_dashboard_calendar.html` and consuming the existing Go `GET /dashboard/calendar` API), and honor `?apartment_id={id}` when deep-linked from a property header so desktop clicks work too.

## 2. Context

Plan: `docs/plans/host-ux-comfy-refresh.md`.
Rules: `docs/context/go-first.md`, `docs/design/design-system.md` (rules 1, 2, 3, 6, 8, 9), `docs/design/pages/dashboard.md`, AGENTS.md rules 6, 7, 10, 11.

Exact excerpts (verify verbatim before editing; if not found, STOP per section 8):

- `App/app/static/dashboard-calendar.js:298`:
  `const PILL_LANES = matchMedia("(min-width:768px)").matches || cleaningMode ? 3 : 1;`
- `go/internal/web/hostweb/dashboard.go:115`:
  `calView := r.URL.Query().Get("cal_view") != "" || strings.HasPrefix(r.URL.RawQuery, "cal_")`
- `go/internal/web/hostweb/dashboard.go:121-127`:
  `Nav: "dashboard"` — note when `calView` is true, `Nav` must be `"calendar"` so the bottom tab bar highlights `Kalendář` (see `go/internal/hostweb/layout/shell.html:329`).
- `go/internal/calendar/handler.go:242`: Go already serves `GET /dashboard/calendar` JSON for the interactive calendar!
- `go/internal/web/cleaning/hosttemplates/_calendar.tmpl`: existing Go template for the calendar widget.
- `App/app/templates/_dashboard_calendar.html`: reference markup & `data-cal-*` hooks expected by `App/app/static/dashboard-calendar.js`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/hostweb/mini_calendar.go` | create | pure server-side 5-week mini-month dot/bar SVG builder (`BuildMiniCalendar(stays, today)`) with deterministic unit tests |
| `go/internal/web/hostweb/mini_calendar_test.go` | create | unit tests: empty month, multi-night bar spanning week boundary, today coral marker, amber bar for action-needed stay, no raw user text in SVG |
| `go/internal/web/hostweb/dashboard.go` | edit | read optional `apartment_id` query param when `calView` is true; set `Nav: "calendar"` when `calView`; auto-select sole property when `len(activeApartments) == 1` |
| `go/internal/web/hostweb/dashboard_data.go` | edit | load 35-day mini-calendar stays per active apartment when `CalView` is true; build `CalProperties` list with stable property color index + `MiniCal` data |
| `go/internal/web/hostweb/templates/dashboard.tmpl`, `go/internal/web/hostweb/templates/_calendar_widget.tmpl` | edit / create | in `CalView` mode: render `.cal-prop-index` (phone-only when 2+ properties & no `apartment_id`) and mount the Go interactive calendar widget (`_calendar_widget.tmpl` using `GET /dashboard/calendar`) pre-filtered to `SelectedAptID` |
| `go/internal/web/hostweb/i18n.json` | edit | CS, EN, VI keys for `Calendars` heading, `All properties` back link |
| `go/internal/web/hostweb/dashboard_test.go` | edit | HTTP tests for `/?cal_view=calendar` (2+ flats -> property index + mini SVGs; 1 flat -> skips index; `?apartment_id=X` -> single-property calendar with back link) |
| `App/app/static/dashboard-calendar.js` | edit | read initial `data-cal-initial-property` attribute / `apartment_id` query param to pre-select the property filter and pre-fill `apartment_id` in the Add Stay dialog |
| `App/app/static/app2.css` | edit | token-only styles for `.cal-prop-index`, `.cal-prop-card`, `.cal-prop-swatch`, `.cal-mini-svg`, `.cal-single-bar` (44 px touch targets, >=12 px spacing, light mode only) |
| `docs/design/pages/dashboard.md` | edit | update Phone Calendar section to document the Property Index -> Single-Property Month flow |

No other file may change. Do not edit Python files.

## 4. Steps

1. **Build `mini_calendar.go` (pure Go SVG data/renderer).**
   - Compute a 5-row x 7-column grid (Monday = col 0 .. Sunday = col 6) starting on the Monday of `today`'s week (minus 1 week so current in-house stays that started last week show smoothly — or starting on the Monday of `today`'s week, covering 35 days). Pick the 5-week window starting on the Monday of `today`'s week (days 0..34) so upcoming bookings fill the mini grid cleanly.
   - For each week row (0..4):
     - Emit light grey dots (`r="2.2"`) for free days.
     - Clip each active stay `[date_from, date_to)` to the week row and emit a rounded `<rect rx="3.5">` bar spanning the occupied columns (`class="mini-bar"` or `class="mini-bar is-warn"` when stay needs action).
     - Mark `today` with a coral ring/dot (`class="mini-today"`).
   - Keep SVG lightweight (`viewBox="0 0 112 68"`, `aria-hidden="true"`, zero inline hex — style fills via CSS classes in `app2.css` using tokens).
2. **Wire `CalView` + `apartment_id` in `dashboard.go` & `dashboard_data.go`.**
   - When `calView` is true, set `page.Nav = "calendar"`.
   - Parse optional `apartment_id` (must belong to owner's active apartments; ignore unknown IDs).
   - If `len(activeApartments) == 1` and `apartment_id == 0`, set `SelectedAptID = activeApartments[0].ID` (auto-skip picker).
   - Fetch active stays overlapping `[miniStart, miniEnd)` (35 days) to build `CalProperties` (one entry per active apartment with `ID`, `Name`, `ColorIdx`, `MiniSVG`).
   - Do NOT include an operational subtitle line on `CalProperties` (owner decision 2026-11-26).
3. **Mount Go calendar widget & Property Index in templates.**
   - Create `go/internal/web/hostweb/templates/_calendar_widget.tmpl` porting the host-stay subset of `_dashboard_calendar.html` (`data-source="/dashboard/calendar"`, `data-cal-initial-property="{{.SelectedAptID}}"`).
   - In `dashboard.tmpl`, when `$d.CalView` is true:
     - Hide the non-calendar dashboard sections (needs-you, month summary, mini Gantt, today list).
     - If `len($d.CalProperties) > 1 && $d.SelectedAptID == 0`: render `<section class="cal-prop-index ph-only">` with the Airbnb-minimal property cards (left: `.cal-prop-swatch` + property name; right: `.cal-mini-svg`), and render the full interactive calendar wrapped in `.ph-hide` so desktop/tablet keeps its full calendar unchanged.
     - If `$d.SelectedAptID > 0` (either 1-property host or user tapped a property): render a compact `.cal-single-bar ph-only` header (`<- All properties` link when >1 property + property selector) above the interactive calendar widget locked to `SelectedAptID`.
4. **Update `dashboard-calendar.js` for initial property selection.**
   - On init, read `data-cal-initial-property` (or `apartment_id` URL param), set the property filter before fetching `/dashboard/calendar`, keep URL sync clean, and pre-select that apartment in the Add Stay dialog when tapping an empty day.
5. **CSS (`App/app/static/app2.css`) & i18n.**
   - Style `.cal-prop-card` as a flat white card (`radius 12`, `1 px --line`, `padding 16`, flex space-between, >=12 px gap, 44+ px touch target, entire card is an `<a>` link per design-system §5b).
   - Color `.cal-prop-swatch` using the existing calendar property palette classes (`data-cal-color`).
   - Style `.cal-mini-svg` dots/bars/today ring purely with CSS tokens (no raw hex in SVG or templates).
   - Add CS, EN, VI keys together with no em dashes.
6. **Tests & UX gate.** Run Go tests, run the Go browser layout-lint harness (1668) on `/?cal_view=calendar` (2+ properties & 1 property) and `/?cal_view=calendar&apartment_id=...` at 390/768/1280 px, inspect screenshots, and run `python3 scripts/context_lint.py`.

## 5. Do not touch

Python files under `App/app/`, `App/migrations_pg/`, `/cleaning` calendar behavior, guest pages, `UBYHOST_GO_PATHS`, or `main`.

## 6. Commands

From `go/`: `go test ./internal/web/hostweb/... ./internal/calendar/... -count=1 2>&1 | tail -30`
From repo root: `python3 scripts/context_lint.py 2>&1 | tail -20`
Browser UX gate (brief 1668 harness): run layout-lint + capture 390/768/1280 screenshots of `/?cal_view=calendar` (multi-property index & single-property calendar).

## 7. Acceptance

- [ ] On phone (`390 px`) with 2+ properties, `/?cal_view=calendar` shows one clean card per property (color badge + name + 5-week mini-month SVG, no operational subtitle line, no timeline toggle).
- [ ] Tapping a property card opens `/?cal_view=calendar&apartment_id={id}` showing only that property's stays cleanly on the month grid (no hidden lanes), with a back link to all properties.
- [ ] With 1 active property, `/?cal_view=calendar` skips the picker and renders that property's month calendar directly.
- [ ] Desktop (`1280 px`) and tablet (`768 px`) keep the full calendar view and honor `?apartment_id=...` deep links.
- [ ] All Go tests + layout-lint pass with 0 skipped; 390/768/1280 screenshots inspected and described in PR.

## 8. Stop and ask

Stop and write the report if: an excerpt in §2 is not found verbatim; `dashboard-calendar.js` requires breaking changes to `/cleaning`; a test fails twice; you reach 25 tool calls or ~50k tokens; or any file outside §3 needs editing.

## 9. Report

Write `docs/tasks/2089-report.md` (<=600 tokens), set `Status: review`, open one PR (include per-page 390/768/1280 screenshot notes and design-system checklist). Report: `git diff --stat`, command tails, §7 ticked, deviations, questions, owner steps.
