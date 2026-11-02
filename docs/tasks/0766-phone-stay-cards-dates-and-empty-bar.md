# 0766 brief: stays list cards show dates and weekdays; no empty white bar on the stay page

Status: review
Executor: Haiku 5.5, alone, on branch `claude/project-thread-19vzly` in `/home/claude/jsfpecharoperations` (already checked out; do not switch branches, do not push, do not commit).
Another Haiku works on brief 0765 in the same folder at the same time: edit only what this brief names; never revert changes you did not make.

## 1. Objective

Owner feedback (2026-11-02, phone, < 1024 px):
- A. Stays list (`/reservations`): most cards read "No name yet" and the dates are cut off at the end of the grey line, so stays cannot be told apart. Each card must show the dates with weekdays, e.g. "Thu 5 – Sun 8 Nov".
- B. Stay page (`/reservations/{id}`): an empty white strip sits right above the tab bar and covers content. It is the fixed phone CTA bar `.stay-head-cta` (`App/app/static/app2.css` ~line 620) shown even when it holds no visible button. Hide it when empty, and drop the extra bottom padding then.
Desktop (>= 1024 px) must not change at all.

## 2. Context

- Stays phone list: `App/app/templates/reservations.html` ~143-185 (`stay_group` macro, `.card.stay` with `.sav` initial, `.in b` title, `.in small` = `internal_name · 5.–8. 11.`).
- Date helpers: `App/app/templating.py` `_PASS_MONTHS`/`_PASS_WEEKDAYS` (~332-347, no `vi` entry) and `_pass_date` (~351); filters registered ~409-411 and ~581.
- Stay page CTA: `App/app/templates/reservation_detail.html` ~38-75 (`stay_cta()` macro; `.stay-head-cta` also holds the desktop-only `ph-hide` copy button). CSS: app2.css ~573 and ~620 (fixed bar), ~649. Padding for the bar: grep `host-stay-detail{padding-bottom` and `.host-stay-detail` padding in app2.css.
- Standing rule for tests: you may change assertions that only check the phone stays list or phone stay page below 1024 px in `App/tests/test_*stay*browser*`, `test_*reservation*browser*`, and the `stays`/`stay` entries and `stays:`/`stay:` BOX_OVERRIDES in `App/tests/v2_mockup.py` (text-dependent widths only, under a `# text-dependent (0766)` comment). Change no desktop assertion.

## 3. Files

`templating.py`, `reservations.html`, `app2.css`, the tests above, one new test file.

## 4. Steps

0. Before editing, take "before" 390 px full-page screenshots of `/reservations` and of one stay page without a CTA (a future stay with no guests) using the fixture the 0710 test uses for `stays`/`stay` (find with `grep -n "stays\|stay" tests/test_0710_v2_mockup_match_browser.py | head`), to `docs/tasks/screenshots-0766/before-stays-390.png` and `before-stay-390.png` (throwaway script in `/tmp`, not committed).
1. Do this step first: the other Haiku waits for it. `templating.py`: add `"vi"` to `_PASS_WEEKDAYS` `("T2","T3","T4","T5","T6","T7","CN")` and to `_PASS_MONTHS` `("thg 1", …, "thg 12")`. Add a `@pass_context` filter `stay_range(context, date_from, date_to)` registered as `stay_range`: lang from context like `_pass_date`; unparseable -> "". Output:
   - en: same month "Thu 5 – Sun 8 Nov"; else "Sat 31 Oct – Mon 2 Nov".
   - cs: same month "čt 5. – ne 8. 11."; else "so 31. 10. – po 2. 11.".
   - vi: "T5 5/11 – CN 8/11".
   - other langs: like en with that lang's tables.
   Use a thin space-free plain " – " (en dash with spaces). Add a unit test in `App/tests/test_0766_stay_range.py` (the five examples above, plus "" for a bad date).
2. `reservations.html` phone card: if there is a lead name or a manual summary, `b` = that name and `small` = `stay_range` first, then ` · ` and `internal_name`; else `b` = `stay_range` and `small` = `internal_name`. The `.sav` circle: name initial when named; when not named show the check-in day number (`d_from.day`). Keep the pill. Do not change the section headers or the desktop table.
3. `app2.css`: hide the phone CTA bar when it has nothing visible to show, below 1024 px only: `body.v2 .host-stay-detail .stay-head-cta:not(:has(form, a.btn)){display:none}` (check the `stay_cta()` macro: every real phone CTA is a `form` or an `a.btn`; the only other child is the desktop `ph-hide` copy button). Also make the phone bottom padding that reserves room for the bar apply only when the bar shows (e.g. `.host-stay-detail:has(.stay-head-cta :is(form, a.btn))`). Then grep app2.css for other phone fixed bars at `bottom:calc(84px` (`.actbar`, ~289) and check whether they can also render empty; fix the same way only if they can. No `!important`.
4. Tests, from `App/` (do NOT reinstall playwright):
   `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -q --tb=short -k "stays or stay" 2>&1 | tail -30`, then the stays/stay browser tests (`ls tests | grep -i -E 'stay|reservation' | grep browser`) the same way, then `tests/test_0766_stay_range.py`.
   Add to a new `App/tests/test_0766_phone_stays_browser.py` (reuse the 0710 fixtures; under 100 lines): at 390 px a no-name stay card's `b` contains the weekday and day of check-in; a stay page with no CTA has no visible `.stay-head-cta`; a stay page with a CTA (guests ready to send, or failed) still shows it.
5. "After" screenshots, same script: `docs/tasks/screenshots-0766/after-stays-390.png`, `after-stay-390.png`.
6. Write `docs/tasks/0766-report.md`: what changed, test commands with their last line, anything you could not do.

## 9. Report

See the matching `-report.md` file.
