# 0069 report

Status: review  
Branch: `task/0069-same-period-shared-pin`  
PR: https://github.com/jsfpechar-ops/jsfpecharoperations/pull/375

## 1. Files changed (`git diff --stat` vs main)

```
 App/app/door_codes.py                   | 63 +++++++++++++++++++++++----------
 App/app/host_i18n.py                    |  4 +++
 App/app/mail_notify.py                  |  2 +-
 App/app/ttlock.py                       |  1 +
 App/tests/test_door_codes_safeguards.py | 48 +++++++++++++++++++------
 5 files changed, 89 insertions(+), 29 deletions(-)
```

Plus this report and brief status flip (`todo` → `review`).

## 2. Commands (last 5 lines)

`grep -n 'is_custom' app/door_codes.py` (from `App/`):

```
(no output)
```

`.venv/bin/python -m pytest tests/test_door_codes_safeguards.py tests/test_door_code_handover.py tests/test_confirmation_with_door_code.py tests/test_ttlock.py -q`:

```
=============================== warnings summary ===============================
...
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
70 passed, 1 warning in 2.07s
```

`.venv/bin/python -m pytest tests -q`:

```
FAILED tests/test_host_wide_geometry_browser.py::test_host_wide_lanes_align
FAILED tests/test_host_wide_geometry_browser.py::test_stay_row_actions_fit_midwidth_lanes
FAILED tests/test_host_wide_geometry_browser.py::test_collapsed_sidebar_keeps_dashboard_and_stays_lanes_aligned
6 failed, 3147 passed, 5 skipped, 7 warnings in 448.76s (0:07:28)
```

Also failed (same six on `main`, re-run confirmed):  
`test_host_copy_feedback_truth_and_geometry`,  
`test_dashboard_geometry_locales_and_screenshots`,  
`test_stays_guest_link_copy_is_status_independent_and_token_guarded`.

`python3 scripts/context_lint.py`:

```
WARN  1 commit(s) touched App/ after the last status.md update. Orchestrator: update docs/context/status.md at review.
next free: task 0070 | migration 0010
context lint: OK
```

## 3. Acceptance (§7)

- [x] The grep gives no output.
- [x] The three new tests pass, and the door-code test files pass.
- [x] The full suite passes, or only failures that also fail on `main` remain (named above; CI decides).
- [x] `git diff --stat` lists only the files in §3 (plus report/brief status).

## 4. Deviations

None. §3 exception (fake `create_period_code` id tweak in other tests) was not needed.

## 5. Questions

None.

## 6. Owner steps left

1. Open PR #375 and check that CI is green.
2. Merge with `scripts/merge-pr-on-green.sh 375`.
3. Optional staging check from the brief: two same-window stays; cancel the first with gateway unplugged; second guest gets a different code and the host gets "an old door code still covers the stay".
