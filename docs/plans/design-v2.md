# Design v2: host app design reset (brief order)

State: briefs written 2026-10-19, all `Status: todo`. Design source: `docs/design/MASTER.md`, `docs/design/direction.md`, `docs/design/pages/*.md`, `docs/design/prototype.html`, `docs/design/migration-map.md`. Decision line: `docs/context/decisions.md` (design v2). Owner-confirmed legacy removal set: 0136 and 0137.

## Rules for running the lane

- One Haiku 5.5 session per brief, in the order below. Branch for every brief: `claude/project-thread-td6fpc`; Haiku commits each step (`NNNN step k`), never pushes, never opens a PR. The owner reviews reports, then merges the branch with `scripts/merge-pr-on-green.sh` when the lane is done (or after 0133 as a first visible checkpoint).
- Tests: the test-map row "Host pages" from `App/` with `.venv/bin/python`. Five pre-existing local failures at 360 px (`test_host_fit_browser.py`, `test_host_invoice_items_browser.py`, `test_host_properties_navigation.py`, `test_host_property_controls_browser.py`) are not caused by the briefs; each brief that runs them quotes the unchanged message.
- Parallel runs: none. Every brief edits at least one of `App/app/static/host2.css`, `docs/design/catalog.json`, `App/app/templates/base.html` or a shared test file, and the page anchors of each brief are written against the state the previous brief leaves behind.
- A brief that stops (`blocked`) is finished by a fresh Haiku session on the same brief; the next brief does not start before it.

## Briefs

| # | Brief | Depends on | Risk | Status |
|---|---|---|---|---|
| 0124 | [CI fixes before the design switch](../tasks/0124-ci-fixes-funnel-popover.md) (funnel window upper bound, create popover reclamp) | none | low | todo |
| 0125 | [Design v2 tokens](../tasks/0125-design-v2-tokens.md) (three layers in tokens.css) | 0124 | low | todo |
| 0126 | [Design lint in CI](../tasks/0126-design-lint.md) (raw colours, inline styles, page CSS, catalog classes, legacy allowlists) | 0125 | low | todo |
| 0127 | [Vendored Lucide icons](../tasks/0127-lucide-icons.md) as an inline SVG macro | 0126 | low | todo |
| 0128 | [v2 controls](../tasks/0128-ui-controls.md) (`_ui.html`: button, field, badge, chip, menu, dialog, toast, empty, tip, pagination; `host2.css`) | 0127 | medium (every later page builds on these macros) | todo |
| 0129 | [host_page.html](../tasks/0129-host-page-template.md) (page header, four body kinds, one skeleton per kind, `_ui_layout.html`, cross-page geometry selectors) | 0128 | medium (shared geometry tests widened) | todo |
| 0130 | [Navigation shell](../tasks/0130-navigation-shell.md) (desktop sidebar, phone top bar, bottom tab bar, More sheet) | 0129 | medium | todo |
| 0131 | [Living component catalog](../tasks/0131-dev-ui-catalog-page.md) at `/dev/ui` with screenshot and coral-budget tests | 0130 | low | todo |
| 0132 | [Shared macros to v2](../tasks/0132-shared-macros-v2.md) (badges, row menu, copy, sync, send, empty state, identity) | 0131 | medium (macros used by every list) | todo |
| 0133 | [Dashboard](../tasks/0133-dashboard-v2.md) (detail kind) | 0132 | low | todo |
| 0134 | [Stays list](../tasks/0134-stays-list-v2.md) (list kind) | 0133 | medium (filter panel hooks) | todo |
| 0135 | [Stay detail](../tasks/0135-stay-detail-v2.md) (detail kind) | 0134 | medium (send controls, filing copy untouched) | todo |
| 0136 | [Remove the host ID check](../tasks/0136-remove-id-check.md) (button, panel, texts; status and route kept) | 0135 | HIGH (filing-adjacent; exact diff only) | todo |
| 0137 | [Remove legacy host actions](../tasks/0137-remove-legacy-actions.md) (sync copies, row send, code lists, slot, claim workarounds; Send all only for manual sending; demo controls kept, deduplicated) | 0136 | HIGH (filing-adjacent; exact diff only) | todo |
| 0138 | [Reports list, report detail, house book](../tasks/0138-reports-housebook-v2.md) | 0137 | medium (filing pages, classes only) | todo |
| 0139 | [Guest edit page, host side](../tasks/0139-guest-admin-form-v2.md) (form kind) | 0138 | low | todo |
| 0140 | [Properties list, property page, add property, businesses](../tasks/0140-properties-v2.md) | 0139 | medium (property partials, many test selectors) | todo |
| 0141 | [Invoices and the shared month filter](../tasks/0141-invoices-v2.md) (list, detail, form, picker, `_list_filter.html`, items grid CSS moved) | 0140 | medium (shared partial) | todo |
| 0142 | [Stay fees](../tasks/0142-stay-fees-v2.md) (list, period detail) | 0141 | low | todo |
| 0143 | [Cleaning pages, host side](../tasks/0143-cleaning-v2.md) (`cleaning.css` from base; shared cleaner page untouched) | 0142 | low | todo |
| 0144 | [Settings, Archive, Privacy requests, Guide, welcome](../tasks/0144-settings-v2.md) | 0143 | medium (UbyPort PIN panel: classes only) | todo |
| 0145 | [Smart locks and admin pages](../tasks/0145-smart-locks-admin-v2.md) (users, incidents, operations, funnel) | 0144 | low | todo |
| 0146 | [Cleanup](../tasks/0146-cleanup-v2.md) (one skeleton, dead macros out, legacy burn-down report) | 0145 | low | todo |

## Checkpoints for the owner

1. After 0131: open `/dev/ui` on staging and compare with `docs/design/prototype.html`; stop the lane if the controls look wrong, since every page brief reuses them.
2. After 0137: read both HIGH risk reports and run the test-map row "Filing, UbyPort, worker, claim" once (`cd App && .venv/bin/python -m pytest tests/test_ubyport_*.py tests/test_soap.py tests/test_worker.py tests/test_submission_*.py tests/test_stale_submission.py tests/test_filed_by_hand.py tests/test_filing_watchdog.py tests/test_police_*.py tests/test_deadline*.py tests/test_claim_*.py tests/test_endtoend.py -q --tb=short 2>&1 | tail -30`).
3. After 0146: decide from the burn-down table whether `host-controls.css` and `host-design0123.css` get a deletion brief (0147).

## Reports

Each brief writes `docs/tasks/NNNN-report.md`. The orchestrator reviewing a report updates the Status column here and `docs/context/status.md` (five lines at most).
