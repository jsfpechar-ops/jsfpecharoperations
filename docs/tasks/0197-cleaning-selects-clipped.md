# 0197: Calendar month, year and property selects clip their text on the shared cleaning page

Status: done
Depends on: none | Base commit: fea8bee | Branch: claude/project-thread-xo8dql
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

On the shared cleaning schedule (`/cleaning/s/<token>`, template `cleaning_shared.html`) the calendar's "October", "2026" and "All properties" selects show only the top half of the text. Make them show the full text at every width.

## 2. Context

Cause: `App/app/static/dashboard-calendar.css` line 23 gives calendar selects `padding:4px 8px; font-size:12px` but only under `.host-workspace`. The shared page body is `.cleaning-public` with `<main class="cleaning-page">`, so the select keeps `app.css` defaults (`padding: 11px 13px; font-size: 15px; min-height: 42px`) while lines 186/202/255 force `height:36px` (44/46 px on phone). 36 px minus 22 px padding leaves no room for 15 px text.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/static/dashboard-calendar.css | edit | append one block (marked `/* 0197 */`) |
| App/app/templates/_dashboard_calendar.html | edit | `dashboard-calendar.css?v=20261020-0193d` -> `?v=20261021-0197` (and any other template with that key) |
| App/tests/static_versions.json | regenerate | `.venv/bin/python tests/test_static_versions.py --write` |

No other file may change.

## 4. Steps

1. Append:
   ```css
   /* 0197: shared cleaning page selects use the same compact box as the host calendar, so text is never clipped. */
   .cleaning-page .dashboard-calendar :is(.cal-heading,.cal-toolbar) select {
     min-width:0; width:auto; max-width:100%; margin:0; box-sizing:border-box;
     font:inherit; font-size:14px; line-height:1.2;
     padding-top:0; padding-bottom:0; padding-left:10px; padding-right:30px;
     border:1px solid var(--cal-line); border-radius:8px;
   }
   .cleaning-page .dashboard-calendar .cal-heading select[data-cal-property] { width:100%; }
   ```
   (Padding-right stays 30 px for the chevron set at line ~229.) If the property select has its own row rule, keep it, just make sure its text is not clipped.
2. Also check the host dashboard calendar (`/dashboard`) selects show full text at 390/1280/2000 (they use the `.host-workspace` rule; do not change it unless clipped).
3. Verify with Playwright (Chromium at `/opt/pw-browsers`). Get a share token the way `tests/test_cleaning*` browser tests do (grep `cleaning/s/` in tests). For each of the three selects assert `scrollHeight <= clientHeight` and that the computed content box height (clientHeight minus vertical padding) is at least the computed line-height. Widths 390, 1280, 2000. Save screenshots to `/mnt/project-files/design-reset/checkpoint-6/cleaning/shared-<width>.png`.

## 5. Do not touch

cleaning.css, cleaning.js, templates other than the key bump. Never push.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_cleaning*.py tests/test_dashboard_calendar*.py tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30`

## 7. Acceptance

- [ ] "October", "2026", "All properties" fully visible on the shared page at 390/1280/2000.
- [ ] Tests above pass; screenshots saved.

## 8. Stop and ask

If an excerpt is not found, stop and report. Do not commit; the orchestrator commits.

## 9. Report

[0197-report.md](0197-report.md)
