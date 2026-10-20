# 0193: Cleaning module polish (chip label, form pages, centred dialogs)

Status: blocked
Depends on: none | Base commit: see git log | Branch: claude/project-thread-3xqb0b
Executor: Haiku 5.5 | Fits one session: 25 tool calls, 60k tokens

## 1. Objective

Owner request (Josef, 2026-10-20) from screenshots: (1) calendar cleaning chips start with the word "Cleaning" and it is never truncated; (2) cleaning subpages (instructions, share, edit) look like raw forms; (3) the "Add stay" and "Add cleaning" dialogs open centred in the viewport, not near the top or below centre.

## 2. Context

- Chip text is built in `App/app/static/dashboard-calendar.js` (`eventLink`), label span `cal-cleaning-label`, title from `cleaning_i18n.py` key `title` (EN "Cleaning", CS "Úklid").
- Create dialog is `[data-cal-create]` (`.cal-create-popover`) in `_dashboard_calendar.html`; it was placed with inline left/top by `placeCreate`.
- Share page: `App/app/templates/cleaning_shares.html` (`fieldset` with `cleaning-share-option` rows). Instructions: `cleaning_settings.html`. Edit: `cleaning_edit.html`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/static/dashboard-calendar.js | edit | label gets " · " suffix; placeCreate stops setting left/top |
| App/app/static/dashboard-calendar.css | edit | create popover inset 0, margin auto; label visible and nowrap |
| App/app/static/cleaning.css | edit | fieldset and option-row styling scoped under `.cleaning-form` |
| App/app/templates/_dashboard_calendar.html, _cleaning_screen.html, base.html, cleaning_shared.html | edit | `?v=` bumps |
| App/tests/static_versions.json | edit | sha256 and v for the three changed files |

## 4. Steps

1. Chip label: `cleaning_label + " · "` in `eventLink`. Done.
2. Label CSS: visible on desktop/gantt, `white-space:nowrap`, `flex:0 0 auto`. Done.
3. Create dialog: centred by CSS (`inset:0; margin:auto; max-height:min(90dvh, ...)`); JS no longer sets position. Done.
4. Fieldset: no raw browser border; bordered option rows with 44 px min height. Done.
5. Bumps and manifest. Done.
6. NOT DONE in this session: browser tests for chip text and dialog centre; 390/1280 screenshots; cleaning_settings and cleaning_edit form restyling; `catalog.json` entries (no new class names were added); `_cleaning_list` chip mirror on the public shared schedule (check it uses the same JS).

## 5. Do not touch

`_shell_sidebar.html`, `_shell_tabbar.html`, `test_design_shell*.py`, `test_host_ux_acceptance.py` (another executor's uncommitted edits). Never `git add -A`.

## 6. Commands

- `cd App && .venv/bin/python -m pytest tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30`
- `python3 scripts/design_lint.py 2>&1 | tail -30` (pre-existing FAIL: smart_locks.html enforced template missing; not this brief)
- `python3 scripts/context_lint.py 2>&1 | tail -30` (pre-existing FAIL: 0192 report missing)

## 7. Acceptance

- [x] static_versions test passes.
- [ ] Browser tests for chip text and dialog centre (0 skipped).
- [ ] Screenshots at 390 and 1280 for calendar, both dialogs, instructions, share, edit.
- [ ] Form restyle of instructions and edit pages.

## 8. Stop and ask

A test fails twice, the share or edit page needs a shared-component change outside `cleaning.css`, or 25 tool calls reached.

## 9. Report

`docs/tasks/0193-report.md` (600 tokens max). Commit by explicit path; the orchestrator pushes.
