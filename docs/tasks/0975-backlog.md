# 0975: B17 optional polish backlog

## 1. Objective

Decide retained or deferred for each B17 finding; only retained ones get a brief.

## 2. Context

Status: in-progress
Base commit: 7b0355c45ccdd2557a28edfcfe228aa1dc766e36. Source: master plan B17 and review report (all seven are "Opportunity", not confirmed defects). Rule: retain only if the change shortens or clarifies the task, changes no behaviour, and no other batch (B01, B03, B04, B07, B10, B12, B13, B16, plus B08/B14/B15/B18 file lists) rewrites the owning files. Briefs run after B01 to B16 are merged.

| Finding | Decision | Reason | Owning files | Waits for |
|---|---|---|---|---|
| G05 entry screen repeats context | Deferred | Fix is guest copy in `i18n.py` (many languages) and the guest shell/header; B01 rewrites `templates/guest/base.html`, B07 the guest form. Needs 390 px check with long property names in every language | `templates/guest/base.html`, `templates/guest/pin.html`, `i18n.py` | B01, B07 |
| G06 required-field errors | Deferred | Adds new behaviour (inline errors, focus, summary) on two pages another batch rewrites; not a pure clarification | `templates/guest/form.html`, `templates/guest_form_admin.html`, `static/guest-enhancements.js` | B01, B07 (guest), B03 (host Add stay) |
| L05 guide editor order and examples | Deferred | Reordering the card editor sits in the file B18 audits for the audience default; examples span 17 cards in 3 catalogs; B08 changes the guide flow | `templates/guest_guide_card.html`, guide copy keys | B08, B18 |
| S04 Stays header tools | Deferred | B10 owns the Stays list scope, filters and header | `templates/reservations.html` | B10 |
| X05 heading/back/tab roles | Deferred | A design-system decision, not a patch; B03 (shell), B13 (`_components.html`) and B14 (headings, back header) change the same components. Plan forbids an invented global system | `templates/_components.html`, `templates/partials/settings_back_header.html`, `docs/design/design-system.md` | B03, B13, B14 |
| F01 invoice empty state | **Retained (body line only)** | One reused sentence under the empty title; no new key, no CSS. The extra button is left out: the head already carries the action, a test asserts the empty block has none (0818), and rule 9 forbids repeating it. Owner may reopen the button | `templates/invoices.html`; tests `test_host_invoice_navigation.py` | none (only calls the `_components.html` macro B13 edits) |
| A03 operations raw codes | **Retained (alerts table, 8 kinds)** | Label first, raw code kept in `<code>`; unmapped kinds unchanged; nothing else on the page touched. B16 only owns Customers and Billing | `templates/admin_operations.html`, `host_i18n.py` (EN, CS), `test_admin_operations.py` | none |

Briefs: `docs/tasks/0975-f01-invoice-empty-state.md`, `docs/tasks/0975-a03-operations-readable-alert-kinds.md`.

Not covered by the A03 brief: mail and Havel kind columns, the other ~23 alert kinds, Vietnamese labels, precise-timestamp secondary detail.

## 3. Files

Two briefs listed above; this file changes no code.

## 4. Steps

Run the two briefs separately, after B01 to B16 are merged.

## 5. Do not touch

Deferred items stay out until the batch they wait for is merged.

## 6. Commands

None here; each brief lists its own.

## 7. Acceptance

Each brief's section 7.

## 8. Stop and ask

See each brief.

## 9. Report

Per brief.
