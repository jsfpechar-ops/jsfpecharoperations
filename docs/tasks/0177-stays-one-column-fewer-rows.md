# 0177: Stays list shows the property once and 15 rows per page

Status: todo
Depends on: 0176 | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session

## 1. Objective

Owner: the Stays list is overwhelming; the Stay and Property columns repeat the same property name, and there are too many rows. Decisions (owner, 2026-10-20): keep one column, and cap the rows.

1. Remove the separate Property column from the Stays table. The Stay cell shows the property's colour dot and the stay label as its title (the property name, or a manual stay's own summary, exactly as `stay_label` is built today), and below it the source badge. When the stay label differs from the property name (manual stays with their own summary), add the property name as a muted third line, so no information is lost.
2. The page size drops from 50 to 15 rows.

## 2. Context

Template `App/app/templates/reservations.html` (table at about lines 131-205: columns `stay-col-stay`, `stay-col-dates`, `stay-col-property`, `stay-col-guests`, `stay-col-reporting`, `stay-col-actions`; the property cell uses `property_identity(...)`; the Stay cell holds `.stay-identity-link` and `.stay-col-source`). Page size: `RESERVATION_PAGE_SIZE = 50` in `App/app/routes/admin.py` line 2820, rendered by the pagination line in the template (about line 210). The phone card layout reads `data-card` roles (`primary`, `secondary`, `meta`, `badge`, `actions`): the phone card currently shows the property as the `secondary` line, so keep a `secondary` role on a visually hidden-on-desktop element, or move the `secondary` role to the Stay cell's property line, so the phone card still shows the property once.

## 3. Files

`App/app/templates/reservations.html`, `App/app/routes/admin.py` (one constant), `App/app/static/host2.css` (append `/* 0177 */` only if needed, tokens only; S1 and S2 apply), `App/app/templates/base.html` and `App/tests/static_versions.json` only if host2.css changed (new key ending `-0177`), tests that count rows or columns of the Stays table (find: `grep -rln "stay-col-property\|RESERVATION_PAGE_SIZE\|page_size\|Showing 1" App/tests | head`), `docs/tasks/0177-*`.

## 4. Steps

1. Read the table section of `reservations.html` once (grep the line numbers first). Remove the `<th class="stay-col-property">` and its `<td>`. Put the colour dot (`property_identity` gives dot and name; reuse its dot markup, do not duplicate the colour logic) before the title in the Stay cell. Add the muted property line when `stay_label != reservation.internal_name`. Keep `aria-label` of the row unchanged.
2. Set `RESERVATION_PAGE_SIZE = 15`.
3. Fix tests that assumed 50 rows per page or the Property column: change only the numbers and selectors. If a test seeds 51+ stays to see a second page, seed 16+ instead. Do not loosen any other assertion.
4. If CSS was needed, run `python3 scripts/design_lint.py 2>&1 | tail -2` (repo root), bump the host2.css key, then from `App/`: `.venv/bin/python tests/test_static_versions.py --write && .venv/bin/python -m pytest tests/test_static_versions.py -q 2>&1 | tail -3`.
5. From `App/` run the unit tests you touched, then the browser tests (foreground, timeout 600000, `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium`): `.venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_a11y_guard_browser.py tests/test_host_list_page_layout_browser.py -q -rs 2>&1 | tail -8`. The known failure `test_list_pages_share_order_edges_and_rhythm` is expected; any other failure must be fixed or reported. Then from the repo root: `git checkout -- docs/tasks/0102-evidence && git clean -fdq docs/tasks/0102-evidence` (skip if refused).
6. One screenshot at 1280 and 390 px of `/reservations`: from `App/`, `.venv/bin/python /mnt/project-files/design-reset/tools/shots.py --new-app $PWD --out ../docs/tasks/0177-screenshots --pages "/reservations" --widths 390,1280 2>&1 | tail -2`.
7. Commit: `git add App docs/tasks/0177-* && git commit` with message "0177: Stays shows the property once, 15 rows per page" and the two trailers given by the orchestrator.

## 5. Do not touch

Filters, other pages, any other assertion; hard rules 1, 3, 8.

## 6. Commands

As in each step.

## 7. Acceptance

- [ ] No Property column; property still visible once per row on desktop and phone; 15 rows per page; tests pass with 0 skipped (except the known failure).

## 8. Stop and ask

An anchor is missing, or a test fails twice for a reason other than the known failure.

## 9. Report

`docs/tasks/0177-report.md`, short; `Status: review`.
