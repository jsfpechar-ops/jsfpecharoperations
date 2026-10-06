# Implementation map and contracts

## Baseline and architecture

Base: `ceb1bc5ed34d020b0c6e21cac3c88bada74d1955`. Branch: `codex/host-app-redesign`. Server-rendered FastAPI/Jinja; plain CSS and JS. No framework, bundler, new dependency, schema migration or background task was introduced.

`base.html` adds `host-workspace` and loads `host.css`/`host.js` only when `show_nav` is true. The host layer loads after legacy shared styles; aliases are rebound on `body.host-workspace` because root-resolved CSS aliases otherwise retain the old 264px sidebar. Host width is 216px. Existing public, login, guest, PDF and e-mail presentation remains governed by its own styles. The shared navigation script has mobile drawer accessibility improvements; asset versions are bumped so returning users receive them.

## Changed code map

| Files under `App/app/` | Responsibility |
|---|---|
| `static/host.css` | Host palette, narrow rail, typography, cards, tables, inputs, local tabs, property cards, mobile layout, notifications, semantic status colors. Scoped overrides, not a duplicate app. |
| `static/host.js` | Opens anchored details sections, including nested sections; expands invalid fields; closes account/tools menus; updates notification count. |
| `static/app.js` | Existing drawer now focuses content, traps Tab while open, restores focus, uses inert for obscured main/closed rail; existing menus/search/forms remain. |
| `templates/base.html` | Four core rail items, conditional fees, Search, Help/account, contextual navigation and in-flow notification partials. Environment and impersonation remain visible. |
| `templates/_host_navigation.html` | Stays/reports/register, Properties/business/tools, invoices/settings, account sections. Existing URLs retained. |
| `templates/_host_alerts.html` | All open alerts in an expandable region. Critical/error starts open. Existing dismiss hooks and non-dismissible resign alerts retained. |
| `host_design_i18n.py`, `host_i18n.py` | Matching EN/CS host-only copy overlay loaded after older catalogs. No guest copy replacement. |
| `templating.py` | Owner-scoped active-property fee discovery and exact haler currency formatter. No fee computation changes. |
| `routes/api.py` | Additional command-palette destinations and role-aware admin links; existing entity/stay access filtering retained. |
| `templates/dashboard.html` | Date/count header, compact urgency-ordered tasks, correct missing-count/failed state and setup guidance after actual work. |
| `templates/apartments.html`, `apartment_form.html` | Property-first entry, shared business links, six-card hub, existing sections in native details, sticky save. All existing inputs remain in the same form. |
| `templates/reservations.html` | Saved views moved from sidebar to Stays. Existing timeline, search and filters retained. |
| `templates/reservation_detail.html` | Property/date/source header, lean next action, inline identity fields, direct Edit, count correction, real report section below guests. |
| `routes/admin.py` | New atomic remove-empty-slot handler described below. Existing guest deletion is not replaced. |
| `templates/invoices.html`, `invoice_detail.html` | PDF links in list and detail; manual payment copy; precise decimals without integer truncation. |
| `templates/stay_fee_detail.html`, `routes/stay_fees.py` | Fix-details wording and additional guest/property ownership association check. Backend calculations/PDF generation unchanged. |
| `templates/settings.html`, `guide.html` | Contextual Settings/Help index; old dashboard illustration removed. |
| `App/scripts/backup_data.sh` | GNU/BSD date/stat/find portability correction exposed by full tests on macOS. Retention behavior unchanged. |

All changed test files appear in `manifest.json`. Existing assertions for ownership, state transitions, security and legal behavior remain. Assertions tied specifically to the old rail, old table shape or inaccurate currency text were updated to the selected design.

## Route coverage

“Shared” means the existing screen receives the host shell, local navigation, typography, forms/tables/pills and responsive styles; it does not mean every field layout was rewritten.

| Area | Routes / actions | Delivered treatment |
|---|---|---|
| Today | `/` | Targeted compact task layout, real counts, existing urgency/order, empty/setup states. |
| Stays | `/reservations`, add/edit/manual/import/sync, list/timeline/saved filters | Shared + saved-view relocation. All original handlers retained. |
| Stay detail | `/reservations/{id}`, quick edit, archive/restore, copy invitation, report/send | Targeted guest-first layout, direct identity details and Edit count. |
| Guest form | `/guests/{id}`, `/reservations/{id}/guests/new` | Shared; existing identity/signature/verification/retention/error contracts remain. |
| Police reports | `/submissions` and submission detail/downloads | Stays local tab + shared; real result/receipt/XML/error controls remain. |
| Guest register | `/housebook`, CSV/PDF/ZIP actions | Stays local tab + shared; export rules remain backend-owned. |
| Properties | `/apartments`, `/apartments/new`, `/apartments/{id}` | Targeted hub, progressively disclosed settings, direct entity link and calendar controls. |
| Business | `/entities`, `?edit={id}`, create/save/archive | Properties local tab + shared; one legal entity can serve multiple properties. |
| Guest links | `/guest-links`, PIN/link/QR/regenerate operations | Property tools + Search + shared; property-specific settings reachable from hub. |
| Automation | `/automation`, per-property anchor, test/settings | Property tools + Search + shared; existing opt-in and UbyPort behavior retained. |
| Invoices | `/invoices`, `/invoices/new`, `/invoices/{id}`, `.pdf`, settings/payment/cancel/correct/send | Targeted list/detail and shared form. Standalone builder remains standalone. |
| Stay fees | `/stay-fees`, `/{property}?month=`, PDF/CSV/payment/decision actions | Conditional rail + shared; property opt-in hub. No fee panel on stay or guest form. |
| Settings | `/settings`, `/settings/archived`, backups/exports/retention/technical controls | Account menu + section index + shared. Environment-sensitive actions preserved. |
| Privacy | `/privacy-requests` and request actions | Account/local navigation + shared; owner/role enforcement retained. |
| Admin | `/admin/users`, `/admin/incidents`, impersonation | Admin-only account/Search links + shared shell. No host access expansion. |
| Help/setup | `/guide`, `/onboarding` | Updated navigation guide and shared styling; no fee requirement added to onboarding. |
| Auth/security | Login, password/2FA flows and access-denied pages | Existing security and auth flow retained. No login redesign. Host shell used only where existing template opts into it. |
| Public/guest/PDF/mail | Existing routes and renderers | No visual redesign. Existing tests exercise them for regressions. |

