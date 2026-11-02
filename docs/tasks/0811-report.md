# 0811 report: sparkles cleaning icon

Status: review

## Files changed
- App/app/templates/_icons.html (brush-cleaning entry replaced by sparkles)
- App/app/templates/_shell_v2.html, docs/design/mockup/ubyhost-redesign-v2.html (cleaning nav svg)
- App/app/templates/_shell_tabbar.html, _shell_sidebar.html, menu.html, _cleaning_table.html (name only)
- App/tests/test_design_icons.py, App/tests/test_design_shell.py (name only)
- docs/design/MASTER.md line 158 (name only)
- docs/design/mockup/ubyhost-phone-v2.html (i-brush symbol contents, id kept)
- docs/tasks/screenshots-0811/ (4 PNGs)

## Tests
Command: `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_design_icons.py tests/test_design_shell.py tests/test_0710_v2_mockup_match_browser.py tests/test_design_guardrails_browser.py -q --tb=short -rs -k "icon or shell or cleaning or menu or guardrail"`
Tail: `76 passed, 61 deselected in 92.16s`. 0 skipped, 0 failed.

Lint: `python3 scripts/context_lint.py` FAIL, only on `docs/tasks/0811-cleaning-icon-sparkles.md needs a 'Status:' line`. The brief's own line says `Status: ready`, which the lint does not accept. Not changed here.

## Screenshots (390 px unless noted)
- docs/tasks/screenshots-0811/cleaning-390.png
- docs/tasks/screenshots-0811/cleaning-1440.png
- docs/tasks/screenshots-0811/menu-390.png
- docs/tasks/screenshots-0811/menu-1024.png

## Deviations
- Installed `playwright==1.63.0` into the local App/.venv only (CI does the same separately; it is not in requirements). No repo change.
- The brief's `grep` check for `brush-cleaning`/`M14 4l6 6` in App and docs/design prints nothing.
- Lint fail as above.

## Owner steps left
- Fix the brief's Status line if the lint must pass.
- Open the PR and merge via `scripts/merge-pr-on-green.sh`. Nothing pushed.
