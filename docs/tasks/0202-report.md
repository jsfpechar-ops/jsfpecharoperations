# 0202 report: Vietnamese phone geometry

Status: blocked

## Files changed (uncommitted)
- App/tests/test_0199_phone_geometry_browser.py: `("en", "cs")` changed to `("en", "cs", "vi")` in 3 loops.
- App/tests/test_0201_tabbar_safe_area_browser.py: lang parametrize adds "vi".
- Temporary sweep App/tests/test_zz_vi_sweep_browser.py: written, run, deleted (not committed).
- Screenshots copied to /mnt/project-files/design-reset/checkpoint-6/mobile/vi/: stay-ready, lock, cleaning-host, properties (tab bar) at 390 vi.

No CSS changed, so no `?v=` bump and no manifest regeneration.

## Faults found
- A (stay page buttons, vi): none. Stay tests pass in vi at 360/390.
- B (tab bar, vi): none. Labels fit on one line at 360 and 390. Widest is "Tổng quan" at 56 px in a 72 px column (78 px column at 390). Bar height unchanged at 56 px.
- C (0200 action rows, vi): none. Sweep at 360 and 390, 0 overflow, 0 wide buttons, 0 buttons escaping their container, 0 horizontal page overflow (sw == vw on all routes).

## Sweep (vi, 360 and 390)
Routes: /, /stay-fees, /apartments, /apartments/new, /invoices, /invoices/new, /submissions, /apartments/1?view=settings, /apartments/1/setup/calendar.

## Commands
- `.venv/bin/python -m pytest tests/test_0199_phone_geometry_browser.py tests/test_0201_tabbar_safe_area_browser.py tests/test_static_versions.py tests/test_design_guardrails_browser.py -q --tb=line -rs` gave `29 passed, 1 warning` with no SKIPPED lines.
- `python3 scripts/design_lint.py | tail -2` gave `design lint: OK`.

## Deviations
- Step 1 commit was refused by the permission classifier. The brief asks for per-step commits, but the owner's instructions say not to commit, so nothing is committed. The two test edits remain in the working tree.
- Done: steps 1 to 4. Left: commit and PR, owner decision.
- Not covered: operator add (route not located in App/app), invoice detail and submission detail (need seeded records). Dashboard tab-bar shot is the /apartments page, which carries the same tab bar.
- docs/tasks/0102-evidence shows pre-existing modified files in git status. They were not touched.

## Questions
- Should I commit and open the PR, or hand that to the owner?
- Which URL is the operator add page, and should invoice detail and submission detail be seeded for the sweep?

## Owner steps left
- Commit the two test files on claude/project-thread-xo8dql (message `0202 step 1`), then open the PR. The Haiku executor was not allowed to do this.