## Empty-slot mutation contract

`POST /reservations/{reservation_id}/remove-empty-slot`

Inputs: normal CSRF token and `expected`, the headcount rendered when the page loaded. Login and current owner-scoped reservation access are required. Invalid ID or another owner's stay is inaccessible.

1. Parse integer; accepted range is 2–60. Never reduce an expected count of 1 to zero.
2. Atomic UPDATE sets `expected_guests_override = expected - 1` only while current headcount matches the submitted value, status is active, reservation is not archived, count of nonarchived guest rows is less than expected, and apartment owner still matches the current workspace.
3. If another tab changed the count or a guest filled the final slot, do not mutate; show the refresh/review message.
4. No guest row is deleted or rewritten. Audit contains reservation ID/new count only.
5. Call existing `reporting.submit_stay_if_complete` after success, preserving automatic-reporting opt-in. Confirmation tells the host that automatic reporting may start if this correction completes the stay.
6. Return to the stay `#guests`. A replay is rejected by the expected-count condition.

Editing an actual saved guest uses existing host guest controls and protections. This action is explicitly for a mistaken empty expected slot.

## Property save preservation

The UI changes sections, not the write contract. Keep every input and checkbox in the original property form so editing one section cannot zero credentials, calendar settings, legal-entity assignment, fee rate, cadence, council account or other sections. Native validation reveals a closed details ancestor before focusing an invalid input. Anchor navigation must open the addressed section on both initial page load and repeated clicks. Shared business records still use `/entities?edit={id}`; no duplicated entity is created by navigation.

## Invoice preservation

`/invoices/new` remains the standalone builder. Stay action only navigates there. Keep `build_draft`, `validate_for_issue`, 422 values, payer/nonpayer VAT, numbering, immutable issued snapshots, manual payment record, cancellation/correction and signed downloads. PDF buttons call existing authenticated routes. `_money_czk` formats integer haler using Decimal and ROUND_HALF_UP; fractional item quantities divide the total before display. It does not change invoice totals or stored data. “Payment recorded” means a host marker, never automatic bank verification.

## Fee and concurrent-work reconciliation

This snapshot was tested against the fee implementation in base `ceb1bc5ed34d020b0c6e21cac3c88bada74d1955`. A separate task reports commit `cbbc632` on `fix/stay-fee-legal-audit`; it was not merged or verified here. Reported changes include per-facility reports, finalized snapshots and complete protected-register identity fields. Those reports are integration context, not a legal verification by this redesign task.

Before integrating, inspect current main and that task's final audited commit. Preserve its calculation, reporting-unit, snapshot, export and legal-retention semantics. Resolve overlaps as follows:

- `routes/stay_fees.py`: retain newer route/model contracts; add the guest-to-selected-property association check in the equivalent current decision handler.
- `templates/stay_fee_detail.html`: preserve newer period/finalization/export controls; apply shared visual classes and concise truthful labels. Do not remove blockers to simplify the screen.
- `host_i18n.py`: preserve audit strings and append the host overlay once; verify overlay wording still describes actual state.
- `apartment_form.html`: preserve newly added audit fields in the original form, placing them in the fee section. Do not drop values with an older payload copy.
- `db.py`, fee domain/PDF/CSV modules: this redesign does not replace them. Newer audited source wins.
- fee docs: never restore old group totals or restricted-identity redaction rules based on `approved-preview.html` or an earlier design plan.

Run the full suite after reconciliation and add tests for any changed combined behavior. Green tests from this snapshot do not certify that future merge.

## Accessibility and responsive behavior

216px desktop rail, existing compact icon state, mobile drawer at the existing breakpoint. Visible text accompanies primary navigation. The menu keeps focus inside while open; Escape restores the trigger and closed drawer is inert. Search retains its existing dialog and keyboard handling. Details elements are native and usable without enhancement. No field is made required merely for aesthetics. Tables retain their existing responsive data labels. Notifications occupy document flow and cannot cover mobile actions. Warning/critical statuses use text, not color alone.

## Release / rollback

No data migration. A source revert restores the prior UI; guest-count changes already made are ordinary persisted data and are not undone by reverting the UI. Keep backup/restore and pre-release security checks required by the repository. Review a feature branch before merging. No deployment was performed here.
