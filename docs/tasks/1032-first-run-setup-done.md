# 1032: first-run polish B, setup wizard "done" page as one calm column

Status: todo
Depends on: none | Base: `origin/main` | Branch: `claude/first-run-1032` | Open one PR (executor.md), never merge
Executor: Haiku 5.5, one run, 30 tool calls (checkpoint at 25: commit, report `Status: blocked`, list what is left). UI brief: rules 7 and 10 apply. Sibling briefs 1031 and 1033 touch other files.

## 1. Objective

Before shots: `/mnt/project-files/first-run/before/setup-done/` and `setup-done-partial/` (`<en|cs>-<390|768|1280>.png`). Open EN 390 and 1280 once. The page (`App/app/templates/setup_wizard/done.html`) is stacked boxes in a 720px wizard lane with a 1000px area around it. Direction: one calm column, rounded, generous even spacing, less is more. Keep logic, copy meaning, a11y, focus behaviour, and every `data-*` hook the tests use (`data-setup-celebrate`, `data-setup-summary-step`, `data-setup-next`, `data-setup-next-step`, `data-finish-go`, `data-finish-note`). No new dependency. Light mode only.

Target page, top to bottom, one 720px column:
1. ONE status line: the existing `.setup-wizard-celebrate` banner reduced to a single line (mark + title + the one-sentence text under it only when partial). Keep the confetti span and `role="status"`.
2. The "How each stay works" `workflow_strip(apartment)` is folded behind a `<details>` disclosure (closed by default) with `<summary>` using the same heading string the strip prints now (read `App/app/templates/_workflow.html` macro `workflow_strip(apartment=none, heading=true)`: call it with `heading=false` inside the details and use the heading string as the summary text; find the heading key with `grep -n "heading" App/app/templates/_workflow.html | head`). The summary is a keyboard-focusable native summary, 44px min height.
3. The checklist ("wizard.done.title") as short rows: each row = icon, title, status badge, optional "Add login" link; hairline dividers inside ONE rounded container instead of one card per row; no nested box in a box (drop `host-property-card` borders on the rows).
4. "What to do next" (`wizard.done.next_title`): the same rows style, each row a full-row link with a chevron at the right (use the icon helper: `{% from "_icons.html" import icon with context %}` then `{{ icon('chevron-right', 16) }}`; check the icon name exists with `grep -n "chevron" App/app/templates/_icons.html | head -5`, else STOP).
5. The finish note (`data-finish-note`) stays as one muted line.
6. The ONE primary button (`wizard_actions` block, `data-finish-go`) is centred inside the 720px lane. Today the block starts with an empty `<span></span>` that pushes it right: remove that span and centre the actions container (override in CSS only for this page via a `.wiz-done` hook class, see section 3).
7. Lane alignment: the 720px column and whatever is at 1000px (heading/steps header in `setup_wizard/_layout.html` and `.wiz-page` rules) must share one left edge at 768 and 1280: make the done page content use the same 720px width and centre as the wizard heading above it; at 390 side padding is 16px.

New copy: none. If any is needed, add EN, CS and VI (parity) in `App/app/host_i18n.py` and `App/app/host_vi_i18n.py` (find neighbours with `grep -nF '"wizard.done.title"' App/app/host_i18n.py`).

## 2. Context

- `welcome_back` looked like dead UI (the route in `App/app/routes/onboarding.py` and the strings exist, no template renders it). Do NOT change it.
- Do NOT touch the "Add a second way in" dialog in `base.html`.
- Existing tests that read this page: `tests/test_design_setup_wizard_browser.py`, `tests/test_0884_wizard_geometry_browser.py`, `tests/test_wizard_four_steps_0884.py`, `tests/test_first_run_steps.py`, `tests/test_wizard_old_look_0953.py`, `tests/test_wizard_old_look_0953_browser.py`. Update an assertion only if it names an element this brief removes (the empty span, the card class on rows, the strip being visible without opening); say so in the report.
- If a test clicks inside the workflow strip, it must open the `<details>` first; adapt only that.

## 3. Files (grep to confirm anchors first; not found: STOP)

