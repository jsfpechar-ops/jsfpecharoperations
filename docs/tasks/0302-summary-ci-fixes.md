# 0302: Property summary: copy-button names and table width (CI red on PR #442)

Status: review
Depends on: 0301 | Base commit: db981ca | Branch: claude/project-thread-1am307 (already checked out; commit here)
Executor: Haiku 5.5 | Fits one session: 12 tool calls, 25k tokens

## 1. Objective

CI `test` fails in `App/tests/test_properties_inline_controls_browser.py` (passes on main):
(a) `test_full_url_pin_and_icon_actions_render` wants `<span class="sr-only">Copy link</span>` inside each copy button; 0300's `copy_button` macro dropped that span.
(b) `test_summary_fits_every_width_both_languages_rail_states` at 1024 px, en, rail open: the summary table is 5 px wider than its panel, because 0296 added a 93 px actions column (Open). The timing cell's `min-width: 20.5rem` (host.css 0098) leaves no room.

## 2. Context

`App/app/templates/_components.html` line ~293 (verbatim):
```
          aria-label="{{ label or t('common.copy') }}">{{ icon('copy', 16) }}<span class="btn-icon-label" data-copy-label-slot hidden></span></button>
```
host.css: `.host-workspace .property-summary-table td.property-inline-timing { min-width: 20.5rem; }`

## 3. Files

| Path | Action |
|---|---|
| App/app/templates/_components.html | edit that one line |
| App/app/static/host2.css | append one block |
| App/app/templates/base.html | host2 key `?v=20261024-0302` |
| App/tests/static_versions.json | `--write` |

## 4. Steps

1. In that line, directly before `</button>`, insert `<span class="sr-only">{{ label or t('common.copy') }}</span>`.
2. Append to host2.css:
   ```css
   /* 0302: the summary table's Open column (0296) needs room at 1024 px with the rail open. */
   .host-workspace .property-summary-table td.property-inline-timing { min-width: 18.5rem; }
   ```
3. Bump the host2 key, run `.venv/bin/python tests/test_static_versions.py --write` from `App/` (or the `--write` way the test file documents).

## 5. Do not touch

Everything outside §3. No other CSS values.

## 6. Commands

From `App/`:
```
.venv/bin/python -m pytest tests/test_properties_inline_controls_browser.py tests/test_static_versions.py tests/test_0252_touch_sweep_browser.py tests/test_host_wide_geometry_browser.py -q --tb=short 2>&1 | tail -20
.venv/bin/ruff check . 2>&1 | tail -5
```
If a test still fails, put its first assertion line in the report and stop (do not try other values).

## 7. Acceptance

- [ ] The §6 commands pass, or the failure is in the report.

## 8. Stop and ask

As in TEMPLATE §8.

## 9. Report

`docs/tasks/0302-report.md` (150 tokens), `Status: review`. One commit `0302: summary copy names and table width`. Do not push.

## Report

Executor commit 118f11f did steps 1-3; Czech at 1024 px still overflowed by 10 px, so the orchestrator added `td:first-child { min-width: 8rem; }` (key 0302b). §6 tests: 29 passed.
