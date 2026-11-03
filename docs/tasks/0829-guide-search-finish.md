# 0829 brief: finish the /guide search (0828)

Status: todo
Executor: Haiku 5.5, alone, in /home/claude/jsfpecharoperations on branch claude/project-thread-a41o7b (checked out; App/.venv exists). Do not commit, push, checkout, reset, stash or restore: the orchestrator commits.

## 1. Objective
0828 (committed) made /guide folded with a search field. Fix what is left red: design lint T1, Turbo page swap, test_guide_coverage, and the 0800/0813 geometry on /guide.

## 2. Context
Reports: `docs/tasks/0828-report.md`, `docs/tasks/0871-report.md`. The app uses Turbo page swap (`App/app/static/vendor/turbo-*.js`): a `<script src>` inside a page template does not run on swap, and design lint T1 forbids it. Host scripts are loaded once in `App/app/templates/base.html` (lines ~38-46) and bind per page with `onPage(fn)` (see `App/app/static/host.js` line ~11 and `App/tests/test_0507_page_hooks_browser.py`).

## 3. Files
`App/app/templates/guide.html`, `App/app/static/guide.js`, `App/app/templates/base.html` (one script line), `App/app/static/app2.css` (only the `/* 0828 guide search (v2) */` block at the end), `App/tests/test_guide_coverage.py`, `App/tests/test_0828_guide_search_browser.py`, `App/tests/test_0800_v2_remaining_pages_browser.py` (only if a selector names old guide markup).

## 4. Steps
Env (from App/): `export PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1`.
a. Remove the `<script src="/static/guide.js…">` from guide.html. Load guide.js in base.html next to host.js (`{% if show_nav | default(true) %}<script src="/static/guide.js?v=20261102-0829" defer data-turbo-track="reload"></script>{% endif %}`). In guide.js wrap the setup in the same `onPage` pattern as host.js and return early when `#guide-search` is absent; bind once per page (no duplicate listeners after a second initPage, like 0507). The hashchange listener on window must be added once only.
b. Add a browser test: navigate from /havel to /guide by clicking the sidebar Help link (Turbo swap), then typing in the search still filters.
c. `tests/test_guide_coverage.py::test_every_guide_section_is_known_to_havel`: its regex expects `<section class="guide-section`; update it to match the topic elements (`<details class="guide-section …" id=`), keeping what it checks.
d. /guide geometry at all 6 widths (0800 test): `section.workflow-block` overlaps `details.guide-section.card` by 30-114 px, and "main content ends under the tab bar". Probe the 5 lowest elements and the overlapping pair, then fix in the 0828 block (likely the closed details content keeps layout: hide `details:not([open])>:not(summary)` like the onboarding fix in the 0800 block, and give topics `display:block` with 12 px gap). Keep the 12 px neighbour rule.
e. Run commands, regenerate screenshots.

## 5. Do not touch
Guide copy, the subtitle line of guide.html (another executor removes it), other app2.css blocks, the cache keys except the guide.js one you add.

## 6. Commands
From App/, env above:
- `.venv/bin/python -m pytest tests/test_0828_guide_search_browser.py tests/test_guide_coverage.py tests/test_0507_page_hooks_browser.py -q --tb=line -p no:cacheprovider 2>&1 | tail -8` → 0 failed
- `.venv/bin/python -m pytest tests/test_0800_v2_remaining_pages_browser.py -k guide -q --tb=line -p no:cacheprovider 2>&1 | tail -8` → 0 failed
- `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -2` (it may refuse because app2.css changed under the same key: then leave it, the orchestrator bumps the key)
- repo root: `python3 scripts/design_lint.py 2>&1 | tail -3` → OK

## 7. Acceptance
Section 6 green (static versions may wait for the orchestrator).

## 8. Stop and ask
Stop at 30 tool calls.

## 9. Report
`docs/tasks/0829-report.md`: changes per step, final tails.
