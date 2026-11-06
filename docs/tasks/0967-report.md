# 0967 report (B09: C02, C03)

Status: blocked
Reason: command 1 failed twice with the same assertion in `test_0967_open_day_panel_never_crushes_booking_text[768]` (App/tests/test_dashboard_calendar_browser.py line 1393): `assert all(width_ >= 36 ...)` on the closed state, names `[99, 99, 99, 228, 228, 228, ...]` (the list is cut off, so the failing narrow name is not visible). The same test passed when run alone (`::test_0967_open_day_panel_never_crushes_booking_text[768]`, 1 passed in 27.55 s), so the failure looks order- or state-dependent, but the stop rule applies. Commands 2 to 7 were not run.

Done: steps 1 to 4 (step 4 = the approved 184 to 226 bound change). Command 1 run twice.
Left: command 1 green with 0 skipped; commands 2 to 7; UX gate for the 0967 shots that were never written (panel at 1024/1280, week, year, focus); §7 ticks that depend on them.

## Commits (branch codex/0967-b09-calendar-orient, not pushed)
- 3a92d95c 0967 step 1 (dashboard.html line 49)
- 7bd9c59d 0967 step 2 (CSS block, JS pillRow, two ?v= keys, static_versions.json)
- 5cd4763c 0967 step 3 (range(3) to range(4) in check_tiles_0891; four new tests)
- 6ecad272 0967 step 4 (line 335 bound 184 to 226, one comment line above it)

## Files changed
- Steps 1 to 3: dashboard.html 1 line; dashboard-calendar.css +16; dashboard-calendar.js +5/-1; _dashboard_calendar.html 2 lines; static_versions.json (matches patch); test_dashboard_calendar_browser.py.
- Step 4: App/tests/test_dashboard_calendar_browser.py, 2 lines changed (bound and comment only).
- `git diff --stat main...HEAD` lists 12 files, including docs/tasks/0978-* and the 0967 brief and report. Those are not §3 files; they come from the branch base, not from this batch. Not changed by me.

## Commands
1. `tests/test_dashboard_calendar_browser.py -rs -x -q --tb=short` with the §6 env: FAIL, twice.
   - Run 1: `1 failed, 60 passed in 675.43s (0:11:15)`, 0 skipped.
   - Run 2 (full file): `1 failed, 60 passed in 790.30s (0:13:10)`, EXIT=1, 0 skipped.
   - Last lines of run 2:
   ```
   E   AssertionError: ('closed', [99, 99, 99, 228, 228, 228, ...])
   E   assert False
   1 failed, 60 passed in 790.30s (0:13:10)
   EXIT=1
   ```
   - Isolated run of the same test at 768: 1 passed in 27.55 s.
2. to 7: not run (stop at first failure).
- `git diff --check`: clean.
- `python3 scripts/context_lint.py`: `context lint: OK` (warnings only, pre-existing, plus "9 commits touched App/ after status.md").

## Screenshots inspected (10 of the 18 expected)
The run stopped at the 768 panel test, so these 10 exist: heading-{en,cs}-{390,768,1280}, overflow-{768,1280}, panel-closed-768, panel-open-768. Not written: panel-{closed,open}-{1024,1280}, week-{768,1280}, year-{768,1280}, focus-{768,1280}. Images were viewed at reduced size (about 330 to 556 px wide), so fine text and badge detail are not verified.
- heading-en/cs-390: one H1 ("Calendar" / "Kalendář") above the month. First month caption ("October" / "říjen") shown, as expected at 390. No +N badge (correct for phone). Sunday bars ("Refresh ...", "0908 st...") look cut at the right edge of the viewport. Needs a zoomed look before the gate can pass.
- heading-en/cs-768: one H1, no duplicate caption over the first month (hidden as specified), "November" caption shown. Sat/Sun bars run to the right edge of the frame and look clipped there. Phone-style bottom nav appears mid-page, likely a full-page capture artifact of a fixed element (not verified).
- heading-en/cs-1280: one H1 on the sidebar layout. Week of Oct 14 to 18 shows bars with "+2" badges sitting below the bars in the tiles. Oct 5 row shows "+1" under Mon. No bar clipped at this size.
- overflow-768 / overflow-1280: full-month shots, not zoomed, so badge placement was not checked by eye here (the test checks it). Same bytes as heading-768 / heading-1280 for overflow-1280 and overflow-768 (identical images, likely the same state captured twice).
- panel-closed-768: month with badges "+2" under Wed to Sat in the Oct 14 row. Nothing obviously clipped at this scale.
- panel-open-768: "Stays on 16 October 2026" panel at the right with full-width list items (for example "Calendar home 1") and an "Add stay" button. Names not truncated. The panel covers the Fri to Sun columns, as the panel-margin rule allows. A blank area above the Oct 1 to 4 row and a toolbar drawn over the grid look like a sticky-head capture artifact (not verified).

## §7 acceptance
- [x] Steps 1-3 committed as 0967 step 1/2/3. Step 4 committed as 0967 step 4.
- [ ] Commands 1-7 pass, 0 skipped. (Command 1 failed twice; 2 to 7 not run.)
- [x] H1 is the only visible H1 at 390, 768, 1280, EN and CS (seen in the six heading shots; the heading test also passed in the run).
- [ ] No pill-more overlaps a pill; badge below every bar; counts match the day list. (The overflow test is earlier in the file and passed, but it was not re-checked by a full green run.)
- [ ] Open panel at 768/1024/1280 names at least 36 px; list items at least 200 px. (Failed at 768 closed state; 1024/1280 not run.)
- [ ] Month, Week, Year, navigation and keyboard focus checked. (Week, Year, focus tests not run.)
- [ ] Event filtering, dates, occupancy, spans and fetching untouched. (Not re-checked in this run.)
- [ ] Design-system checklist (docs/design/design-system.md) ticked. (Not done.)

## Deviations
- HEAD at start was 61508ab4 (brief commit on top of de537cb3). Worked on top of it.
- Step 4 changed a bound in an existing test (line 335, 184 to 226) on the orchestrator's approval, with the comment above it.
- Created App/.venv symlink to the 0978 venv (git-ignored) in an earlier batch step.
- Tracked PNG tests rewrite (docs/tasks/screenshots-0908/week-1280.png) were reverted with `git checkout` after each run; nothing staged.

## Questions
1. The 768 closed-state name check: is the narrow name a real fragment (a one-night bar under 36 px in a week above 687 px) or a test-state issue? Output shows only the first six widths. Suggest a run with `-vv` or a probe that lists all `.cal-pill-name` widths at 768 after the file's earlier tests.
2. The 0967 test order makes the 768 closed-state check depend on earlier tests in the file (passes alone, fails in file order). Accept as a test-isolation fix, or require a fix in the CSS?

## Owner steps left
None. No push, PR or merge was done.
