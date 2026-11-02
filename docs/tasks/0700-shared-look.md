# 0700: shared look of the redesign (canvas, cards, coral, pills, header, tables, pills)
Status: todo
Depends on: none | Base commit: origin/main | Branch: task/0700-shared-look
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
Every host page (computer width, 768 px and up) takes the visual style of the approved mockup `/mnt/project-files/ux-redesign/ubyhost-redesign-v2.html` (owner approved 2026-11-01; gap list `/mnt/project-files/ux-redesign/overview/gap-list.md` items 1-6). Style only: no template, copy or behaviour change. Other page threads build on this, so all of it lives in two places only: the coral tokens in `tokens.css` and ONE block at the end of `host2.css`.

## 2. Context (mockup values, use them literally)
- Canvas `#f6f6f4`; surface `#fff`; line `#ebebe7`; ink `#1c1c1a`, ink-2 `#55554f`, ink-3 `#8a8a84`.
- Coral `#d4472f`, soft `#fdece8`. Status soft pills: ok `#e6f5ec`/`#167044`, warn `#fff4d6`/`#8a5200`, bad `#fdecea`/`#b42318`.
- Card: `background:#fff; border:1px solid #ebebe7; border-radius:12px`.
- Buttons: `border-radius:999px; padding:9px 16px; font-weight:600; border:0`. Primary coral on white text. Secondary `background:#efefeb; color:ink; border:0`. Small: `padding:6px 12px; font-size:13px`. `:active{transform:scale(.97)}`.
- Page title 24px/800, letter-spacing -.01em, a 28x3 px coral bar 8px under it (`::after`), sub/meta line ink-3. No rule or border under the page header.
- Section headings (`h2` in the main column, `.ui-section-h` etc.) 16px/700, no count badge styling change needed.
- Tables: one white card (the wrapper), header cells `font-size:12px; font-weight:500; color:ink-3; text-transform:none; letter-spacing:0; background:transparent; padding:10px 14px; border-bottom:1px solid line`; body cells `padding:12px 14px; border-bottom:1px solid line`; rows are NOT separate cards at computer width (no per-row border, radius, margin or shadow).
- Badges (`.ui-badge`): `font-size:12px; font-weight:600; padding:3px 9px; border-radius:999px; border:0`, soft background by tone (`data-tone` amber -> warn, red -> bad, green -> ok; others: `#efefeb`/ink-2).
- `.ui-how-toggle` ("Jak to funguje?"): a quiet text link (no border, no pill background, ink-3, 13px, underline on hover).

## 3. Files
Edit `App/app/static/tokens.css` (coral scale + `--canvas` only), `App/app/static/host2.css` (append one block headed `/* 0700 shared look (mockup v2) */`), `App/app/templates/base.html` (only the two `?v=` keys, value `20261101-0700`), `App/tests/static_versions.json` (only via `--write`), `docs/design/catalog.json` only if you add a class (you should not need to). Create `App/tests/test_0700_shared_look_browser.py`. Screenshots in `docs/tasks/screenshots-0700/`. Report `docs/tasks/0700-report.md`.

## 4. Steps
1. Tokens: set `--canvas: #f6f6f4`; coral scale `--coral-50:#fef5f3; --coral-100:#fdece8; --coral-200:#f6c6bc; --coral-500:#e0644e; --coral-600:#d4472f; --coral-700:#b83a24`. Change nothing else in tokens. Commit `0700 step 1`.
2. Find the real selectors before writing: `grep -n 'ui-ph\b\|\.ui-ph \|ui-ph-main\|ui-ph-meta' App/app/static/*.css | head`, the same for `ui-table`, `ui-row`, `ui-badge`, `ui-btn-secondary`, `ui-how-toggle`, `data-card`, and the canvas background (`grep -n 'background: var(--canvas\|background: var(--bg)' App/app/static/*.css | head`). Note which rules turn table rows into cards at computer width.
3. Append the block to `host2.css`, all rules inside `@media (min-width: 768px)` and prefixed `body.host-workspace` so phone stays as it is, except the canvas background of the main area which applies at every width. Use the values in section 2. Override, do not delete, older rules (other threads still use them). Commit `0700 step 2`.
4. Bump the two `?v=` keys, `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5` from `App/`. Commit `0700 step 3`.
5. Test `test_0700_shared_look_browser.py` (copy server/login fixtures from `tests/test_design_guardrails_browser.py`), at 1280 px on `/`, `/reservations`, `/apartments`, `/cleaning`: computed `border-radius` of `.ui-btn-primary` >= 999 px or equals half its height; `.ui-ph` has no bottom border; first `th` has `text-transform: none` and transparent background; on `/reservations` two consecutive `tr.ui-row` have a vertical gap of 0 px (one card); main background is rgb(246, 246, 244). At 390 px the `.ui-btn-primary` radius is unchanged from origin/main (read it before your change and hard-code it). Commit `0700 step 4`.
6. Screenshots at 1280 px of `/?lang=cs`, `/reservations?lang=cs`, `/apartments?lang=cs` with the demo data loaded (look for the demo loader: `grep -rn 'def .*demo' App/app/demo.py | head`; use it in the screenshot fixture), into `docs/tasks/screenshots-0700/`. Commit `0700 step 5`.

## 5. Do not touch
Templates (except the `?v=` keys), JS, routes, copy, other CSS files, phone layout (below 768 px), `workflow.css` (`.needs-you` belongs to brief 0701), `dashboard-calendar.css` (0701).

## 6. Commands (from `App/`, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`)
`.venv/bin/python -m pytest tests/test_0700_shared_look_browser.py tests/test_design_guardrails_browser.py tests/test_dashboard_rows_browser.py tests/test_host_quiet_dashboard_browser.py tests/test_dashboard_calendar_browser.py tests/test_cleaning_browser.py tests/test_static_versions.py tests/test_design_dashboard.py -q --tb=short -x -rs 2>&1 | tail -30`; then every other `tests/test_*geometry*browser*.py` and `tests/test_*design*browser*.py` that exists; then from the repo root `python3 scripts/design_lint.py | tail -3` and `python3 scripts/context_lint.py 2>&1 | tail -3`.

## 7. Acceptance
All pass, 0 skipped. `git diff --stat origin/main` lists only section 3 files.

## 8. Stop and ask
An existing test that asserts an old colour value, button radius, header rule or table-row-card geometry at >= 768 px may be updated to the new value; list each in the report. Stop if a phone-width (< 768 px) test changes result, or more than 6 existing assertions need changes.

## 9. Report
`docs/tasks/0700-report.md`: Status, test and lint tails, diff stat, screenshot paths, updated assertions, deviations.
