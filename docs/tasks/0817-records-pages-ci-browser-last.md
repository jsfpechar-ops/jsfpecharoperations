# 0817: Last CI browser failures on PR #707 (run 41450674965, shard 1)

Status: todo
Depends on: 0816 | Branch: claude/project-thread-v4nqi5 (main checkout, do NOT commit; the orchestrator commits)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Make these CI failures pass. Fix the page when the v2 page really breaks the rule; update the test only when it asserts old-shell markup the v2 page intentionally dropped (comment "v2, 0792/0794"). Reproduce each with `-k` first: CI failed on some that passed locally in 0814, so run with `UBYHOST_REQUIRE_BROWSER=1` and the same widths.

## 2. Context

1. `tests/test_host_wide_geometry_browser.py:523`: `('housebook', 'en', 1024, {'left': 256, 'right': 988, 'top': 100, 'bottom': 119, ...}) is None`: an element the test expects to be absent/aligned at 1024 on /housebook. Read the test around 500-523 to see what it is.
2. `tests/test_host_list_cards_browser.py:120`: `('stay-fees/1280', [])`, `assert 0 >= 2`: the test finds no clickable list rows on /stay-fees at 1280. Either the v2 table rows need the row-link hook the other v2 lists use (compare `/reservations` `.stays-desk` rows), or the selector must include the v2 rows.
3. `tests/test_host_button_contrast_browser.py:154` `test_empty_state_action_is_centred_under_its_text`: /invoices empty state, action centre 420.5 px off the text centre. Centre it (see `.ui-empty` on `/reservations`).
4. `tests/test_design_guardrails_browser.py:117` and `:287`: `/invoices` at 1280 with the filter panel open: "button-heights-differ" (`button.ui-btn.ui-btn-primary.filter-apply "Apply filters"` 37 px vs its siblings). One shared height (`var(--control-h)` or the stays filter's).
5. `tests/test_host_list_page_layout_browser.py` `fees` entries at 760/1024 "expanded": "no list panel" and "missing block": the test looks for an old list panel on /stay-fees. If the v2 page has `.stays-desk`/`.stays-phone`, update the fees selectors like 0795 did for invoices.

## 3. Files

`App/app/templates/invoices.html`, `housebook.html`, `stay_fees.html`; `App/app/static/app2.css` (0792-0794 blocks); the five test files above (selector updates only, rule in §1). If you change app2.css, bump `app2.css?v=` in `App/app/templates/base.html` to `20261102-0817` and run `.venv/bin/python tests/test_static_versions.py --write` from `App/` at the end.

## 4. Steps

Reproduce, fix, rerun, one item at a time.

## 5. Do not touch

Anything outside §3. No new dependency, colour or JS.

## 6. Commands (from `App/`, each `2>&1 | tail -30`)

`UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_wide_geometry_browser.py tests/test_host_list_cards_browser.py tests/test_host_button_contrast_browser.py tests/test_design_guardrails_browser.py tests/test_host_list_page_layout_browser.py tests/test_host_geometry.py -q -rs --tb=short`

## 7. Acceptance

- [ ] The command: 0 failed, 0 skipped.

## 8. Stop and ask

Blocked if a fix fails twice, a file outside §3 needs a change, or 30 tool calls.

## 9. Report

`docs/tasks/0817-report.md`, 250 tokens at most. Do not commit or push.
