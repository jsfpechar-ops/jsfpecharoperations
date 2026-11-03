# 0853: Last CI browser failures on PR #707 (run 41455096365, shard 4)

Status: todo
Depends on: 0852 | Branch: claude/project-thread-v4nqi5 (main checkout, do NOT commit; the orchestrator commits)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

CI on the merged head ef5fe66 (run 41455096365) passes shards 1-3; the old shard-1 items are gone. Make the three shard-4 failures below pass. Fix the page when the v2 page really breaks the rule; update a test only when it asserts old-shell markup the v2 page intentionally dropped (comment "v2, 0792/0794"). Reproduce each with `-k` first, with `UBYHOST_REQUIRE_BROWSER=1`.

## 2. Context

1. `tests/test_0252_touch_sweep_browser.py:103`: `/stay-fees` at ipad1024, ipad1180 and desk2000 reports `noCue` on the property rows ("Karlín Loft (demo) Praha", "Vinohrady Studio (demo) Praha"): a clickable row with no touch/hover cue. Read the PROBE in that test, then give the v2 stay-fees rows the same cue the `/reservations` `.stays-desk` rows have (same class or rule, no new look).
2. `tests/test_host_controls_browser.py:363`: the housebook PDF dialog `#housebook-pdf-dialog` no longer contains `.housebook-pdf-warn` (the 100-PDF limit). 0798 moved that `<p>` into the page help (`housebook.html` around line 36). The limit belongs where the export happens: move that one `<p class="housebook-pdf-warn">` back into the PDF dialog (see `git show f48f8dd~10:App/app/templates/housebook.html` or `git log -p -S housebook-pdf-warn` for where it was) and remove it from the help body. Do not change the test.
3. `tests/test_host_geometry.py:213`: `/invoices` month-filter `.month-step` buttons are 37 px tall at widths > 600; the test expects 42 (44 at <= 600). Fix the height in the invoices v2 / 0854 filter block of app2.css so the steppers match the test, without changing other controls.

## 3. Files

`App/app/templates/housebook.html`, `stay_fees.html`; `App/app/static/app2.css`; tests only per §1. If you change app2.css, bump `app2.css?v=` in `App/app/templates/base.html` to `20261102-0853` and run `.venv/bin/python tests/test_static_versions.py --write` from `App/` at the end.

## 4. Steps

Reproduce, fix, rerun, one item at a time.

## 5. Do not touch

Anything outside §3. No new dependency, colour or JS.

## 6. Commands (from `App/`, each `2>&1 | tail -30`)

`UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0252_touch_sweep_browser.py tests/test_host_controls_browser.py tests/test_host_geometry.py tests/test_0710_v2_mockup_match_browser.py -k "touch_sweep or host_interactions or month_filter or invoices or housebook or stay_fees" -q -rs --tb=short`

## 7. Acceptance

- [ ] The command: 0 failed, 0 skipped.

## 8. Stop and ask

Blocked if a fix fails twice, a file outside §3 needs a change, or 30 tool calls.

## 9. Report

`docs/tasks/0853-report.md`, 250 tokens at most. Do not commit or push.
