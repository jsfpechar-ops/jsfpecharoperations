# 0789a2: finish part A (settings index + sub-pages)

Status: todo. Executor: Haiku 5.5, alone, branch `claude/project-thread-umes84`. Context: 0789a brief and its hand-back (commits ea522fe..82ad1a1). Do these, in order:

1. **Back button position (decision):** at every width the back button sits at the left edge of the 720 settings lane, not the viewport. Change the 0789 test: `back.x - lane.x` between 0 and 32 (lane = the element that holds the h1), and the h1 below it.
2. **Row height < 56 px at 390/768:** probe with Playwright `getComputedStyle` on the Account row and its parent; find which rule wins (likely an older `.settings-lane a`/list rule or the row is an inline element). Fix in the 0789a CSS block (e.g. `display:flex; align-items:center; min-height:64px` on the row element the test measures).
3. **Duplicate titles:** on a sub-page the back-header h1 is the only page title; hide or drop the old group h2 that repeats it (keep section h2s inside the group).
4. **Data requests:** `#settings-privacy-requests` must not render on /settings/data (the index row links to /privacy-requests).
5. **Unit test** (`App/tests/test_0789_settings_subpages.py`): logged in, `/settings` has the 9 rows with their hrefs; each `/settings/<group>` returns 200 and contains its section ids from brief 0789a §2; `/settings/archived`, `/entities`, `/privacy-requests` return 200.
6. **design_lint:** add the `airbnb-*` classes to `docs/design/catalog.json` the way existing classes are listed.
7. **Brief 0789 §6 test set:** run it, then fix each failure caused by the split: tests that fetch `/settings` and expect a section now fetch its sub-page (test_pwa, test_pwa_browser, test_operator_naming, test_settings_technical, settings geometry). For each remaining failure, run it on `git stash`-free clean main checkout? No: instead check `git show origin/main:<test file>` and whether it touches settings; if it fails for reasons unrelated to settings (e.g. a `missing_ok` KeyError), list it in the report with the error line, do not fix.
8. Report: append "Part A2" to `docs/tasks/0789-report.md` with the final test line of the §6 set and the 0789 test.

Do not restyle sub-page contents (part B). No app.js change. Commit, do not push.
