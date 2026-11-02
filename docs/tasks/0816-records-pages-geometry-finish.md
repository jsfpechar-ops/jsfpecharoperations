# 0816: Finish the owner geometry rules on the four records pages

Status: todo
Depends on: 0798 part 1 (c921cd75) | Branch: claude/project-thread-v4nqi5 (main checkout, do NOT commit; the orchestrator commits)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Fix what `docs/tasks/0798-report.md` left open on `/submissions`, `/invoices`, `/housebook`, `/stay-fees`, plus one CI failure, and take the final screenshots.

## 2. Context

1. **Help "?" next to the title (R1).** Today the closed `details.ui-how` toggle sits 49 px below the h1. Put it on the h1's line: in each of the four templates the `details.ui-how` goes inside the head, right after the h1, and CSS makes the h1 and the toggle one row (`display:flex; align-items:center; gap:var(--space-2)` on the h1 wrapper; the summary shows the circle-help icon plus the one-word label, or just the icon at < 1024). The open body drops below the head as a panel (`position:absolute` under the toggle, `width:min(520px, calc(100vw - 32px))`, card background, `var(--space-4)` padding, z-index above the table) so the page does not reflow. Must work without JavaScript (native details). Check `tests/test_page_help_0277.py` and `tests/test_motion_browser.py` still pass (one closed help per page).
2. **R2:** housebook phone card text 15 px from the card's top edge: >= 16 px.
3. **R3:** invoices `.month-step` buttons and the month label touch (gap 0): `gap:var(--space-3)`. Invoices "Apply filters"/"Cancel" touch the empty-state h2: >= 12 px. Stay fees "Apply filters" 6-7 px from the title: >= 12 px.
4. **CI:** `tests/test_host_geometry.py:207` "/invoices?lang=en: stepper must not be stranded at the far edge" (assert 0 > 40). Read the test, fix the invoices month row layout (not the test).
5. **Stay fees fine print (orchestrator decision):** delete the summary line under the h1 (`#fee-list-summary`, counts) and any CSS/test that only serves it; move the "send to databox" sub line into the page help body; keep the "period running" line (it is a state, not a description).

## 3. Files

`App/app/templates/submissions.html`, `invoices.html`, `housebook.html`, `stay_fees.html`; `App/app/static/app2.css` (0791-0794 blocks; one shared `body.v2 .head details.ui-how` rule set may go in the 0791 block, used by all four); the i18n files only for strings that become unused; tests that assert `#fee-list-summary` (update). `App/app/templates/base.html` + `App/tests/static_versions.json`: bump `app2.css?v=` to `20261102-0816` and run `.venv/bin/python tests/test_static_versions.py --write` from `App/` at the end.

## 4. Steps

1. One Playwright script in `/tmp/claude-0/scratch-0816/measure.py` (rich-host fixture from `App/tests/v2_mockup.py`) printing: h1 top vs help toggle top, card text insets, the gaps of item 3, at 390/1024/1280/1440 for the four pages. Run it (red).
2. Fix items 1-5. Rerun measure.py until clean.
3. Commands, then screenshots: `docs/tasks/screenshots-0790/<page>-390.png` and `<page>-1280.png` (8 files, overwrite) with the help closed; plus `stay-fees-1280-help-open.png`. Look at each once.

## 5. Do not touch

Anything outside §3. No new dependency, colour or JS. Do not change `host_page.html` or other pages' help.

## 6. Commands (from `App/`, each `2>&1 | tail -30`)

1. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k "invoices or housebook or submissions or stay_fees" tests/test_host_geometry.py tests/test_motion_browser.py tests/test_0252_touch_sweep_browser.py tests/test_host_button_contrast_browser.py -q -rs --tb=short`
2. `.venv/bin/python -m pytest tests/test_page_help_0277.py tests/test_design_fees.py tests/test_design_invoices.py tests/test_design_reports.py tests/test_static_versions.py tests/test_design_lint.py -q --tb=short`
3. From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -5`

## 7. Acceptance

- [ ] measure.py clean: help toggle top within 4 px of the h1 top (or centred on its line) on all four pages at all four widths; card text >= 16 px from edges; the item-3 gaps >= 12 px (paste final output, max 10 lines).
- [ ] Commands 1-3: 0 failed, 0 skipped.
- [ ] 9 screenshots saved.

## 8. Stop and ask

Blocked if a fix fails twice, a file outside §3 needs a change, or 30 tool calls.

## 9. Report

`docs/tasks/0816-report.md`, 300 tokens at most. Do not commit or push.
