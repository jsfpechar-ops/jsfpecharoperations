# 0989: PR #790: entity card buttons sit in their own row, text centred

Status: todo
Depends on: 0988 | Base commit: origin/codex/ux-remediation-handoff | Branch: codex/ux-remediation-handoff
Executor: Haiku 5.5 | Fits one session: 15 tool calls.

## 1. Objective
On /entities (Business & legal details) at phone width the "Edit" and "Invoice settings" buttons look like they float: the buttons are 44 px tall but their text sits at the top of the pill, and the row is glued to "Properties 2" above it. Owner wants them fixed.

## 2. Context
CSS in App/app/static/app2.css ~lines 1715-1729 (`.entities-page` stacked table under 1024 px). Line 1729 sets `height:44px` on `td.row-actions .ui-btn` but the button is not a flex box, so its label is not vertically centred.

## 3. Files
App/app/static/app2.css, App/app/templates/base.html (cache key), App/tests/static_versions.json, docs/tasks/0989-report.md, docs/tasks/screenshots-0989/.

## 4. Steps
1. `git fetch origin codex/ux-remediation-handoff | tail -3 && git checkout -B codex/ux-remediation-handoff origin/codex/ux-remediation-handoff | tail -3`.
2. In app2.css, after line ~1729 add exactly:
   `body.v2 .entities-page td.row-actions .ui-btn{display:inline-flex;align-items:center;justify-content:center;line-height:1.2;padding-top:0;padding-bottom:0}`
   and inside the `@media (max-width:1023px)` stacked-table block (next to line ~1723):
   `body.v2 .entities-page>table.ui-table td.row-actions{margin-top:8px;padding-top:12px;border-top:1px solid var(--line)}`
3. Cache key for app2.css in base.html to `20261106-0989`; from App/: `.venv/bin/python tests/test_static_versions.py --write | tail -3`.
4. Verify (section 6). Copy `/tmp/shots-0989/layout-lint/operators-390.png` and `invoice-settings-390.png` to docs/tasks/screenshots-0989/.
5. Report, Status, commit `0989: entity card buttons centred in their own row`, push `git push -u origin codex/ux-remediation-handoff` (no force, never main).

## 5. Do not touch
Anything else.

## 6. Commands
From App/: `.venv/bin/python -m pytest tests/test_static_versions.py -q | tail -3`; `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots-0989 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q --tb=line -rs | tail -8`; `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k "operator or entit" -q --tb=line -rs | tail -8`. Repo root: `python3 scripts/design_lint.py | tail -2`.

## 7. Acceptance
- [ ] All commands 0 failed, 0 skipped.
- [ ] operators-390.png: button labels centred, a line above the button row, 12 px or more between "Properties" and the buttons.

## 8. Stop and ask
A v2_mockup pin for `.row-actions` fails: set it to the measured value with `# 0989`. Anything else fails: stop and report.

## 9. Report
docs/tasks/0989-report.md, 150 tokens: Status, commit, counts, screenshot names.
