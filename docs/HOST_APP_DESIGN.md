# UbyHost host app design specification

**Status:** implemented signed-in host-app direction, 30 September 2026. Source baseline: `ceb1bc5ed34d020b0c6e21cac3c88bada74d1955`. See `docs/archive/plans/host-app-redesign/IMPLEMENTATION.md` for the exact delivered scope and route coverage. It extends the light-mode brand policy in `docs/DESIGN.md`. It does not govern the public site, login, or guest-facing forms.

## 1. Product idea

The host should always be able to answer three questions without decoding the interface: **Where am I? What needs me? What happens if I press this?** The app should feel like a tidy working desk. A first-time host can add one property and one stay; an experienced host can reach any record quickly. Simplicity means fewer decisions on each screen, not fewer capabilities.

The approved visual starting point is `docs/archive/plans/host-app-redesign/approved-preview.html`: warm near-white canvas, clear type, narrow rail with Search, compact action rows, restrained coral actions, and visible guest facts. The implementation should improve consistency and actual data handling; do not transliterate demo JavaScript into production.

### Non-negotiable UX rules

1. Show the object's name and useful context before its status: property, stay dates, guest or customer, amount or report period.
2. Give each page one obvious primary action. Keep secondary actions near the object or in a labeled menu. Destructive actions require a clear confirmation.
3. Use a sentence only when it explains a consequence, a missing prerequisite, or a recovery step. Never repeat a heading or explain the product inside every card.
4. Show real available actions. A status must come from persisted data. Never imply that UbyHost watches bank payments or has sent a municipal filing when it has not.
5. Keep successful records visible and scannable. Do not fill the page with congratulatory copy or empty decorative panels.
6. Use familiar nouns and verbs in English and Czech. Prefer “Guest details”, “Police report”, “Download PDF”, “Edit count”, and “Connect calendar” over internal model names.
7. Preserve access to advanced and legal functions through context, Search, and Settings. A shorter rail must not erase a route.

## 2. Navigation and information architecture

### Desktop rail

Fixed 208–224 px width when open; collapses to an icon rail using the existing control. Top: UbyHost wordmark, Search button with shortcut. Main links, without category headings:

1. **Today** → `/`
2. **Stays** → `/reservations`
3. **Properties** → `/apartments`
4. **Invoices** → `/invoices`
5. **Stay fees** → `/stay-fees` **only when at least one active, accessible property has a positive configured rate**. If none has a rate, show a quiet “Optional stay fee” entry inside the relevant property's settings, not a dashboard task or onboarding step. If the existing route still permits a direct visit, show its accurate empty state.

Bottom: Help, then the account button (name/avatar). Account menu contains Settings, Archived records, Privacy requests, Team (admin), Incidents (admin), language, and Sign out. Environment and impersonation indicators stay visible whenever relevant; do not hide them in the menu. Legal and support links remain available from Help or the bottom of Settings. Search opens the existing command palette and includes all destinations, properties, stays, and records the user is allowed to see.

Do **not** render property shortcuts or saved views in the default rail. Property shortcuts belong inside Search and on the Properties page. Existing saved-view behavior can appear as a chip above Stays filters for users who have saved views, without a blank rail region.

### Local navigation

| Location | Visible local links | Why |
|---|---|---|
| Stays landing | **Stays · Police reports · Guest register** | Records tied to stays remain discoverable in one place. `/submissions` and `/housebook` are both one click from Stays. |
| Stay detail | Guests · Police report, with a direct Invoice action | Guest facts and report state live with the stay. The unused `#money` anchor should not create an empty visual panel. |
| Properties landing | **Properties · Business details**; “Property tools” menu for all guest links and automation overviews | Business entities may be shared across properties. Each property shows its assigned entity and links to edit it. |
| Property detail | Bookings · Guest link · Police reporting · Business details · Optional stay fee | Settings are grouped by the property they affect. Technical fields appear only in the relevant section. |
| Invoices | All invoices · Invoice settings | Creation remains a prominent action; settings are one click away. |
| Stay fees | Period selector; property/group report details | This feature is independent of stay detail and is enabled per property. |

Retain existing URLs and backend handlers as deep links. The navigation redesign changes placement and wording first. Do not create redirect loops or break bookmarked URLs.

### Mobile

Use the implemented top bar with menu, logo, Search, and environment indicator. The account is at the bottom of the menu. The drawer includes the complete rail hierarchy; no additional bottom navigation is required. Give touch controls at least 44 × 44 CSS px. Do not rely on hover.

## 3. Layout, visual system, and language

