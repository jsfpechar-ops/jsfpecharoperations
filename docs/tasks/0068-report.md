# 0068 report: TTLock host provider copy

Status: done

## 1. Files changed

```
 App/app/guide_i18n.py              |  8 ++++----
 App/app/i18n.py                    | 10 +++++-----
 App/app/routes/legal.py            |  3 +--
 App/app/subprocessors_i18n.py      | 23 ++++++++++++-----------
 App/app/templates/guide.html       |  2 +-
 App/app/ttlock.py                  |  2 +-
 App/tests/test_ttlock_host_provider.py | 43 +++++++++++++++++++++++++++++++++++++++++++
 docs/tasks/0068-screenshots/       |  9 PNGs (acceptance)
 docs/tasks/0068-report.md          | this file
```

## 2. Commands

```text
grep -rn 'subprocessors.ttlock_\|Standard Contractual Clauses for any transfer' app/
# (no output; exit 1)

cd App && .venv/bin/python -m pytest tests/test_ttlock_host_provider.py tests/test_privacy_legal_positions.py -q
  /workspace/App/.venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
10 passed, 1 warning in 0.81s

cd App && UBYHOST_BROWSER_EXECUTABLE=/usr/local/bin/google-chrome UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests -q
FAILED tests/test_host_wide_geometry_browser.py::test_stay_row_actions_fit_midwidth_lanes
FAILED tests/test_host_wide_geometry_browser.py::test_collapsed_sidebar_keeps_dashboard_and_stays_lanes_aligned
6 failed, 3145 passed, 5 skipped, 7 warnings in 435.76s (0:07:15)

python3 scripts/context_lint.py
next free: task 0069 | migration 0010
context lint: OK
```

## 3. Acceptance (§7)

- [x] The grep gives no output.
- [ ] Both test runs pass; browser and geometry tests ran with 0 skipped — **6 host browser/geometry failures** (same on `main` without this diff; `test_host_wide_geometry_browser.py::test_host_wide_lanes_align` checked on stashed tree). Suite also has **5 skips** unrelated to this brief (backup `age`, optional evidence/screenshot env).
- [x] Screenshots at 360, 390, 1280 px in `docs/tasks/0068-screenshots/`:
  - `guide-door-codes-en-{360,390,1280}.png` — `/guide` door-code terms (en)
  - `subprocessors-recipients-en-{360,390,1280}.png` — `/subprocessors?lang=en` recipients panel
  - `guest-privacy-door-codes-cs-{360,390,1280}.png` — guest privacy notice (cs, TTLock property)
- [x] `git diff --stat` lists only §3 code files plus this report and screenshots.

## 4. Deviations

None in copy or legal tuple move. Full-suite green is blocked by pre-existing host geometry failures in this cloud image, not by 0068 edits.

## 5. Questions

None.

## 6. Owner steps left

1. Open the PR and confirm CI.
2. Merge with `scripts/merge-pr-on-green.sh <PR number>`.
3. On Smart locks, accept the **2026-10-12** door-code terms if prompted.
