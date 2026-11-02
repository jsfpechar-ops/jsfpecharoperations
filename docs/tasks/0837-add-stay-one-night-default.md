# 0837: Add stay: departure defaults to arrival + 1 night; phone day tap opens the form

Status: todo
Depends on: 0841 (baseline first); goes before 0840 (both edit `reservations.html`). Older open briefs naming the same files (0134, 0137, 0236, 0237, 0242) are stale; this one goes first | Base commit: b8c87df | Branch: task/0837-add-stay-defaults
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Picking an arrival in the "Add stay" panel or the calendar dialog fills the departure with the next day when it is empty or not after the arrival. On a phone, tapping an empty calendar day opens the create form with that day filled instead of an empty day list. Target: 3 taps + 2 typed to 2 taps + 0-1 typed.

## 2. Context

Verified on b8c87df: on desktop a day click already opens the create dialog with arrival = day and departure = day + 1 (`App/app/static/dashboard-calendar.js` line 740). What is missing: (a) the stays-page panel has no departure default; (b) changing the arrival in the calendar dialog does not move the departure; (c) on a phone (`phoneDots()`), a day tap opens the day list (line 739), one extra tap to "Add".

The host still sees and can change both dates; the form posts only on the create button. Stay dates feed the police report, so never post without the host's tap (UbyPort rule 1).

Anchors:
- `App/app/templates/reservations.html` (around line 52, add-stay panel): `          <input type="date" id="date_from" name="date_from" required>`
- `App/app/static/app.js` line 872: `  function initTogglePanels() {` and line 2253: `    initTogglePanels();`
- `App/app/static/dashboard-calendar.js` line 739: `      if (phoneDots()) { openDay(day.dataset.calDay); return; }` and line 792: `  ["date_from", "date_to", "apartment_id"].forEach(name => form.elements[name].addEventListener("change", updateNights));`
- Cache keys: `App/app/templates/base.html` line 41 `app.js?v=20261102-0510`; `App/app/templates/_dashboard_calendar.html` line 170 `dashboard-calendar.js?v=20261102-0507`. A changed static file needs a new key and `tests/static_versions.json` rewritten (`tests/test_static_versions.py` docstring).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/reservations.html` | edit | One attribute on `#date_from` |
| `App/app/static/app.js` | edit | `initDepartureDefault` |
| `App/app/static/dashboard-calendar.js` | edit | Arrival moves departure; phone empty day opens create |
| `App/app/templates/base.html` | edit | app.js key |
| `App/app/templates/_dashboard_calendar.html` | edit | calendar key |
| `App/tests/static_versions.json` | regenerate | `--write` |
| `App/tests/test_dashboard_calendar_browser.py` | edit | Two tests |
| `docs/tasks/0837-report.md` | new | Report |

No other file may change. If `grep -rn 'app.js?v=' app/templates` names another template, add it to the report and update its key too (same value).

## 4. Steps

1. `reservations.html`: `grep -c 'id="date_from" name="date_from" required>' app/templates/reservations.html` must print 1. Replace the anchor line with `          <input type="date" id="date_from" name="date_from" required data-departure-for="date_to">`. Commit.
2. `app.js`: insert directly above `  function initTogglePanels() {`:
```js
  // 0837: a new stay defaults to one night; the host can still change the departure.
  function initDepartureDefault() {
    document.querySelectorAll("input[data-departure-for]").forEach(function (arrival) {
      if (!claimNode(arrival, "initDepartureDefault")) return;
      arrival.addEventListener("change", function () {
        var departure = document.getElementById(arrival.getAttribute("data-departure-for"));
        if (!departure || !/^\d{4}-\d{2}-\d{2}$/.test(arrival.value)) return;
        var next = new Date(arrival.value + "T00:00:00Z");
        next.setUTCDate(next.getUTCDate() + 1);
        var iso = next.toISOString().slice(0, 10);
        departure.min = iso;
        if (!departure.value || departure.value <= arrival.value) departure.value = iso;
      });
    });
  }

```
   and below `    initTogglePanels();` add `    initDepartureDefault();`. Commit.