- Light mode only. Use existing `App/app/static/tokens.css`: `--canvas`, `--surface`, `--ink`, `--muted`, `--line`, `--brand`, semantic state colors, 4 px spacing scale, system font, and reduced-motion tokens. Preserve the real UbyHost mark and existing host/guest token split. No gradient or competing accent system.
- Content max width approximately 1080 px for working pages, narrower for forms. On a 1024 px viewport, main content must not feel pinched by the rail; tables may scroll horizontally only as a deliberate last resort.
- Page header: small breadcrumb or category, strong page title, one concise orientation line **when needed**, primary action aligned right. Do not put the same copy in a hero card and the heading.
- Default content density: 16–24 px gaps between groups, 12–16 px inside rows, compact list cards with borders rather than deep shadows. No giant blank “achievement” boxes. Use one coral primary action per screen or decisive step.
- State color has a meaning: coral for an action, amber for attention, green for verified success, muted for waiting/neutral. Text labels must carry meaning without color. Do not show green “Paid” unless the manual invoice payment record actually says so.
- Numbers and dates use the app's locale. Keep the current Prague date basis where business logic uses it. Czech and English text must have matching i18n keys. A label should fit mobile without abbreviations that change meaning.
- Long identifiers (passport, VS, IBAN, invoice number) use a readable mono style and copy control where appropriate. Guest identity is visible inline to authorized hosts on stay detail, with wrapping and a direct Edit action. Avoid duplicating sensitive data in toast text, audit logs, screenshots, or client analytics.
- Focus rings, skip link, visible labels, keyboard search, escape-to-close, form errors adjacent to fields, and native semantics are required. Announce success or error once. Reduced motion must remove decorative animation.

## 4. Today: a useful work queue

