# 0395 report: Havel panel above sticky page rows; no stale start screen restore

Status: review
Executor: Haiku 5.5 | Branch: claude/0395-havel-panel-layer | PR #520

## Files changed

- App/app/static/host2.css: `.havel-dialog` gets `z-index: var(--z-popover)` at every width; the two phone `--z-drawer` declarations removed
- App/app/static/havel.js: `restore()` puts saved thread HTML back only when it holds `havel-msg-host`
- App/app/templates/base.html, App/tests/static_versions.json: host2.css and havel.js `20261025-0395`
- App/tests/test_0395_havel_panel_layer_browser.py: calendar hit-test at 1280, z-index at 390, stale start screen vs saved conversation
- docs/tasks/screenshots-0395/: panel-calendar-1280.png, panel-390.png

## Commands (last lines)

- ruff: All checks passed. node --check: ok. design lint: OK
- §6 pytest set: 160 passed, 0 skipped

## Deviations

- The calendar test uses the `calendar_workspace`/`calendar_origin` fixtures (plain `/` for the default seed shows no gantt header); the orchestrator answered the executor's §8 question.
