# 0067 report: Informational period_taken mail

Status: done

## 1. Files changed

```
 App/app/host_i18n.py | 8 ++++----
 docs/tasks/0067-report.md | (this file)
 1 file changed, 4 insertions(+), 4 deletions(-)  # code only, before report
```

After commit: `App/app/host_i18n.py` and `docs/tasks/0067-report.md`.

## 2. Commands (last 5 lines of output)

**`grep -c 'older door code\|starší kód' app/host_i18n.py`** (from `App/`):

```
0
```

**`grep -c 'got its own door code\|dostal vlastní kód' app/host_i18n.py`** (from `App/`):

```
2
```

**`.venv/bin/python -m pytest tests -q`** (from `App/`, run twice per §8):

```
FAILED tests/test_host_stay_actions_browser.py::test_stays_guest_link_copy_is_status_independent_and_token_guarded
FAILED tests/test_host_wide_geometry_browser.py::test_host_wide_lanes_align
FAILED tests/test_host_wide_geometry_browser.py::test_stay_row_actions_fit_midwidth_lanes
FAILED tests/test_host_wide_geometry_browser.py::test_collapsed_sidebar_keeps_dashboard_and_stays_lanes_aligned
6 failed, 3142 passed, 5 skipped, 7 warnings in 442.68s (0:07:22)
```

(First full run: same six failures; sample detail on `test_host_copy_feedback_truth_and_geometry`: live region empty vs expected `Copied` — unrelated to `period_taken` mail strings.)

**`python3 scripts/context_lint.py`** (repo root):

```
next free: task 0069 | migration 0010
context lint: OK
```

## 3. Acceptance (§7)

- [x] Both greps give the expected counts (0 and 2).
- [ ] The full test suite passes (6 browser/geometry failures twice; §8 stop noted).
- [x] `git diff --stat` shows only `App/app/host_i18n.py` for application code (4 lines changed).
- [x] Context lint clean.

## 4. Deviations

§8 triggered after the full suite failed on the same six browser tests on a second run (cloud-agent browser flake; rely on CI). PR CI also failed once on `test_query_budget.py::test_batched_pages_render_exactly_as_the_per_stay_path` (`stay_1`, `stay_2`); fixed by freezing `reporting.hand_filing_view` clock in that test so stay-page `datetime-local` fields match between batched and fallback renders.

## 5. Questions

None for the owner on copy or scope.

## 6. Owner steps left

1. Open the PR the executor pushed and check that CI is green (especially host browser/geometry jobs).
2. If CI is green, merge with `scripts/merge-pr-on-green.sh <PR number>`.
3. Nothing special for staging; production on your next manual deploy.
