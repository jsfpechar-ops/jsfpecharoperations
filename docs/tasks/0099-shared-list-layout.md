# 0099: One shared list-page layout

Status: review | Executor: Claude (owner-authorized) | Branch base: claude/quirky-lamport-9svmd1 (bd77446) | Report: [0099-report](0099-report.md)

## 1. Objective

Owner decision 2026-10-13: Stays, Properties, Invoices and Stay fees are sibling lists, but each one had its own layout. Stays had its tab bar above the title, Properties had a "Business & legal details" button under the title, and Invoices had an "Invoice settings" button beside Generate invoice. Give the four pages one layout so hosts learn it once.

## 2. Context

Supersedes combined plan §4 rule 1, "tabs only on property pages", for list pages ([plan](../plans/host-ux-combined-staging.md#4-ux-reconciliation-senior-design-rules)). This change builds on 0079 (Stays row actions), 0084 O2 (list cards), 0091 (Stays row/card layout) and 0098 (Properties summary).

## 3. Files

- `App/app/templates/`:
  - `_components.html` (the macros)
  - `base.html` (local-nav include removed, `?v=20261013-0099`)
  - `_host_navigation.html` (removed)
  - `reservations.html`, `apartments.html`, `invoices.html`, `stay_fees.html`, `_list_filter.html`, `dashboard.html`
- `App/app/templating.py` (`section_tabs`, `page_tabs`)
- `App/app/static/app.js` (`initClickableRows`)
- `App/app/static/host.css` (`/* 0099 */`)
- `App/app/host_i18n.py` (`_LIST_LAYOUT_0099_STRINGS`)
- The tests

## 4. Steps

Every list page shows these blocks, in this order:

1. **Notices.** The environment banner (from base) and the "Continue setup" banner (from `list_page_header`).
2. **Title row.**
   - Title on the left. Actions on the right: at most one filled primary, the rest outline, all the same height.
   - Small meta (Last updated) under the actions.
   - At 760 px and below, the row stacks like every other page header.
3. **Sub-page tabs**, directly under the title row (`sub_tabs`). They are plain links, and the open page has `aria-current="page"`.
   - Stays: Stays · Police reports · Guest register. They also show on /submissions and /housebook.
   - Properties: Properties · Business & legal details · Door lock account. As before, the lock tab only shows when the host has a lock account. These tabs also show on /entities and /smart-locks.
   - Invoices: Invoices · Invoice settings. The second tab is `/invoices/settings`, the existing redirect to Invoice details. When /entities is opened from Invoices it shows these tabs.
   - Stay fees: no tabs. Fee settings are set per property, so there is no single page to link to.
4. **Toolbar** (`list_toolbar`).
   - Left: chips, Filters and the applied summary.
   - Right: Save this view and Export CSV.
5. **One list panel.** Tables and list cards are unchanged.
6. **Secondary sections**, each with a plain heading plus a `?` (`list_section_heading`).
7. **Empty states** use `empty_state`: one message and one button.
8. **Clickable rows.** Every list row is a full click target, including the Dashboard stay rows. Click, Enter or Space opens it, and it shows a focus ring. Controls inside a row keep their own action, and selecting text does not open the row.

## 5. Do not touch

Form names, actions and CSRF; filter semantics; export links; saved views; Send buttons and their guards; routes and data.

## 6. Commands

From `App/` with the staging/mock/REQUIRE_BROWSER env, run `pytest tests/test_host_list_page_layout_browser.py -q -rs`. With `UBYHOST_CAPTURE_0099=1`, the test writes screenshots to `docs/tasks/0099-evidence/`.

## 7. Acceptance

- The new test passes with 0 skipped.
- The template suites listed in the report pass.
- The full suite passes apart from the known environment-only failures.

## 8. Stop and ask

Stop and ask before any route or data change other than computing tab hrefs.

## 9. Report

See [0099-report](0099-report.md).
