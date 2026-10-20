# 0191: Comfy table rows (host list and tables)

Status: review
Depends on: 0189 | Base commit: f69218a | Branch: claude/project-thread-3xqb0b
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Owner (2026-10-20): rows on /reservations (Stays) are too compacted, with too much info in one small row. Make rows comfy and large, with just enough white space. Visible 1 px borders stay; tokens only; light mode; WCAG 2.2 AA.

## 2. Context

- `App/app/static/tokens.css`: `--row-h`, `--row-py`, `--row-px`, `--row-gap` (was 48 / 12 / 16 / 12).
- `App/app/static/host2.css`: `.ui-table td` (height and padding), `.ui-sub`, badges in cells, phone card roles (MASTER 7.3 and 7.4).
- `App/app/templates/_ui_layout.html`: the shared `ui-table` macro (Stays uses it).
- `App/app/static/host.css:66` `.host-workspace td { padding: 14px 16px }` is the legacy override for non-ui tables; not changed.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/static/tokens.css | edit | row tokens: 80 px row, 16 px vertical, 20 px horizontal, 16 px gap |
| App/app/static/host2.css | edit | td padding `--space-4` vertical; sub line gap; badge gap (desktop only) |
| App/app/templates/base.html | edit | cache keys tokens 0190a, host2 0190c |
| App/tests/static_versions.json | edit | sha and v for tokens.css and host2.css |
| docs/tasks/0191-comfy-rows.md | new | this brief |

## 4. Steps

1. Tokens and table CSS (done, commit "0191 comfy rows and design catalog classes").
2. Column padding kept at `--space-4` (16 px) horizontally: 20 px broke the invoices 1280 geometry (page-scroll 1289 > 1280).
3. Cache keys and hashes bumped.

## 5. Do not touch

Templates, Python, Stays markup, dense pages' own CSS (host.css legacy rules), host-design0123.css (no row rule found).

## 6. Commands

- `cd App && UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell .venv/bin/python -m pytest tests/test_design_shell_browser.py tests/test_design_shell.py tests/test_static_versions.py tests/test_a11y_guard_browser.py tests/test_design_guardrails_browser.py -q --tb=short -rs 2>&1 | tail -30`
- `python3 scripts/design_lint.py 2>&1 | tail -30`
- `python3 scripts/context_lint.py 2>&1 | tail -30`

## 7. Acceptance

- [x] Shell and guard browser tests: 26 passed, 0 skipped.
- [ ] Calendar-review job tests (not run in this session).
- [ ] Screenshots at 390 / 1280 / 2000 (not taken; out of budget).
- [x] design_lint OK on the committed HEAD (clean export).

## 8. Stop and ask

Column padding at 20 px needs a geometry threshold change in the invoices test; owner decides.

## 9. Report

Deviations: columns stay at 16 px horizontal padding; screenshots and calendar-review job not run. Left: owner review of Stays at 390/1280.
