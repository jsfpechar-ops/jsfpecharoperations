# 0765 brief: phone Today shows the check-in window; Calendar tab opens its own screen

Status: review
Executor: Haiku 5.5, alone, on branch `claude/project-thread-19vzly` in `/home/claude/jsfpecharoperations` (already checked out; do not switch branches, do not push, do not commit).
Another Haiku works on brief 0766 in the same folder at the same time: edit only what this brief names; never revert changes you did not make.

## 1. Objective

Owner feedback (2026-11-02, phone, < 1024 px):
- A. Today only lists stays that arrive or leave *today*, so most days read "All done" with one grey "Next arrival" line. Hosts work from the day before check-in until 3 days after it (police deadline). Today must show every stay in that window as a card.
- B. The Calendar tab (`/?cal_view=calendar`) opens the Today page with the calendar under it, and the Today tab stays highlighted. It must show only the calendar, with the Calendar tab active.
Desktop (>= 1024 px) must not change at all.

## 2. Context

- Route: `App/app/routes/admin.py` `dashboard()` (~line 440-545): context keys `today_rows`, `next_arrival`, `cal_view`.
- Template: `App/app/templates/dashboard.html`: line 3 `{% set nav = 'dashboard' %}`; phone top `.ph-top` (~57), `h1.hl` with `.ph-hide`/`.ph-only` spans (~62), `.hl-sub` next-arrival line (~63), `#needs-action` (~89), 14-day grid `.ov-cal-block` (~113-123), `{% include "_dashboard_calendar.html" %}` (~124), the phone stay cards `<div class="hs ph-only">` (~126-136).
- Tab bar: `App/app/templates/_shell_v2.html` line ~47: Calendar tab is `on` when `nav == 'calendar'`.
- CSS: `App/app/static/app2.css` `.hs` cards ~264-270 (phone v2 shared, reuse; add no new card style). `.kind.in/.out` label exists.
- i18n: `App/app/host_i18n.py` (en ~8674, cs ~8709 near `dashboard.ph.next`) and `App/app/host_vi_i18n.py` (~3938).
- Date filter: brief 0766 adds the Jinja filter `stay_range` (e.g. "Thu 5 – Sun 8 Nov"). Do not add it yourself: the other Haiku owns `templating.py`. Use it in the template; before running tests check `grep -n stay_range App/app/templating.py`, and if it is still missing, do other steps first and check again.
- One visible h1 per page (geometry rule): switch h1 text by state inside the one h1.
- Standing rule for tests: you may change assertions that only check the phone Today screen below 1024 px in `App/tests/test_0729_phone_today_geometry_browser.py`, `test_dashboard_phone_browser.py`, `test_host_quiet_dashboard_browser.py`, and the dashboard entry of `App/tests/v2_mockup.py`. Change no desktop assertion.

## 3. Files

`routes/admin.py`, `dashboard.html`, `app2.css` (only if needed), the three i18n files, the tests named above, one new test file.

## 4. Steps