**Owner selection, 2026-10-10: Quiet overview.** Keep the simple text-first design,
quiet status colors and consistent hover/keyboard feedback. No property photos
or decorative details. Show at most **five unique stay rows total** across the
dashboard. Routine stays are current or arrive within **30 days**, using Prague
today; real overdue/failed work takes priority even for older stays. Counts
must be calculated before truncation, with a visible additional-action count
when necessary and **View all stays** for the full list. See
[dashboard policy](DESIGN.md#dashboard-only-useful-information).
The 30-day window supersedes the earlier 14-day choice.

**Header:** “Dashboard” and the current date. “Add stay” and “Update calendars”
share action geometry. The owner reaffirmed the four white Quiet overview
cards: amber Needs action, taupe Waiting for guests, muted blue Ready to send,
Overdue red only when positive. Small dots and restrained attention lines;
zero counts stay neutral. Count the full candidate set before the five-row cap.
Open stay buttons and More share consistent columns across both row sections.
Owner's latest wording: label the row button **Open**; label invitation copying
**Copy guest form link** and copy the guest-facing registration URL.

**Needs you now:** compact rows ordered by actual urgency. Each row shows arrival/departure context, property, one task label (“1 guest missing”, “Check police report”, “Property needs setup”), and one action (“Open”, “Check report”, “Finish setup”). A second short line is allowed only if the action would be unclear, for example “No confirmation from UbyPort yet.” Avoid “2 of 3 registered. Share the invitation to finish check-in” when the count and button already say this.

**Current and coming up:** date, property, one meaningful status/task and a row link. Keep receipt access on the stay/report pages; do not add a separate activity feed to this overview. Do not place invoicing or fee work into the dashboard unless the backend can accurately establish a real action; the default place to find invoices and fees is their dedicated section.

**Empty state:** “Nothing needs you today.” followed by the next known stay or a single Add stay action. Do not show invented “all caught up” statistics.

## 5. Stays and guests

### Stays list `/reservations`

Existing archive actions use the owner-selected **Delete** label and explain
that the record moves to **Archived**. Preserve archive/restore behavior and
guards across host pages; see [action policy](DESIGN.md#delete-action-move-to-archived).

The owner's latest “all the time” direction is interpreted as an unbounded
**All dates** default, replacing the earlier current/upcoming default. Keep
Upcoming/current and Past available as views. Default collapsed summary:
**All properties · Active**. Show dates only for an explicitly applied custom
range, using one **Stay dates** control in the panel. Keep existing status,
property, archive, list/timeline and saved filters. A row shows arrival date,
property or booking label, stay range, guest count, and only a meaningful status.
“Add stay” opens a short path: property → dates → expected guests → save.
Calendar import, manual creation and sync remain available. Empty states
distinguish no property, no calendar, no matching filter and no stays.

### Stay detail `/reservations/{id}`

Top: property or stay label, dates, one next-action panel, secondary actions (Edit stay, Invoice, invitation/copy link) in a restrained menu. Render **Guests** immediately after the next step. For each saved guest, show name, document type and number, date of birth, nationality, residence, purpose, stay dates, and signature/identity state if present in backend, grouped into two readable rows. Do not make the host open every guest simply to read existing details. Saved guest cards remain visible without a disclosure. Missing slots stay visible underneath them.

The guest count row shows “2 of 3 guests” with **Edit count** and **Add guest**. A missing slot offers “Share invitation” and **Remove extra guest** when the expected count was entered by mistake. Removing an empty expected slot edits `expected_guests_override`; removing an actual guest uses the existing authorized guest-delete/archive rules. The UI must explain when a submitted record cannot be removed or changed and provide the appropriate correction path. Never silently remove a reported guest or rewrite a prior report.

The police report section shows the actual persisted state and an appropriate action: review/send, view result, fix rejected guests, download receipt or errors. Do not say “Waiting for guest 3”, “Mode: Manual review”, or “Result unknown” as generic boilerplate. “Guest details needed” or “No confirmation yet” is enough, with a concrete next action. Keep `#reports` and other deep-link anchors working. Do not add a stay-fee panel to this page; fee decisions belong on the fee detail page per the approved fee plan.

### Host guest form `/guests/{id}` and new guest

Organize fields as Identity, Address and stay, Document, Signature/verification. Preserve every existing validation and protected data path. Show `doc_type` directly with document number. Keep 422 field values and errors, edit/restrict/verify/resend/archive actions, and clear return navigation to the originating stay, report, or register. Do not change guest-facing forms.

### Police reports `/submissions` and detail

Local Stays tab “Police reports”. List shows submission time, property/stay, result based on UbyPort response, and a direct receipt or errors download where available. Detail shows actual result, the affected guests and a “Fix stay” path. Keep XML diagnostics behind a “Technical details” disclosure. Never show “confirmed” without a confirmed result.

### Guest register `/housebook`

Local Stays tab “Guest register”. Preserve filter, archival, retention, legal information, CSV, guest forms/PDF ZIP, and restricted-data behavior. Retain the working register table and export controls under the shared host visual system. Do not change legal export contents as a visual refactor. Restriction and deletion affordances must retain confirmation and privacy behavior.

## 6. Properties and first setup

### Property list and detail

Property list cards/rows show name, location, one truthful setup state, and a clear Open action. Owner decision 2026-10-10: remove the duplicate Property tools menu inside individual property pages. The Properties landing page provides useful cross-property overview links, also reachable through Search. Business details are a local tab or section of Properties, because they are used by properties and invoices. Do not duplicate a legal entity just to make the UI appear property-specific; show the assigned entity on each property and provide a direct link to its shared record.

Property detail groups existing sections into readable cards: **Bookings** (feeds/sync), **Guest link** (copy URL, PIN, regenerate with warning), **Police reporting** (UbyPort credentials, test connection, code lists, automation), **Business details** (assigned entity, contact), **Stay fee** (optional, rate and council/payment inputs). Keep advanced technical fields in their section, not on the landing view. Section links or anchored tabs should be stable across failed submissions.

### First setup and onboarding

The main path is **Add property → connect booking calendar or add a stay manually → prepare guest link → check reporting details → use the app**. Each step has one task, a visible Skip/Later when optional, and a return route. Do not require invoices or stay fees before a first stay. Existing demo-load/reset may remain in onboarding with a conspicuous demo label. A host can return to any setup card from Properties, without losing work or encountering a dead-end success screen.

### Global guest links and automation

`/guest-links` and `/automation` remain working overviews for multi-property management and old links. They are reached from overview links on the Properties landing page and Search. Each row links to the property's exact setting, so edits occur in context. Keep PIN, resend, automation, test connection, and error details as supported today. Avoid a global “on/off” appearance if settings are per property. Preserve shared-lock account setup, contextual property links and return navigation.

## 7. Invoices

The rail entry is always visible. List header has **Generate invoice**, an Invoice settings link, and a simple list: invoice number, customer, issue date, amount, direct **PDF** button. A row opens detail. Do not show a bank-derived “Paid/Unpaid” dashboard: this codebase only has host-recorded payment markers and invoice send state. If a recorded payment is displayed, label it “Payment recorded” and provide its recorded date on detail; an absence is “No payment recorded”, not evidence the customer has not paid.

Creation flow: select seller/legal entity if multiple, customer, items/tax, payment terms, review, issue. The stay action opens the existing standalone builder at `/invoices/new`; there is no stay prefill or invoice-to-stay relationship in this delivery. Do not invent one. Preserve VAT payer and non-payer behavior, numbering, immutable issued snapshots, correction/cancellation, email send flow, and validation after HTTP 422. Show errors next to fields; do not discard entered values. Preview must clearly say it is a preview. Issued detail has a prominent **Download PDF** action and secondary Send, Record payment, Cancel/correct only where allowed. Do not invent automatic reconciliation.

## 8. Optional stay fee

The fee plan in `docs/plans/stay-fee-remittance/PLAN_STAY_FEE_REMITTANCE.md` owns calculations and legal data. This design owns its host-facing organization. A property opts in through a rate greater than zero in its property panel; no onboarding nag, guest form field, or stay-detail fee card. The sidebar item appears after opt-in.

**List `/stay-fees`:** period selector; rows show property, locality/rate, period, liable and exempt nights, calculated total. Clicking opens detail. Use the report unit defined by the current audited fee implementation. The tested base version groups some properties by legal entity, variable symbol and cadence; a separate audit is changing this. This design does not authorize retaining or restoring that grouping. Preserve newer per-facility reports and finalized snapshots when integrating, and label exactly what the actual downloaded report contains.

**Detail `/stay-fees/{apartment_id}?month=…`:** first row gives period and included properties; clear blockers link to the exact property or entity field to fix. Then concise totals, **Download PDF** and **Download CSV** actions when their actual routes exist, council payment details with copy buttons and QR Platba when complete. “Payment details ready” means a QR can be made, not that payment occurred. No paid status, bank polling, municipal submission status, or filing claim. Guest decisions appear in a readable list beneath the summary: guest, stay dates, nights, liable/exempt state, amount, and a small Change action. Require a reason for host exemption as specified in the fee plan, with the existing data-minimizing hint. Never put sensitive exemption reasons on the public PDF or audit row.

**PDF:** retain the selected **Invoice Companion** style from `docs/plans/stay-fee-remittance-design/DESIGN.md` and its sample PDF. The older `stay-fee-document*.html/.jpg` files are content references, not the final visual design. Preserve the current audited calculations, owner access, finalized snapshots and legally required protected-register fields. Never apply an older grouping or restricted-row redaction rule from a preview over a newer audited implementation. A disabled download explains what must be fixed or when the period is not ready.

## 9. Settings, account, and advanced work

Account menu → Settings opens a concise index of Workspace, Data and archive, Privacy, Security and team (role-aware), and Help. Existing `/settings` technical configuration, retention, backups, export, notification/mail, and destination information remain reachable through cards or anchored subsections. `/settings/archived` is a full page with stay/property/guest/entity filters and restore controls. `/privacy-requests` has clear request states and actions. `/admin/users` and `/admin/incidents` stay admin-only. Password and 2FA pages are reached through account settings; the login experience itself is outside this redesign. The guide must reflect the new navigation and include a route back to the task that opened it.

Role, impersonation, environment, authentication, and error banners are functional controls. Keep them visible and accurate even if they take space; simplicity does not justify hiding a risky state. Form confirmation, empty states, 403/404, loading, offline/retry, and long-content layouts must use the same shell and typography.

## 10. Copy and state examples

| Situation | Heading / label | Supporting text only when necessary | Action |
|---|---|---|---|
| One guest slot missing | `1 guest missing` | None if count and invitation button are visible | `Share invitation`; `Remove extra guest` |
| UbyPort result has not arrived | `No confirmation yet` | `Check the report before sending again.` only if resend is offered | `Check report` |
| Property has no feed | `Connect a calendar` | `Stays will appear here automatically.` | `Connect calendar` |
| Invoice has host marker | `Payment recorded` | Recorded date on detail | `Download PDF` |
| Invoice has no marker | `No payment recorded` | `Update this when you receive payment.` on detail | `Record payment` |
| Fee PDF blocked | `Report not ready` | Name the exact missing payer, council, VS, or unfinished period | `Fix details` |
| Fee payment QR exists | `Payment details ready` | `Scan in your banking app.` | `Copy account` |
| No actions today | `Nothing needs you today` | Next stay date if known | `View stays` |

## 11. Review criteria

Test with someone unfamiliar with the product: they should find a stay, identify missing guest details, correct an accidental guest count, inspect a saved guest without opening another page, find a police report, download an invoice PDF, find business details under Properties, and locate an enabled stay-fee report without coaching. On mobile and desktop, every task should have a visible route and honest state. See `docs/archive/plans/host-app-redesign/TEST_REPORT.md` for measured checks and limitations. Real usability testing with novice hosts is a separate release check; it was not conducted here.

## 12. Implementation boundaries and integration authority

The shared host shell and primitives cover signed-in destinations. Today, navigation, property organization, stay/guest detail, invoice list/detail and notifications have targeted layout changes. Other host forms, records and admin pages inherit the shared design while retaining their existing content and handlers. This is not a claim that every screen was rebuilt from scratch.

The prototype contains sample states and is a visual reference. Production controls use real backend data and existing routes. `IMPLEMENTATION.md` takes precedence over prototype behavior for delivered capabilities. This document governs presentation; current audited fee and security contracts govern legal data and backend behavior.

No database schema migration, dependency update, live filing, real e-mail delivery, public deployment or bank reconciliation is part of this change.