| Path | Action |
|---|---|
| App/app/templates/setup_wizard/done.html | edit: items 1-6 (the `wizard_content` and `wizard_actions` blocks) |
| App/app/templates/setup_wizard/_layout.html | edit only to add a page hook class `wiz-done` when the child sets it (read how `wiz-page` is applied: `grep -n "wiz-page" App/app/templates/setup_wizard/_layout.html App/app/templates/base.html App/app/templates/host_page.html`). If a hook is impossible without touching 3+ files, scope the CSS with `.setup-wizard-celebrate ~ .setup-wizard-checklist` selectors instead and say so |
| App/app/static/app2.css | edit/add rules next to `body.v2 .wiz-page .setup-wizard-celebrate...` (lines ~1337-1401, 2758) and `.setup-next-card` (~1375); delete rules that only served the removed card borders |
| App/app/static/host.css | `.setup-wizard { max-width: 720px ... }` at ~1317: edit only if the lane alignment (item 7) needs it |
| App/app/static/wizard.css, workflow.css | edit only if their rules fight the new layout (`grep -n "setup-summary\|workflow" App/app/static/wizard.css App/app/static/workflow.css | head`) |
| App/app/templates/base.html, App/tests/static_versions.json | bump `?v=` of each static file you changed and update `static_versions.json` (`grep -n "app2.css" App/app/templates/base.html App/tests/static_versions.json`) |
| docs/tasks/1032-report.md | create |

## 4. Steps

0. Clean tree. `git checkout -B claude/first-run-1032 origin/main`. Read the design-system checklist headings only (`grep -n '^## \|^- \[' docs/design/design-system.md | head -40`).
1. `done.html` template edit: items 1-6. Keep Jinja variables and the logic (`missing_row`, `link_next`, `lock_available`) unchanged.
2. Run `cd App && .venv/bin/python -m pytest tests/test_first_run_steps.py tests/test_wizard_four_steps_0884.py tests/test_wizard_old_look_0953.py -q --tb=short -x 2>&1 | tail -30`.
3. CSS for items 3, 4, 6, 7: one container `border-radius` token already used by cards, 1px hairline divider, rows 56px min height, 16px horizontal padding, 24px gap between sections (title, list, next list), chevron colour muted. Status badges keep their classes.
4. Static `?v=` bump.
5. Tests (test-map "Host pages, host templates, host CSS"): `cd App && .venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py tests/test_design_setup_wizard_browser.py tests/test_0884_wizard_geometry_browser.py tests/test_wizard_old_look_0953_browser.py tests/test_onboarding_wizard_browser.py tests/test_design_guardrails_browser.py -q -rs --tb=short -x 2>&1 | tail -30`. 0 skipped.
6. UX gate: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -rs -x 2>&1 | tail -30`: green, 0 skipped, zero host findings.
7. Screenshots of both states (`setup-done` all set, `setup-done-partial`), EN at 390, 768, 1280, saved to `/mnt/project-files/first-run/after/setup-done/en-<w>.png` and `/mnt/project-files/first-run/after/setup-done-partial/en-<w>.png`, plus CS 390 of each. Reuse the fixtures/helpers of `tests/test_design_setup_wizard_browser.py`. Look at each once. Write per page in the report and PR body: "390: ...; 768: ...; 1280: ..." (one status line, disclosure closed, chevron rows, primary button centred in the lane, same left edge as the heading, no overflow). Tick the design-system checklist in the PR.
8. Report (600 tokens max), `Status: review`, one PR. Commit each step as `1032 step k`.

## 5. Do not touch

other `setup_wizard/*` step templates, `_workflow.html` itself (call it with `heading=false`; if that argument does not remove the heading, STOP), `_components.html`, `account_accept.html`, base.html except the `?v=` bump and never the "Add a second way in" dialog, `welcome_back*`, wizard route logic.

## 6. Commands

From `App/`, as in steps 2, 5, 6. Browser tests: 0 skipped.

## 7. Acceptance

- [ ] One status line; "How each stay works" is closed behind a disclosure and opens with keyboard.
- [ ] Checklist and next-steps are single containers with divided rows; next rows are links with a chevron; no nested boxes.
- [ ] One primary button, centred in the 720px lane; content and heading share a left edge at 768 and 1280.
- [ ] All `data-*` hooks still present; layout lint and browser tests green, 0 skipped; shots in `/mnt/project-files/first-run/after/setup-done*/`; per-page notes in the PR.

## 8. Stop and ask

- Anchor not found; `chevron-right` icon missing; `heading=false` does not hide the strip heading.
- A layout-lint finding or skipped browser test (report the text, never silence).
- A test fails twice. 25 tool calls reached: commit, report `Status: blocked`.

## 9. Report

Per `docs/context/executor.md` plus the UX-gate notes. Owner steps: none.
