# 0987 report

Status: blocked

## Run 1

Done: steps 1 to 4. Left: step 5 (lock tab, blocked, see Questions), steps 6 to 10.

### Files changed (committed)
- `App/app/templates/partials/settings_back_header.html`: main's version (help back inside the h1).
- `App/app/templates/dashboard.html`: non-calendar branch uses main's single h1 (`ph-hide` span with title and page_help, `ph-only` span).
- `App/app/templates/_components.html` (page_help macro): wrapper span no longer carries `data-how`; the `<div class="page-help-body">` sits inside `<details>` as on main. Needed because the test counts `data-how=` == 1 and expects the `<li>` steps before `</details>`.
- `App/tests/test_0534_property_page_v2.py`: 2 pins changed, `class="form prop-form-single"` to `class="form prop-form-single property-detail"` (old, new). Class stays in the template.

Not changed: `app2.css`, so no cache-key bump. The `.airbnb-header>.page-help` rules (lines 1845-1847, 2379) are kept: `reservation_detail.html` line 29 still passes `help_after=page_help('stay')`, so they are not dead. Callers of the partial: 17 templates (grep `settings_back_header`).

### The 15 CI tests
- test_0534 x2: pass (pin change, step 4).
- test_design_dashboard: pass (dashboard h1).
- test_page_help_0277 x3: pass (macro and dashboard h1).
- test_signed_in_chrome: pass (dashboard h1).
- test_host_redesign x2: pass (dashboard h1 and partial).
- test_ttlock_setup_0954 x4: FAIL, not fixed.
- test_door_code_missing_times_0397: FAIL, not fixed.
- test_door_code_one_lock_one_property: FAIL, not fixed.
Result: 9 pass, 6 fail.

### B command (last 5 lines)
FAILED tests/test_ttlock_setup_0954.py::test_state_block_matches_the_state[on]
FAILED tests/test_ttlock_setup_0954.py::test_state_block_matches_the_state[off]
FAILED tests/test_ttlock_setup_0954.py::test_state_block_matches_the_state[offline]
FAILED tests/test_ttlock_setup_0954.py::test_state_block_matches_the_state[times]
6 failed, 81 passed in 7.89s

ruff (last lines): All checks passed!

Not run: non-browser full run, browser commands, section 6 lint (context_lint, design_lint). No screenshots for part A (none required yet).

## Questions (owner decision needed)
1. Lock ids vs pins: `_property_editor.html` lines 432, 446, 485 put `id="lock-connected-off"`, `id="lock-setup-state"`, `id="lock-unavailable"` between `class` and `data-state`. The pinned regex (`test_ttlock_setup_0954.py` line 40s, `test_door_code_missing_times_0397.py` line 44) needs `<div class="lock-state" data-state="X" role="status">` with no id in between. Moving the id after `role` also fails (tried, reverted, not committed). Browser tests (`test_ttlock_setup_0954_browser.py:65`, `test_host_property_controls_browser.py` 746-799) select these ids. Both cannot hold without changing a pin or a selector.
2. Form on the "off with account" state: `test_door_code_one_lock_one_property.py` line 198 expects `action="/apartments/<id>/door-codes"`. The branch (0984) shows the setup row with no form in state `off` with a TTLock account, while main has the form. Restoring main's form reverses 0984, which is a product decision, so I did not change it.

## Run 2

Status: blocked
Done: amendment items 1 to 3 (lock tab), steps 1 to 7 (parts A to D). Left: F (see below), E (no CSS changed, so no cache bump), screenshots, report review.

### Lock tab (amendment, final owner decision)
- `_property_editor.html`: condition now `{% if door_code and door_code.account and door_code.locks %}`; the 0984 comment line above it deleted. Connected lock with codes off shows main's "Turn on" row; "Connect my lock" is for first-time setup only.
- Pins: regex allows the id in `test_ttlock_setup_0954.py` (line 53) and `test_door_code_missing_times_0397.py` (line 44): `<div class="lock-state"(?: id="[^"]+")? data-state=...`. Nothing else changed in those files.
- `test_door_code_one_lock_one_property.py`: restored to main's form assertion (an intermediate "row" assertion was reverted per the owner's last message).
- Item 3: not needed; the 0984 browser test was in the browser run and was not among the failures.
- Part B command: 87 passed, 0 failed (8 files).

### Commits (branch codex/ux-remediation-handoff)
- cce555b4 and e1d14824 (intermediate lock-tab commits, superseded), d2b8c420 (owner decision: final lock state), 55a6aecd (step 6, stays copy), c62c2cd3 (step 7, alert).

### Step 6 (part C, stays copy)
- `reservations.html`: lines 101-105 (overdue_scope block and data-stays-overdue-note paragraph) deleted. `grep overdue_scope` prints 0.
- i18n: `stays.chip.upcoming` restored to main in en, cs (host_i18n.py) and vi (host_vi_i18n.py). `stays.scope.overdue_note` removed from the three files. `stays.grp.overdue` kept. uk file: not present in the repo, nothing to change.
- Tests: `test_0285_rows_browser.py` line 33 label to `Upcoming &amp; current`; `test_host_filter_panels_browser.py` SCOPE_LABEL to main's texts, SCOPE_NOTE dict deleted, note assertions deleted (the `in page` assert, the `not in` loop over four URLs, `note`/`noteBox`/`noteInside` in the geometry JS and its assert). Overdue stay visibility asserts kept.
- Command: `pytest tests/test_0285_rows_browser.py tests/test_host_filter_panels_browser.py -k "stays or overdue or scope or rows" -q --tb=short -rs` gave 8 passed, 0 skipped.
- Test function name `test_default_stays_tab_label_names_overdue_and_the_note_only_shows_there` left unchanged (name only).

### Step 7 (part D, alert)
- `_host_alerts.html`: removed `compact_page or` from the "Open the stay" condition. The label now shows on /settings. No screenshot taken yet (see Left).

### Part F: verification
- `ruff check app tests tools --select E9,F63,F7,F82,F401,F841`: All checks passed!
- `python3 scripts/design_lint.py`: OK.
- `python3 scripts/context_lint.py`: OK.
- Browser set (`test_layout_lint_browser.py`, `test_0786_settings_geometry_browser.py`, `test_host_property_controls_browser.py`, no -x): 9 failed, 53 passed in 320.84s, 0 skipped listed. All 9 failures are `test_0786_settings_geometry_browser.py::test_0972_property_h1_stays_short_while_its_help_is_open` (en/cs x 390/768/1280 and more): `no .page-help-wrap .page-help > summary beside the property H1`. Cause: the restored main partial puts the help inside the h1 (run 1 step 2), so the test's "summary beside the H1" pin no longer matches. Not fixed; this needs a decision (update the pin to main's markup, or keep the outside help).
- Not run: the non-browser full run (`pytest tests -q -x --ignore-glob='*browser*'`), the `test_0710_v2_mockup_match_browser.py` command, and the 0390 screenshots.
- `docs/context/decisions.md` shows a local modification that is not from this run; it is not committed here.

### Questions
1. test_0972 pin: keep main's help inside the H1 (then update the 0786 pin) or keep the outside help (then the partial stays on the branch version)?

### Owner steps left
- None until F is green. Then the 390 screenshots (`/tmp/shots-0987/layout-lint/`) go to `docs/tasks/screenshots-0987/`.