0. Before editing, take "before" 390 px full-page screenshots of `/` and `/?cal_view=calendar` with the fixture used by `test_0729` (`dashboard_rich_host`) to `docs/tasks/screenshots-0765/before-today-390.png` and `before-calendar-390.png` (write a throwaway script in `/tmp`, reuse `_open_app`/`_launch` helpers; do not commit the script).
1. Route: add context key `key_rows` = rows from `rows` whose reservation is active and where `today - 3 days <= date_from <= today + 1 day`, or `date_to == today`; sorted by `date_from`; each as `dict(row, nights=_today_nights(...), key_kind=...)` where `key_kind` is `"tomorrow"` (date_from == today+1), `"today"` (date_from == today), `"leaves"` (date_to == today and date_from < today), else `"arrived"`. Change `next_arrival` to the first row (not just reservation) with `date_from > today + 1` so the template can show its status. Set `"nav": "calendar" if cal_view else "dashboard"` in the context and remove `{% set nav = 'dashboard' %}` from the template only if the context value then reaches `_shell_v2.html` (check; otherwise use `{% set nav = 'calendar' if cal_view else 'dashboard' %}`).
2. Template, phone only (everything new is `ph-only`):
   - When `cal_view`: phone shows only the h1 (phone span text `t('nav.calendar')`) and the full calendar include. Hide on phone in cal_view: `.ph-top`, `.hl-sub`, `#needs-action` and `.needs-you-more`, the "Today" `h2.sec` and `.hs`, the month line. Do it with a `ph-hide` class added only when `cal_view` (desktop keeps today's look; `ph-hide` is phone-only). Hide the "Full calendar" link `.ov-cal-more` on phone in cal_view too.
   - Not cal_view: replace the phone loop over `today_rows` in `.hs.ph-only` with a loop over `key_rows`, same `.card` markup; the `.kind` label text by `key_kind`: tomorrow -> `dashboard.ph.kind.tomorrow` ("Tomorrow" / "Zítra" / "Ngày mai"), today -> `calendar.arrival` (existing), leaves -> `calendar.departure` (existing), arrived -> `dashboard.ph.kind.arrived` ("Arrived %(day)s" / "Přijel(a) %(day)s" / "Đã đến %(day)s", day = `reservation.date_from | pass_date('wd')`). `.kind` class `in` for tomorrow/today/arrived, `out` for leaves. Under the name line keep `.meta`, and prefix it with `reservation.date_from | stay_range(reservation.date_to)`.
   - The h2.sec above the cards: phone text `t('dashboard.ph.window')` ("Check-ins" / "Příjezdy" / "Khách đến") shown when `key_rows`; desktop text unchanged (use `.ph-hide`/`.ph-only` spans).
   - When `key_rows` is empty and `next_arrival` exists: replace the `.hl-sub` sentence with one `.hs` card (same markup) for `next_arrival`, `.kind.in` label `dashboard.ph.kind.next` ("Next stay" / "Další pobyt" / "Lượt khách tiếp theo"). Keep the "All done" headline. Remove the now-unused `dashboard.ph.next` key from the three i18n files only if no other template uses it (grep).
3. i18n: add the new keys to en, cs and vi.
4. Tests, from `App/` (do NOT reinstall playwright):
   `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0729_phone_today_geometry_browser.py tests/test_dashboard_phone_browser.py -q --tb=short 2>&1 | tail -30`, then `tests/test_0710_v2_mockup_match_browser.py -k "dashboard or overview or today"` the same way, then non-browser `ls tests | grep -i dashboard` files without `browser`.
   Add `App/tests/test_0765_phone_today_window_browser.py` (reuse 0729 fixtures, freeze nothing; build stays relative to `deadlines.local_now().date()`): at 390 px (a) a stay with check-in 2 days ago and one tomorrow both render a `.hs .card`; a stay 10 days ahead does not; (b) `/?cal_view=calendar` at 390 px: the Calendar tab `.tabs .tab.on` text is the calendar label, `.hs`, `#needs-action` and `.ph-top` are not visible, exactly one visible h1; (c) at 1280 px `/?cal_view=calendar` still shows `#needs-action` (desktop unchanged). Keep it under 120 lines.
5. "After" screenshots, same script: `docs/tasks/screenshots-0765/after-today-390.png`, `after-calendar-390.png`, plus `after-today-nothing-in-window-390.png` (a host whose only stay is 10 days ahead).
6. Write `docs/tasks/0765-report.md`: what changed, test commands with their last line, anything you could not do.

## 7. Follow-up (orchestrator, after the first run)

The first executor finished steps 0-3 and 5 (see `0765-report.md`); the template and route changes are in the working tree. Do not redo them. Remaining:

1. The 0729 failures ("stay card 0/1 off centre", "stay card 1 overflows the viewport") are expected: with more than one stay in the window, `.hs` is the approved sideways-scrolling row from #681 (cards 272 px, scroll-snap). Do not change the CSS. Update `test_today_phone_geometry` in `App/tests/test_0729_phone_today_geometry_browser.py`: when there is one visible `.hs .card`, keep today's centre/inside checks; when there are several, check instead that the first card's left edge equals the `h2.sec` left edge (±1 px), every card's top is equal (±1 px), and `.hs` `scrollWidth > clientWidth`. Measure `.hs` in MEASURE for that.
2. Write `App/tests/test_0765_phone_today_window_browser.py` as step 4 says.
3. Run, from `App/`, with `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome`: `tests/test_0729_phone_today_geometry_browser.py tests/test_dashboard_phone_browser.py tests/test_0765_phone_today_window_browser.py -q --tb=short 2>&1 | tail -30`, and the non-browser dashboard tests (`ls tests | grep -i dashboard | grep -v browser`). Also run `tests/test_static_versions.py` and `python3 ../scripts/context_lint.py` if present.
4. Append results to `0765-report.md`.

## 8. Follow-up 2 (orchestrator)

Two failures left (see report):
1. 0729 "first card left 0, h2 left 20": `.hs` has `scroll-snap-type:x mandatory` and cards `scroll-snap-align:start`, but no scroll padding, so the browser snaps the first card to the scrollport edge (left 0) and hides the 20 px gutter. That is a real bug. Fix in `App/app/static/app2.css` line ~264 by adding `scroll-padding-inline:20px` to `body.v2 .hs` (this one CSS change is allowed). Rerun 0729.
2. `test_dashboard_phone_browser.py::test_phone_dashboard_compact`: `.needs-you-more > summary` not visible at 390. Find the cause: dump the rendered HTML of `/` for that test's fixture around `needs-you-more` and `#needs-action`, and check computed `display` of the details/summary and its parents at 390. Compare with `git show HEAD~1:App/app/templates/dashboard.html` (main's version). Possible causes: the moved next-stay/`.hs` block, an unclosed tag in the edited template, or the `ny-phone-only` rule. Fix the template, not the test, unless the test assumption is about the old Today cards.
Then run 0729, test_dashboard_phone_browser.py, test_0765 (same env as §7), plus the 0710 subset `-k "dashboard or overview or today"` and the non-browser dashboard tests. Append results to 0765-report.md.

## 9. Report

See the matching `-report.md` file.
