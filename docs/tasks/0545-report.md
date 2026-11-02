# 0545 report

Status: review

## Files changed
- App/app/routes/cleaning.py (`_context`: `cleaning_day`, `cleaning_short`)
- App/app/templates/_cleaning_table.html (Day and arrival cells)
- App/app/static/app2.css (cleaning block: 1024 px rules, 44 px kept below 1024)
- App/app/templates/base.html (`?v=20261101-0545`)
- App/tests/static_versions.json (`--write`)
- docs/tasks/screenshots-0545/cleaning-1280.png, cleaning-390.png
- docs/tasks/0545-report.md

No date assertions existed in test_0540_cleaning_tables.py or test_cleaning_browser.py, so no test edits were needed.

## Commands (last lines)
- `pytest tests/test_0540_cleaning_tables.py tests/test_cleaning.py -q`: `43 passed in 10.05s`
- `pytest tests/test_static_versions.py -q`: `3 passed in 0.15s`
- `pytest tests/test_0710_v2_mockup_match_browser.py -k "cleaning and (768 or 1024 or 1280 or 1440)" -q -rs`: `8 passed, 17 deselected in 12.74s`, 0 skipped
- `pytest tests/test_cleaning_browser.py tests/test_0252_touch_sweep_browser.py tests/test_0540_cleaning_tables.py tests/test_cleaning.py tests/test_static_versions.py -q -rs`: `1 failed, 72 passed in 88.39s`. The one failure is the known Overview "/" touch-sweep failure (`phone390` and `ipad820`, "Reserved" chips outside the box). Cleaning cases pass.
- `python3 scripts/design_lint.py`: `design lint: OK`

## Brief section 7
- [x] Cleaning cases at 768-1440 pass
- [x] Step 3 second set passes except the known Overview "/" failure
- [x] Lint OK
- [x] Screenshot exists

## Visible differences left (1280)
- The screenshot is English, not `lang=cs`. The screenshot helper does not set the language, so the brief's Czech short dates ("Po 3. 11.") are not visible in the shot. The cs output is covered by the code change only.
- The page is a full cleaning page (Today, This week, Later, calendar, legend). The mockup `clean` view is a single compact table with Czech labels and a different sidebar and header.
- Row height is now about 48 px (mockup about 46 px). The open cue is a small chevron, as specified.
- Pills read "Check the time", "Hours missing" and "Next arrival not scheduled" (English copy); the mockup has "Naplánováno" and "Chybí uklízečka".

## Deviations
- Step 3 generated 0710 screenshots as a side effect of `UBYHOST_SHOTS_V2=1`. They were restored with `git checkout` and `git clean` on `docs/tasks/screenshots-0710`, and nothing there was committed.
- No PR opened: the brief says do not push.
- The 390 px screenshot was saved but not re-inspected.

## Questions
- Should the cleaning screenshot helper set `lang=cs` so the shot matches the mockup language?

## Owner steps left
- Review the branch and open the PR (`claude/project-thread-c1h7ok`) when ready to push.
