# 0700 report (executor)

Status: done (no push, no PR)

## Done
- Step 1 tokens.css: canvas #f6f6f4, coral scale per brief.
- Step 2 host2.css: block "0700 shared look (mockup v2)" at the end. Buttons, page header (no rule), table cells and header, badges by data-tone, how-toggle at >= 768 px. Rows lose their card look at >= 1024 px.
- Step 3 base.html ?v= keys bumped. Static manifest refreshed.
- Legacy canvas overrides removed so the mockup canvas applies (orchestrator decision A):
  - host-design0123.css line 4: `--canvas:#fff;` removed.
  - host.css line 5 (`.host-workspace { --canvas: #faf1ec; ... }`): same override, removed. This one was not in the decision text; it was also needed for rgb(246,246,244). Flagging it.
  - host2.css main rule is `body.host-workspace main#main-content`, because host-design0123 has `body.host-workspace #main-content {background:#fff}`.
- Step 4 test: App/tests/test_0700_shared_look_browser.py (2 tests, pass). Rows checked at 1280 px only.
- Step 5 screenshots: docs/tasks/screenshots-0700/home-1280.png, reservations-1280.png, apartments-1280.png (cs, 1280 px, full page, demo wide_host data).

## Cache keys
host.css ?v=20261101-0700, host-design0123.css ?v=20261101-0700, host2.css ?v=20261101-0700c (the brief said 0700; host2 changed again after the manifest was written, so it got a suffix).

## Tests (App/, 0 skipped)
- Group in brief section 6: 62 passed.
- Remaining geometry and design browser files: 48 passed (0199 phone, 0447 billing, design setup wizard, design shell, funnel ads geometry, guest OCR geometry, host wide geometry).
- design_lint: OK. context_lint: OK (warning only: status.md not updated since the last commits).

## Updated assertion (brief section 8)
- App/tests/test_design_guardrails_browser.py test_table_rows_have_their_own_border_on_desktop: `gap >= 4` changed to `gap == 0` (0700: one card, no gap). Top and left 1px checks kept.

## Deviations
- Tablet 768-1023 px: the card-row rule lives in a max-width 1023 block, so I scoped the no-card override to >= 1024 px (accepted by orchestrator).
- Tokens instead of raw colours (design_lint S1): secondary button and neutral badge use --surface-2 (#f1f1ef, not #efefeb); warn and ok use --st-attention-* and --st-done-*; bad uses --red-100 and --red-700.
- rem instead of px (S2).
- Commit attribution: the brief said Opus 5.5; system attribution says Haiku 5.5. Haiku 5.5 used.

## Elements that were white cards and now show canvas grey (not fixed)
From the rules that read var(--canvas) or var(--surface-2) in host scope:
1. Calendar on home (dashboard-calendar): empty day cells, weekday header row, and the outside-month cells are grey (home-1280.png).
2. Search trigger "Hledat" (host.css `.host-workspace .command-trigger`) is grey.
3. Anything using var(--surface-2), which is canvas in body scope (host.css body.host-workspace block): secondary buttons, "Otevřít pobyt" buttons in "Co na vás čeká", neutral badges, table row hover.
4. Anything using var(--bg) (app.css `background: var(--bg)` rules) on host pages.
5. Disabled textarea (host.css `.host-workspace textarea:disabled`).
Not host scope, left alone: cleaning.css `.cleaning-public`, landing.css `.calendar-days i`, host2.css swatch demo.

## Visible issues seen in screenshots (not fixed, outside the brief's selectors)
- /apartments: tables use row cards (`ui-table-stack` / lc-properties rows still bordered and rounded). Only /reservations was fixed for rows.
- /apartments second table header (`.lc-properties` th) keeps a coral tint.

## Owner steps left
1. Review the three screenshots and decide whether the apartments row cards and calendar grey cells are acceptable, or give a follow-up brief.
2. Branch task/0700-shared-look is local only. Nothing pushed.
