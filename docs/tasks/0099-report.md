# 0099 report: one shared list-page layout

Status: review. Executor: Claude (owner-authorized). Base `bd77446` (claude/quirky-lamport-9svmd1). No push.

## What changed

- **Macros** (`_components.html`):
  - `list_page_header(title, actions, meta, tabs)`: renders the notices slot (the setup banner), then the title row, then the tabs.
  - `sub_tabs(items)`: the one tab component. Tabs are plain links with `aria-current="page"`.
  - `list_toolbar(summary, chips, panel_id, actions)`: one toolbar for every list.
  - `list_section_heading(id, title, help)`: a plain `h2` plus `?`.
  - `empty_state(...)`: one message and one button. An optional caller block holds the mock-only demo loader on Stays.
  - `page_header` also gained a `tabs` argument, so every page shows its section tabs under the title.
- **Tab lists** are now computed in Python (`templating.section_tabs` / `page_tabs`) instead of `_host_navigation.html`, which is removed. The base.html include that drew the tabs above the title is gone.
- **Tabs per section:**
  - Stays: Stays · Police reports · Guest register (also on /submissions and /housebook).
  - Properties: Properties · Business & legal details · Door lock account. The lock tab appears only when the host has a lock account. These tabs also show on /entities and /smart-locks. The `.properties-shared` button row is gone.
  - Invoices: Invoices · Invoice settings (`/invoices/settings`, the existing redirect). The ghost "Invoice settings" button beside Generate invoice is gone. When /entities is opened with `next=/invoices…` it shows the Invoices tabs.
  - **Stay fees: no tabs.** Fee settings are per property (Settings → Reporting & fees), so there is no single page to link.
- **Pages:**
  - All four pages use `list_page_header`.
  - Properties: the "Last updated" sync time moved to the meta line under the actions. The toolbar shows a count summary. The guest-links section and the Archived section use the shared heading; the old Archived lede became its `?`.
  - Stays: chips, Filters, the summary, Save this view and Export CSV now sit in one `list_toolbar`. The saved-views list moved below the toolbar (it rendered above the title before).
  - Invoices and Stay fees: the toolbar comes from `_list_filter.html` using `list_toolbar`.
  - All empty states use `empty_state`.
- **Rows:**
  - Rows that now open on click: Dashboard stay rows (`article.clickable-row[data-href]`), Properties summary rows, archived property rows, and Stay fees "Not set up" rows (to the fee editor).
  - `initClickableRows` uses one selector (`tr[data-href], .clickable-row[data-href]`), also for j/k.
  - A click does nothing when it lands on a control, a row menu, the row actions or `.dashboard-row-actions`, or when it ends a text selection.
- **CSS:** one `/* 0099 */` block in `host.css`, covering header, tabs, toolbar, sections, empty state and the dashboard row hover/focus. The title row stacks at 760 px, as the shared header does. `host.css` and `app.js` are tagged `?v=20261013-0099`.
- **Strings:** `_LIST_LAYOUT_0099_STRINGS` in EN and CS (tab labels, property count).
- **Docs:** one line in `ui-decisions.md`. Combined plan §4 rule 1 is updated, because it said "tabs only on property pages".

## Unchanged

Form names, actions and CSRF; filter semantics; export links; saved views; Send / Send all and their guards; routes and data.

## Tests (App/, staging/mock/REQUIRE_BROWSER, pinned Chromium)

- **New:** `tests/test_host_list_page_layout_browser.py`, 5 passed. It checks:
  - DOM order (env notice → setup notice → title row → tabs → toolbar → panel) on all four pages, at 760/1024/1280/1440, rail expanded and collapsed, EN/CS.
  - The same left edge (±1 px) for title, h1, tabs, first tab, toolbar, notices and panel.
  - One gap above the tabs and one gap above the toolbar on every page.
  - At most one filled action, all actions the same height, actions right-aligned (stacked under the title at 760), meta under the actions.
  - Tab labels and `aria-current` on 8 pages; no tabs on Stay fees or on property pages.
  - Every row (dashboard, stays, properties, summary, invoices, fees) opens on click and on Enter and has a focus ring; More/Copy inside a row do not navigate.
  - Every empty state is the shared component with one button.
- **Updated** because they pinned old markup; each still asserts the same intent:
  - `test_stays_empty_workspace`, `test_first_property_step`, `test_properties_table_chips`: empty-state regex now targets the shared component; toolbar marker updated.
  - `test_host_properties_navigation`: the shared link is now a tab.
  - `test_properties_inline_controls_browser`: heading class.
  - `test_host_fee_navigation`: "no `/setup`" became "no legacy `/stay-fees/{id}/setup`", because the setup notice links `/setup`.
  - `test_host_filter_panels_browser`: chip selector.
  - `test_host_property_controls_browser`: the Properties list now has one tab bar; the property page still has none.
- **Template-touching sets:** 132 browser tests (ux_acceptance, list_cards, wide_geometry, quiet_dashboard, inline_controls, unsaved_changes, list_layouts, controls, fee/invoice navigation, filter panels, property controls/create/navigation, fit, stay actions, feedback, account nav, locks, help) plus 367 non-browser: all pass after the updates above.
- **Full suite:** `2 failed, 3447 passed, 3 skipped`.
  - The 2 failures are the known environment-only ones: `test_feed_dns_pinning` (concurrent) and `test_posthog_snippet_browser`.
  - The 3 skips are pre-existing evidence-capture gates.
- `ruff` (selected rules) clean. `context_lint` OK.

## Evidence

`docs/tasks/0099-evidence/{stays,properties,invoices,fees,dashboard}-{390,1280}-{en,cs}.png`, captured with `UBYHOST_CAPTURE_0099=1` on synthetic data.

## Notes / risks

- Detail pages that share a section's `nav` (stay detail, invoice detail, invoice builder, settings pages) now show their section tabs under the title instead of above it. The tabs are the same as before; only the position changed.
- Tab labels "Police reports" and "Guest register" (CS "Hlášení policii", "Domovní kniha") follow HOST_APP_DESIGN. The rail and Search keep "Reports" and "House book".
- The unused `.properties-shared` CSS is left in `host.css`.

## Owner steps

1. On staging, open Stays, Properties, Invoices and Stay fees in turn. The title, the tabs under it, the filter row and the list should start at the same left edge on each page.
2. On Dashboard, click anywhere on a stay row. The stay should open.
