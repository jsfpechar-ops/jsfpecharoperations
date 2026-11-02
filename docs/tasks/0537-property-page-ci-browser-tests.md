# 0537: property pages on v2: fix the CI browser tests, take the 0536 screenshots
Status: todo
Depends on: 0536 (this branch, merged with 0724) | Branch: claude/project-thread-819gyo
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
CI on this branch has browser failures in tests that still look for the old properties list and property page markup. Point them at the new v2 markup (list: `.props-card` table and `.props-phone a.card.prop`; property page: one scroll page of `details.prop-sec#sec-<key>`, `aside.preview .pv`, `.savebar`). Then take the screenshots step 5 of 0536 left open.

## 2. Context
Failing in CI (shards 1 and 3, run 41342999192), grouped by file. Each failure gives its cause:
- `test_door_code_window_browser.py` (26): the door-code window now sits inside `details#sec-lock`, and tests assert `!el.closest('details')`; one asserts `folded: True` must be False. Open `#sec-lock` first (or use `?view=settings&section=lock`, which opens it on the server), then drop the "not inside details" assert.
- `test_onboarding_wizard_browser.py` (14, `test_wizard_polish_and_overview_cards`): the overview cards part looks for the removed health cards. Keep the wizard part and point the overview part at the aside `.pv` rows. Do not touch the wizard itself.
- `test_host_help_browser.py` (4): help tips on the property page are now an inline grey hint (0536 item 6, `.help-tip-btn` hidden on v2 inside `details`). Assert the hint text is visible under the input; the button tests run on another page that still has the button, or skip the property page in the page list.
- `test_0199_phone_geometry_browser.py` (2: KeyError 'E', "no property rows on /apartments"), `test_0281_card_borders_browser.py`, `test_host_list_cards_browser.py` ("no list panel"), `test_host_wide_geometry_browser.py` (2: lane `.panel.tight.scroll-x, .panel.empty` missing; fee backlinks lane): use `.props-card` from 1024 px and `.props-phone .card.prop` below.
- `test_0396_leon_opt_in_browser.py` (2): `a.host-property-card[data-leon-card]` and `.host-property-grid` are gone; the Leon state is now a row in the aside (`.pv .r` that links to Leon).
- `test_0284_states_browser.py`, `test_0251_tablet_browser.py`, `test_lock_navigation_browser.py` (`test_lock_setup_flow_keeps_its_place`), `test_wp28_geometry.py` (2), `test_host_quiet_dashboard_browser.py`, `test_0503_page_inits_once_browser.py` (2), the calendar remove button test, the operator signature test: read each failure; if it is about the property list or page markup, update the selector or assert; if it is about another page, list it and leave it.
- Not ours, list only: `test_0710_v2_mockup_match_browser.py` overview-320/390, `test_design_guardrails_browser.py` (layout guard, padded setup card), `test_0705_v2_shell_browser`.
- To find the failure text fast: run one file at a time with `--tb=line`.

## 3. Files
The tests listed above only (section 8 rule). No app or template change unless a test shows a real bug in this branch's pages: then stop and report it. Screenshots: `docs/tasks/screenshots-0536/app-1280.png` (full page) and `app-1024.png` of `/apartments/<first id>?lang=cs`. Use the method in the "0535 steps 5-6" section of `docs/tasks/0534-report.md`. If its fixture setup errors, copy the client/host setup that `tests/test_0534_property_page_v2.py` uses into a temporary script outside the repo, and do not commit it. Report: new section "0537" in `docs/tasks/0534-report.md`.

## 4. Steps
1. Door-code and help tests. Commit.
2. List and geometry tests. Commit.
3. Leon, wizard and the rest. Commit.
4. Run section 6. Commit.
5. Screenshots. Commit.

## 5. Do not touch
App code, templates, CSS, JS, the wizard, other pages, the 0710 comparison logic. No new dependency.

## 6. Commands (from `App/`)
`export UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`, then each changed file `-q --tb=short -rfs -p no:cacheprovider 2>&1 | tail -30`, then `tests/test_0534_property_page_v2.py tests/test_0530_properties_chips.py tests/test_0710_v2_mockup_match_browser.py`, then `.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841 | tail -5`, then from the repo root `python3 scripts/design_lint.py | tail -3` and `python3 scripts/context_lint.py 2>&1 | tail -3`. Restore stray tracked PNGs outside `screenshots-0536/`.

## 7. Acceptance
Every listed test that is about the properties pages passes, with 0 skipped. Not-ours tests are listed with their failure line.

## 8. Stop and ask
Standing rule: tests that assert the removed property tabs, views, health cards, old list panels or old class names may get new selectors or asserts (assertion or selector only; list each). A test may be deleted only if it tests nothing but removed markup; list it. Stop if a save/POST test fails or a test shows a real layout bug on the new pages (report the numbers).

## 9. Report
Section "0537" in `docs/tasks/0534-report.md`: status, tails, the section 8 list, the not-ours list. Stage by name, never `git add -A`; never commit `App/.venv`. Do not push. If out of calls, commit what passes and list what is left.