3. `dashboard-calendar.js`: insert directly above the line-792 anchor:
```js
  form.elements.date_from.addEventListener("change", () => {
    const start = form.elements.date_from.value, end = form.elements.date_to.value;
    if (createKind === "stay" && validDate(start) && (!end || end <= start)) form.elements.date_to.value = addDays(start, 1);
  });
```
   (it must stay above, so it runs before `updateNights`). Replace the line-739 anchor with:
```js
      if (phoneDots()) {
        const tapped = day.dataset.calDay;
        if (readOnly || state.events.some(event => displayOverlap(event, tapped, addDays(tapped, 1)))) { openDay(tapped); return; }
        openCreate(tapped, addDays(tapped, 1), state.property, "stay", day); return;
      }
```
   Commit.
4. Bump keys: `app.js?v=20261102-0510` to `app.js?v=20261102-0837` and `dashboard-calendar.js?v=20261102-0507` to `dashboard-calendar.js?v=20261102-0837`. Then `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`. Commit.
5. Tests in `test_dashboard_calendar_browser.py`, after `test_drag_nights_create_persist_and_open_details`, using its fixtures and helpers (`launch`, `open_page`, `shot`):
   - `test_arrival_change_sets_one_night`: open the calendar, click a day of the selected property (as that test does, but a single click on `[data-cal-day="2026-10-26"]`), then `page.locator("#cal-arrival").fill("2026-11-05")`; assert `#cal-departure` is `2026-11-06`. Then on `/reservations` (same context, `page.goto(calendar_origin + "/reservations")`), click the first visible `[data-toggle-panel="add-stay-panel"]`, fill `#date_from` with `2026-11-05`, assert `#date_to` is `2026-11-06`. `shot(page, "add-stay-panel-390")` after `page.set_viewport_size({"width": 390, "height": 844})`.
   - `test_phone_empty_day_opens_create`: `page.set_viewport_size({"width": 390, "height": 844})`, reload, wait for `[data-cal-day]`; pick, with `page.evaluate`, a `[data-cal-day]` whose element contains no `[data-cal-event]` child; click it; assert `[data-cal-create]` is visible and `#cal-arrival` equals that day; `shot(page, "calendar-phone-create-390")`. If no empty day can be found in the fixture month, STOP and ask.
   Commit.
6. Run §6. Commit.

## 5. Do not touch

`routes/admin.py` (`reservation_create`), drag selection code, cleaning create, any wizard, onboarding or property-editor file (other threads). No autosave.

## 6. Commands

From `App/`:
1. Calendar row: `.venv/bin/python -m pytest tests/test_icalsync.py tests/test_ical_skip_unchanged.py tests/test_feed_*.py tests/test_dashboard_calendar*.py tests/test_calendar_*.py tests/test_sample_calendar.py -q --tb=short -x -rs 2>&1 | tail -30`
2. Host row: `.venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py -q --tb=short -x -rs 2>&1 | tail -30`
3. Static row: `.venv/bin/python -m pytest tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py -q --tb=short -x 2>&1 | tail -30`

Expected: all pass, 0 skipped.

## 7. Acceptance

- [ ] Arrival change fills departure + 1 in the panel and the calendar dialog; a later departure the host typed is kept.
- [ ] At 390 px an empty day opens the create form; a day with stays still opens the day list.
- [ ] Commands 1-3 pass, 0 skipped.
- [ ] 390 px screenshots of `/reservations` (panel open) and the calendar (create open) in the report.

## 8. Stop and ask

Stop, and write the report, if an excerpt is not found; a test fails twice; you reach 25 tool calls or about 50k tokens (report `blocked`, see executor.md); a new dependency seems needed; a file outside §3 needs a change; §5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0837-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left, and the 0841 counts for "add stay" after the change.

## Risk list (for the reviewer)

`App/app/static/dashboard-calendar.js` (listener order; phone branch must not open create for read-only users).

## Owner steps

1. Check the two 390 px screenshots in the PR, then merge with `scripts/merge-pr-on-green.sh <pr>` when CI is green.
