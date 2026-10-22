# 0247 report: Round 2 verification

Status: review
Executor: Haiku 5.5 | Brief: docs/tasks/0247-round2-verification.md

## Files changed

- `docs/tasks/0247-report.md` (this report, new)
- `docs/tasks/0247-round2-verification.md` (Status line only: todo to review)
- No App/ file changed. Screenshots written outside the repo under `/mnt/project-files/foolproof-round2/{en,cs,vi}/`.

## Commands (last lines)

Step 2, browser and geometry tests (14 files, `-rs`):
```
........................................................................ [ 50%]
........................................................................ [100%]
=============================== warnings summary ===============================
...fastapi/testclient.py:1: StarletteDeprecationWarning ...
144 passed, 1 warning in 765.02s (0:12:45)
```
Skipped: none listed by `-rs`. Result: 144 passed, 0 skipped.

Step 3, non-browser round 2 tests (14 files):
```
...
tests/test_host_i18n.py::test_a_signed_out_page_ignores_the_vietnamese_cookie
  ... return super().request(
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
163 passed, 3 warnings in 14.73s
```

Step 4, screenshots (`shots.py`, 7 pages, widths 390/1280/2000):
- en: `35 shots, 0 with problems`
- cs: `35 shots, 0 with problems`
- vi: `35 shots, 0 with problems` (the tool did not refuse `--lang vi`)

## Geometry problems

- en: none (35 shots, 0 problems)
- cs: none (35 shots, 0 problems)
- vi: none (35 shots, 0 problems)

## Stylesheet key check (stale-cache pass)

Every shot in all three languages lists `/static/workflow.css?v=20261022-0246` in `sheets`. Result: no stale stylesheet found.

## Image notes (EN, looked at once each)

- `reservations-1-390.png`: The alert stack, the stay header, the "Next step" card, the guest card, police reporting and stay settings all render in one column. The long alert text wraps cleanly and the red and amber icons align. No cut text, no overlap.
- `reservations-1-1280.png`: The alert strip sits above the stay header with the sidebar open. Police reporting shows the "4 days left" and "Incomplete" tiles side by side. No overlap or cut text. The page has the expected whitespace under police reporting.
- `apartments-1-390.png` (brief named `apartments-1-setup-door-lock-390.png`, which does not exist in the folder): The property overview shows the "Health check" card with the "All set" badge at the bottom. No cut text or missing strip. The health check card is visible on this page, so the wizard card is not in the way.

## Deviations

- Step 6 file name: the brief's `apartments-1-setup-door-lock-390.png` does not exist. I used `apartments-1-390.png`.
- Collapsed-sidebar shots exist only at 1280 and 2000 px (the tool's choice). The 390 px shots are open-sidebar only.
- `/mnt/project-files/foolproof-round2/` also contains a `dashboard` folder that is not one of the language folders. I did not inspect it or change it.
- Step 7 (worktree removal) ran. `git worktree list` shows only the main checkout.
- Untracked `docs/tasks/0102-evidence/*` files were present before this run. They are not in this commit.

## Questions

None.

## Owner steps left

None.
