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
