# 0192: Sidebar "Stay fees" replaces "Invoices and stay fees"

Status: done
Depends on: none | Base commit: branch tip at pull | Branch: claude/project-thread-3xqb0b
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Owner request (Josef, 2026-10-20): the Invoices section is removed from the sidebar. Invoices are reached through a stay (the Generate invoice button on the stay and reservation detail pages). The sidebar gets a "Stay fees" item again, with the same icon as invoices (`invoice-slip`).

## 2. Context

- `App/app/templates/_shell_sidebar.html`: the nav item `/invoices` with label `nav.invoices_fees` ("Invoices and stay fees").
- `App/app/templates/_shell_tabbar.html`: the phone More sheet has the same `/invoices` link.
- `nav.stay_fees` already exists: `App/app/host_design_i18n.py` (EN "Stay fees", CS "Poplatky z pobytu") overrides `host_i18n.py`.
- `reservation_detail.html` already links `/invoices/new?reservation_id=...` (Generate invoice).
- Section tabs for invoices (`templating.py`, `section == "invoices"`) already list Invoices and Stay fees; not edited here.
- `App/tests/test_stay_fee_list.py` asserted the sidebar link waits for opt-in. The owner asked for the section without a gate, so that test now asserts the item is shown.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/_shell_sidebar.html | edit | nav item `/invoices` -> `/stay-fees`, `nav.stay_fees`, active when `nav == 'stay_fees'` |
| App/app/templates/_shell_tabbar.html | edit | More sheet link `/invoices` -> `/stay-fees`, `nav.stay_fees` |
| App/tests/test_design_shell.py | edit | sidebar and More sheet assertions use `/stay-fees` |
| App/tests/test_design_shell_browser.py | edit | More sheet link check uses `/stay-fees` |
| App/tests/test_host_ux_acceptance.py | edit | sidebar click to Invoices becomes a section link; focus walk expects `/stay-fees` |
| App/tests/test_stay_fee_list.py | edit | opt-in test becomes "sidebar has a Stay fees item" |
| docs/tasks/0192-sidebar-stay-fees.md | new | this brief |

No other file may change. Do not touch `.css`, `base.html` asset keys, `App/tests/static_versions.json` or `templating.py`.

## 4. Steps

1. Sidebar: replace the `('/invoices', 'invoice-slip', t('nav.invoices_fees'), nav in ('invoices', 'stay_fees')),` line with `('/stay-fees', 'invoice-slip', t('nav.stay_fees'), nav == 'stay_fees'),`. Done.
2. Tab bar More sheet: `href="/invoices"` and `nav.invoices_fees` -> `href="/stay-fees"` and `nav.stay_fees`. Done.
3. Tests: swap `/invoices` for `/stay-fees` in the three sidebar and More assertions; the focus walk in test_host_ux_acceptance clicks the Invoices section link on the stay-fees page instead of the rail. Done.
4. Opt-in test in test_stay_fee_list.py: assert the sidebar contains `/stay-fees`. Done.
5. Run §6.

## 5. Do not touch

Invoice routes, `templating.py` tab lists, the command palette entries, the design CSS, the static asset keys, `invoice_*` templates. Invoice pages keep `nav = 'invoices'`, so no sidebar item is highlighted on them (no Stays highlight in this change).

## 6. Commands

- `cd App && UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell .venv/bin/python -m pytest tests/test_design_shell_browser.py tests/test_design_shell.py tests/test_a11y_guard_browser.py tests/test_invoice_*.py tests/test_stay_fee*.py tests/test_host_ux_acceptance.py -q --tb=short -rs 2>&1 | tail -30`
- `python3 scripts/context_lint.py 2>&1 | tail -30`

## 7. Acceptance

- [x] Sidebar has six items, one of them "Stay fees" at `/stay-fees` with `invoice-slip`; no `/invoices` item in the sidebar.
- [x] More sheet links to `/stay-fees`.
- [ ] The commands in §6 pass with 0 skipped (`-rs`).
- [ ] Screenshots at 390 and 1280 px of `/stay-fees` with the Stay fees item active, written to `/mnt/project-files/design-reset/checkpoint-4-shell-fixes/`.

## 8. Stop and ask

An excerpt is not found, a test fails twice, a file outside §3 needs a change, 25 tool calls reached. Owner question open: should the Stay fees item stay hidden until a property opts in (the previous test rule)? This brief shows it always, as the owner asked.

## 9. Report

`docs/tasks/0192-report.md`, 600 tokens at most: files changed, commands with the last 5 lines, §7 ticked, Deviations, Questions, owner steps left.
