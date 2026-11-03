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

## 10. Addendum (0811b): calendar cleaning chips

- `App/app/static/dashboard-calendar.js` line 229: broom `d` replaced with SPARKLES paths. Nothing else changed in the file.
- `App/app/templates/_dashboard_calendar.html` line 170: `?v=20261023-clean-url` → `?v=20261102-0811`.
- `App/tests/static_versions.json` regenerated with `tests/test_static_versions.py --write` (41 files; only dashboard-calendar.js changed).
- Tests: `tests/test_static_versions.py tests/test_0710_v2_mockup_match_browser.py -k "static or cleaning"` → 15 passed, 0 skipped.
- Tests: `tests/test_0199_phone_geometry_browser.py tests/test_0252_touch_sweep_browser.py tests/test_dashboard_calendar_browser.py` → 18 passed, 0 skipped.
- Screenshot: `docs/tasks/screenshots-0811/cleaning-1440.png` recaptured (sparkles chips).
- Deviations: `git clean` of untracked `docs/tasks/screenshots-0710/` files was denied by the auto-mode classifier, so those untracked PNGs remain on disk (not committed). Tracked 0710 PNGs were restored.

## 11. Addendum (0811c)

- Changed files (`git diff a933a5b~5 --stat`): `App/app/templates/_icons.html`, `_shell_sidebar.html`, `_shell_tabbar.html`, `_shell_v2.html`, `menu.html`, `App/tests/test_design_icons.py`, `App/tests/test_design_shell.py`, `docs/design/MASTER.md`, `docs/design/mockup/ubyhost-phone-v2.html`, `docs/design/mockup/ubyhost-redesign-v2.html`, and the four PNGs in `docs/tasks/screenshots-0811/`. 14 files, 25 insertions, 25 deletions.
- Tests: `tests/test_design_icons.py tests/test_design_shell.py tests/test_0710_v2_mockup_match_browser.py tests/test_design_guardrails_browser.py tests/test_0728_menu_geometry_browser.py tests/test_0705_v2_shell_browser.py tests/test_host_ux_acceptance.py`: 158 passed, 0 skipped.
- Screenshots (390 px and 1024/1440 px, recaptured after the icon change):
  - `docs/tasks/screenshots-0811/cleaning-1440.png`
  - `docs/tasks/screenshots-0811/cleaning-390.png`
  - `docs/tasks/screenshots-0811/menu-390.png`
  - `docs/tasks/screenshots-0811/menu-1024.png`
- `docs/tasks/screenshots-0710/`: tracked PNGs restored with `git checkout`, untracked PNGs removed. The folder is clean.
