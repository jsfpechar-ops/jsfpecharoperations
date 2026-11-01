# 0471: remove the phone top bar; the bottom tab bar is the only phone chrome
Status: on hold until the Go migration is done (owner, 2026-11-01); re-check paths against the Go templates before running
Depends on: none | Base commit: main 0ee0152 | Branch: claude/project-thread-hm2s1w
Executor: Haiku 5.5 | Fits one session: 25 tool calls, 60k tokens
## 1. Objective
Owner, 2026-11-01: "just sidebar, no upper bar". Desktop already has only the sidebar. On phone (below 1024 px) the host app shows a 52 px top bar (`_shell_topbar.html`: logo, environment badge, search icon) above every page, plus the bottom tab bar. Remove the top bar so a phone page starts with its own heading, like a simple consumer app. Nothing is lost: search is the first row of the More sheet (`_shell_tabbar.html`), and practice mode keeps its red banner (`_env_banner.html`); production stays quiet.
## 2. Context
- `App/app/templates/base.html:37` includes `_shell_topbar.html`.
- `App/app/static/host2.css`: `.ui-topbar` rules at lines ~285 (hide on desktop, keep `.ui-tabbar` there), ~329-330 (phone layout), ~669 (safe-area padding), ~1113 (`view-transition-name: host-topbar`), ~1116-1117 (`host-topbar` entries in the reduced-motion view-transition lists).
- `--topbar-h` stays: `.ui-brand` (sidebar wordmark row, host2.css:272) uses it and `test_design_tokens.py` lists it.
- Tests: `App/tests/test_design_shell.py:11` asserts the top bar exists. `App/tests/test_host_feedback_browser.py:272` comment names the topbar icon.
- Docs: `docs/design/MASTER.md` §6.2 item 5; `docs/design/catalog.json` entry `"ui-topbar"`; `docs/design/pages/havel.md:15` names `_shell_topbar.html` as a Havel launcher (stale: the top bar has no Havel button).
## 3. Files
Delete `App/app/templates/_shell_topbar.html`. Edit `App/app/templates/base.html`, `App/app/static/host2.css`, `App/tests/test_design_shell.py`, `App/tests/test_host_feedback_browser.py` (comment only), `docs/design/MASTER.md`, `docs/design/catalog.json`, `docs/design/pages/havel.md`. Write `docs/tasks/0471-report.md` and the screenshots under `docs/tasks/screenshots-0471/`. Nothing else.
## 4. Steps
1. Delete `_shell_topbar.html` and its include line in `base.html`.
2. host2.css: line ~285 becomes `.host-workspace .ui-tabbar { display: none; }`. Delete the two `.ui-topbar` rules at ~329-330 and the one at ~669. Delete the `.ui-topbar { view-transition-name: host-topbar; }` rule and remove only the `host-topbar` items from the two selector lists at ~1116-1117 (keep `host-rail` and `host-tabbar`). If a media block becomes empty, delete it. Bump the `host2.css?v=` query in `base.html` to `20261101-0471`.
3. Check the phone page top: at 390 px the first content must not touch the screen edge. If `main` had no top padding because the bar gave it, add `padding-top: var(--space-4)` to the existing phone rule for `.host-workspace main.with-sidebar` (or the rule that sets phone `padding-bottom` for the tab bar). Add no new selector if an existing one fits.
4. `test_design_shell.py`: replace the line-11 assertion with `assert 'class="ui-topbar"' not in page`, and in the module docstring drop "top bar". Also assert the More sheet still offers search: `assert 'class="ui-menu-item" type="button" data-command-open' in page`.
5. `test_host_feedback_browser.py:272`: comment becomes `# v2 shell: the palette opener is the sidebar search row (desktop) or the More sheet row (phone).` Change no code.
6. MASTER.md §6.2 item 5: `5. The slide-out sidebar is removed on phone and there is no top bar: a page starts with its own heading. Search is the first row of the More sheet; practice mode shows the environment banner.` catalog.json: remove the `"ui-topbar"` entry (keep the JSON valid). havel.md:15: remove `` `_shell_topbar.html` (left of search), ``.
7. `grep -rn "topbar" App/app App/tests docs/design | grep -v topbar-h` must return nothing except the `host-tabbar`-free leftovers you removed; fix any remaining reference.
## 5. Do not touch
`_shell_sidebar.html`, `_shell_tabbar.html`, `shell.js`, `tokens.css`, any route or Python in `App/app/`. Admin navigation belongs to another brief.
## 6. Commands
From `App/`:
- `.venv/bin/python -m pytest tests/test_design_shell.py tests/test_design_tokens.py -q --tb=short -x 2>&1 | tail -15`
- `.venv/bin/python -m pytest tests/test_host_geometry.py tests/test_host_feedback_browser.py tests/test_design_guardrails_browser.py -q --tb=short -x 2>&1 | tail -15` (0 skipped)
From the repo root: `python3 scripts/context_lint.py | tail -3`; `python3 -c "import json;json.load(open('docs/design/catalog.json'))"`.
## 7. Acceptance
All commands pass with 0 skipped. No `ui-topbar` in rendered host pages. 390 px screenshots of `/` (dashboard) and `/reservations` signed in, saved as `docs/tasks/screenshots-0471/dashboard-390.png` and `stays-390.png`: page heading at the top, no bar above it, tab bar at the bottom.
## 8. Stop and ask
Stop if a geometry or browser test fails for a reason other than the removed bar, or if step 3 needs more than one CSS line.
## 9. Report
`docs/tasks/0471-report.md`: pytest tails, `git diff --stat origin/main`, the two screenshot paths.
