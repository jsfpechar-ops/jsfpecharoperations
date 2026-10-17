# Host navigation and one editor per setting

Status: approved for phased Cursor implementation and staging review — production awaits explicit staging-candidate approval.
Owner: Josef | Prepared: 2026-10-12 | Base: `c4c8f979319e53341833065b2a8790c30159581f` (current main source base; planning branch `task/host-navigation-plan`)

## Current owner corrections and execution entry

[Production UX corrections](production-host-ux-corrections.md) supersede conflicting older parser, platform, active/controller-toggle, disclosure and onboarding instructions. Start with [the new Cursor prompt](production-host-ux-cursor-prompt.md). 0087–0094 deliver the urgent corrections and revised property navigation; 0072–0074 are replaced by 0094. Remaining 0075–0086 stay gated until their exact patches are refreshed against the reviewed correction integration SHA. Essential settings are visible; routine explanations use shared ? help, not More options. Production remains behind explicit staging-candidate approval.

## 1. Outcome and approval scope

Make the signed-in host app easier to scan, navigate and maintain. Preserve the familiar warm visual system and property shortcut cards. Each setting has one canonical editor; other pages summarize it and link to that editor.

The owner selected the combined property concept in chat: **Overview · Bookings & calendars · Settings**, with four grouped sections inside Settings. The owner also agreed with applying the ownership principle across the host app. On 2026-10-12 the owner approved the full design set and requested detailed Cursor delivery, first staging then production after approval. Implementation proceeds through the numbered briefs and integration-only review protocol; no main merge or production action occurs before explicit approval of the implemented staging candidate.

The [design gallery](host-navigation-design-review.html) is approved for direction. Follow [the detailed execution protocol](host-navigation-execution-protocol.md) and [Cursor master prompt](host-navigation-cursor-prompt.md). Generated boards illustrate hierarchy and navigation using fictional data; they are not screenshots of a working build, complete field specifications or proof of accessibility. The route/data contracts and acceptance criteria in this plan take precedence over abbreviated image text.

## 2. Scope and boundaries

Included: Properties list/detail, property calendars and settings, contextual guest-link and automation configuration, shared business/invoice configuration, shared lock-account navigation, Dashboard, Stays list/detail, invoice list/creation/detail navigation, optional stay-fee list/detail/setup navigation, account settings and the existing host links to reports, register, archive, privacy and Help.

Keep public marketing, login, guest-facing registration, PDF document designs, statutory export content, filing state machine, actual report sending, lock/PIN lifecycle, fee calculations, issued invoice snapshots and all retention/access rules under their existing owners. This plan changes presentation and editor ownership; it does not authorize changes to those contracts. No framework, dependency, schema migration, new analytics or outbound integration is proposed.

Reports, Guest register, shared lock accounts, archive and privacy retain their current feature-specific layouts while inheriting shared navigation, spacing and controls. Admin destinations remain role-aware. This is not a separate redesign of every technical or legal screen.

## 3. Verified starting point

Targeted working-tree reads, not a whole-repository audit:

| Finding | Evidence | Consequence |
|---|---|---|
| Plain FastAPI/Jinja2 and JavaScript/CSS | `docs/context/architecture.md` | Reuse the existing stack; no SPA or new router. |
| Property page owns guest-link and automation configuration already | `App/app/templates/apartment_form.html`; `App/app/routes/admin.py` GET `/guest-links`, GET `/automation`; task 0066 report | Keep those old URLs as compatibility redirects. Do not recreate independently editable global pages. |
| Property update is a broad form save | `admin.py` `_save_apartment_form`, `_apartment_payload` | Hiding sections or dropping fields can reset unrelated values. Preserve the existing full-form contract in the first navigation change. |
| Missing automation fields are specifically preserved now | `_save_apartment_form` removes timing keys when `automation_mode` is absent | Retain the regression protection; do not assume all fields have this protection. |
| Address wizard has a distinct scoped save | `_save_address_only`; task 0066 report | Keep its limited payload; do not route onboarding through a broad settings POST. |
| Fee fields already have a shared template | `_stay_fee_fields.html`, included by property and `stay_fee_setup.html` | Reuse this positive pattern. Consolidate overlapping save/validation paths and canonical navigation, not copy the form again. |
| Fee setup still has a dedicated save path | `routes/stay_fees.py` `_fee_values`, GET/POST `/stay-fees/{apartment_id}/setup` | Compare its semantics with the property save before consolidating; preserve IBAN-only accounts and exact field clearing behavior. |
| Shared business edit and invoice settings overlap | `entities.html` `operator_fields`; `invoice_settings.html`; their handlers | Define field ownership before redirecting or extracting shared fields. Keep both business identity and invoice-specific capabilities. |
| Invoice creation is tied to a stay | GET `/invoices/new` uses `reservation_id`, renders `invoice_stay_picker.html`, checks stay eligibility and an existing invoice | Preserve this current implementation. The older standalone-builder paragraph in `HOST_APP_DESIGN.md` is stale for this contract. |
| Earlier property-hub report was not wholly green | `docs/tasks/0066-report.md`: 6 failures, 3138 passes, 4 skips; browser geometry/copy failures | Capture a fresh baseline. Do not call an unrun checkout green or suppress failures. |

## 4. Navigation and editor ownership

Global rail stays **Dashboard · Stays · Properties · Invoices · Stay fees** with Search above, Help and Account below. Preserve current feature eligibility, environment/impersonation warnings and account roles. Do not force tabs onto pages whose primary task is searching a list.

| Surface or data | Canonical destination | Other entry points |
|---|---|---|
| Property overview | `/apartments/{id}`, Overview | Properties rows, Search and breadcrumbs |
| Property calendar connections | Same property, Bookings & calendars | Bookings card and calendar preview; mutation handlers remain dedicated |
| Basic information, address, private notes, assigned entity | Same property, Settings → Property information | Property details card, setup links |
| Guest-link configuration | Same property, Settings → Guest experience → Guest links | Guest links card, stays, Search; legacy `/guest-links` redirect |
| Property lock assignment/window | Same property, Settings → Guest experience → Digital door lock | Door-lock card |
| Reporting credentials and reporting address details | Same property, Settings → Reporting & fees → Police reporting | Police reporting card and missing-configuration links |
| Fee rate, cadence and council/payment configuration | Same property, Settings → Reporting & fees → Stay fee | Fee card, fee report setup/fix links; compatibility setup route |
| Reporting timing/default purpose | Same property, Settings → Automation | Relevant configuration links; legacy `/automation` redirect |
| Business identity/contact and invoice defaults | One shared entity editor based on `/entities?edit={id}`, with Business details and Invoice details | Property business card, Properties, invoice settings link, Account settings |
| Shared TTLock account | Existing `/smart-locks` | Properties and property lock section; remains distinct from property assignment |
| Stay facts and expected guests | Existing `/reservations/{id}` and its authorized actions | Stays, Dashboard, report links |
| Saved guest data | Existing authorized host guest editor | Inline stay facts, register, report correction links |
| Issued invoice | Existing invoice detail | Invoice list PDF/detail and stay's eligible invoice action |
| Fee-period report and guest fee decisions | Existing `/stay-fees/{id}?month=…` | Fee list; configuration links return to the same report period |
| Account/workspace/security/data preferences | Existing `/settings` and specialized actions | Account menu; no duplicated property or business editor |

The shared business card opens the currently assigned entity. Changing which entity a property uses remains a property operation. A business change may affect several properties, but issued invoice snapshots remain unchanged. Host invoice payment and fee sent/paid markers retain their current manual-recording semantics; do not imply bank reconciliation or automatic municipal submission.

Approved cross-property guest-link/automation summaries live as a small disclosure on Properties. They are read-only status/link rows using existing authorized data; they do not become new settings pages. Legacy redirects retain the one-property/multi-property behavior from task 0066. For multiple properties, land on Properties rather than choosing an arbitrary record.

## 5. Page specifications

### 5.1 Properties and property overview

- Properties: name, location, truthful setup state and calendar count; clear Open action; Add property; existing filtering/archive controls; links to shared business and lock accounts.
- Overview: seven familiar shortcut cards, consistent summaries, small setup indicator/checklist when needed, optional read-only calendar preview. No editable copy of Settings or always-open connection form.
- Setup stays optional where the existing contract says so. No fee or lock onboarding nag. Do not infer reporting readiness merely from non-empty credentials or a connected calendar.
- A card links to the exact tab/section; keyboard and normal-link behavior remain usable. Business details may legitimately navigate to the shared entity editor.

### 5.2 Property settings

Four local groups: **Property information · Guest experience · Reporting & fees · Automation**. Familiar feature headings remain visible within their group; e.g. Guest links and Digital door lock should not disappear behind unexplained names.

Desktop: slim local section navigation beside one focused editor. Mobile: labelled section selector or accessible wrapping navigation above a single-column form. Full real address, credential, fee, guest-link and lock fields remain available, even when the review image shows only a subset.

Initial implementation: extract existing fields into shared Jinja partials, render each once and retain the existing full-property save. Section changes within Settings preserve the form draft. All relevant successful controls remain in the form payload even when their section is visually inactive; do not disable unrelated controls merely to hide them. Reveal and focus a section containing an invalid field before asking the browser to show its error. Do not introduce section-specific POSTs as an incidental UI refactor.

Save/Discard feedback is at the form end in normal flow, aligned with the form, visible when there are changes. Saving covers the entire settings draft, including changes made in earlier sections. Changing sections must not silently discard that draft. Discard restores persisted values and clears the draft. Navigating to Overview, Calendars, a shared editor or another page with dirty settings presents **Save / Discard / Stay here**; Save navigates only after successful persistence. Cancel/failed validation keeps the draft. Passwords and secrets are never copied to local storage.

If safe full-form preservation cannot be achieved, stop and write a separate scoped-save brief with field allowlists, omitted-versus-cleared semantics, merged validation, authorization and unchanged-field regression tests. Do not attach the existing broad saver to a subset of fields.

### 5.3 Calendars

Show connection name/platform, actual sync result, last check and contextual actions. Put full iCal URL and removal inside details/More. Removal retains the existing confirmation, stay lifecycle and archive behavior. Connect calendar opens one form, with advanced options collapsed and the existing Add and sync operation. The form belongs outside the property-settings form.

Keep the existing sync action scope. A per-calendar Sync now button appears only if a supported handler is found; do not fake one by labelling a global sync as local. Failures remain visible with a concrete recovery path; partial sync success is not reported as universal success.

### 5.4 Business and invoice configuration

One shared entity editor with Business details and Invoice details. Reuse shared field partials for any field legitimately shown in both contexts; give each editable field one authoritative definition and shared validation path. Keep create/edit differences explicit rather than constructing an unrestricted generic form builder.

Preserve ARES click-to-fetch and its existing limits, VAT modes, bank/IBAN/BIC behavior, registered address, contact, signatures and invoice defaults. Entity list retains visible Edit, Invoice settings and More. Invoice settings links select the proper entity and return safely to the originating invoice/stay/property context. Legacy GET/POST routes may remain adapters to the same implementation while clients/bookmarks migrate; authenticated POSTs are not naively redirected to a different handler.

### 5.5 Dashboard and Stays

Dashboard retains Quiet overview: four white state cards, at most five unique stay rows, 30-day routine window using Prague today, overdue/failed work first, counts before truncation, Open and adjacent More. No new photo cards, revenue dashboard or feed of routine achievements.

Stays retains **Stays · Police reports · Guest register** navigation, All dates default, collapsed **All properties · Active** filter summary, existing optional views/filters/list-timeline/saved behavior and Add stay. Lists prioritize property, dates, guest progress, meaningful state and aligned actions. Narrow layouts turn rows into labelled cards.

Stay detail: property/dates, a real next action, then saved guest facts inline. Keep document type/number, DOB, nationality, residence, purpose, dates and existing verification/signature state visible to authorized hosts. Preserve Edit count, Add guest, invitation/copy actions, safe removal of an extra empty slot, existing corrections and report downloads. Do not hide all guests behind another tab or add a stay-fee panel.

The redesign does not invent check-in/out tracking, loosen report restrictions or enable expired/missing registration links. Retain the wording **Copy guest form link** and truthful clipboard outcomes.

### 5.6 Invoices and fees

Invoices: searchable/filterable list, existing period control, Generate invoice, one Invoice settings entry, direct PDF. Creation chooses an eligible stay or starts from its existing stay action, retains the correct seller, current prefill, item grid, Preview and Issue. Keep issued-detail downloads/send/manual markers/cancellation rules and immutable snapshots. Do not replace the existing invoice item layout with another visual design.

Stay fees: period-first per-property rows, truthful setup/blocking states, totals and Open report. Report detail owns calculations, finalized snapshots, protected guest decisions, statutory data and supported downloads. Configuration fixes open the canonical property fee section and return to the same report and period. Keep legitimate manually recorded filing/payment facts distinctly labelled. Rate 0 remains optional/off. No change to municipal rules, night/day arithmetic, tax, payment integration or PDF formats.

### 5.7 Account and advanced settings

Account menu → Settings groups **Account · Security · Data & archive · Privacy · Technical · Help**. Keep email change/confirmation and language as their existing actions; they are not one generic broad save. Retain role-aware links to Team/Incidents, archive/restore, privacy requests, retention, backups/export and legal/support information. Shared business links navigate to the same entity editor. Technical/dangerous actions retain their consequences and confirmations.

## 6. Code structure and maintenance contract

- Extend the existing `base.html`, `_components.html`, `_host_navigation.html`, filter/date/account/fee partials, CSS tokens and host feedback. No second host shell or parallel token palette.
- Prefer a small shared local-nav macro, section navigation, summary-card markup and existing action groups. Domain forms stay domain-specific; do not combine business, guest, fee and security validation into a universal form engine.
- Property field partials have one render site per active property document. Overview reads values/status only. Render IDs/names once; avoid hidden cloned forms for desktop/mobile.
- Canonical GET destinations have normal links and server-readable view/section parameters. JavaScript enhances section switching, draft preservation and legacy hash activation; it does not become the only route to a feature.
- Keep `#basics`, `#address`, `#ubyport`, `#automation`, `#communication`, `#stay-fee-settings`, `#door-code`, `#calendars`, and relevant report anchors working. Legacy hashes must reveal the correct target. Provide a usable non-JavaScript fallback without separately maintained editor markup.
- All return destinations use existing safe-local-path guards. Preserve owner access, CSRF, archive state, unavailable-feature explanations and data scope. Shared rendering never implies shared authorization.
- Shared copy lives in one i18n key for a meaning, in both EN/CS. Different field contexts may need different hints; reuse the field without erasing domain-specific explanations.
- Do not blanket-replace CSS or every page. Migrate a page family at a time; keep changes to shared primitives backward compatible until their consumers move.

**Maintenance acceptance:** changing a shared field's label/layout/validation requires one authoritative change, reflected through all supported entry points. Changing business identity does not require editing a property template and an invoice template independently. Overview summaries are read-only projections, not editors.

## 7. Compatibility and migration rules

1. Inventory routes, forms, overlapping fields, return parameters, saved views, anchors and mutations first. Classify shared record scope separately from duplicate implementations.
2. Refactor field markup without changing payloads or behavior, then add the navigation. Do not combine a backend rewrite with the first property UI change.
3. Preserve legacy entry URLs. GET adapters may redirect to the canonical view; POST compatibility must invoke the same scoped logic and preserve inputs/CSRF/error behavior. Do not use a 303 redirect to pretend a submitted form was saved.
4. Fee setup and invoice-settings adapters retire only after equivalence tests and function inventory. Never delete a unique control just because the overview screenshot omitted it.
5. During transition, two visible entry routes may exist if they share one editor implementation. Two independent field definitions/save rules are a failure.
6. No mass migration, data rewrite or new flag/dependency is needed. Rollback is the normal owner-reviewed revert of the presentation/refactor commit; preserve stored data and issued/finalized snapshots.

## 8. Ordered delivery phases

Each row has a numbered contract in docs/tasks. 0071 is runnable; 0072 includes the exact extraction command and awaits reviewed readiness. Later implementation contracts stay blocked until the orchestrator releases exact code/diffs against their reviewed integration predecessor. This follows the repo anchor rule instead of asking Cursor to guess patches against future files. File allowlists are explicit and no unnamed change is authorized.

| Phase | Deliverable and likely files | Dependency and acceptance |
|---|---|---|
| 0 | Task **0071**: documentation-only ownership inventory and fresh verification report; no application edits | Designs approved; actual route/form table, duplicate-field list and test baseline; unresolved failures named |
| 1a | Shared property section partials extracted from `apartment_form.html`; relevant property regression tests | 0; rendered names/IDs/payloads equivalent, no removed capability |
| 1b | Property tabs, grouped editor, legacy anchors, dirty-form handling; `apartment_form.html`, shared nav/components, `host.css`, `app.js`, EN/CS copy, scoped tests | 1a; one editor, cards land correctly, hidden-section validation/dirty navigation safe |
| 1c | Calendar tab/connection form/details; property calendar partials and existing feed routes only if justified | 1b; add/remove/errors use existing operations, URLs discreet, drafts protected |
| 2a | Shared business fields/validation mapped and extracted; `entities.html`, `invoice_settings.html`, shared partials and their handlers/tests | 0/1b; overlapping identity/VAT/account fields have one owner; create/edit and ARES unchanged |
| 2b | Shared entity navigation and invoice-settings compatibility/returns | 2a; one business editor, correct entity, no issued-invoice mutation |
| 3 | Fee setup canonical links/adapters/shared normalization; `_stay_fee_fields.html`, fee setup/property templates, fee/admin routes and focused tests | 1b/2b; no fee arithmetic/period changes, existing setup inputs preserved, period return retained |
| 4a | Properties list and optional read-only cross-property summaries; `apartments.html`, existing authorized context, Search links | 1b/2b; zero duplicate editors, one/many/no-property paths usable |
| 4b | Dashboard/Stays list geometry and shared actions; `dashboard.html`, `reservations.html`, shared primitives and browser tests | 0/4a; current Quiet overview/filter semantics retained, table/cards fit |
| 4c | Stay-detail grouping/navigation; `reservation_detail.html`, relevant shared primitives and tests | 4b; saved guest facts visible, only supported actions, report guards unchanged |
| 5a | Invoice list/detail/navigation into existing stay-linked builder; invoice templates/routes only as needed | 2b/4c; stay eligibility, preview/422 values, VAT, numbering/snapshots unchanged |
| 5b | Fee list/detail visual integration; fee templates and existing view context | 3/5a; finalized data/download protections and manual marker semantics unchanged |
| 6 | Account settings organization and Help/Search/role-aware link review; `settings.html`, host nav, `api.py`, scoped tests | 2b/5b; specialized actions remain distinct, ordinary user never sees admin controls |
| 7 | Whole-navigation acceptance report and owner staging review | All prior phases; route/locale/width matrix green, review screenshots, no unresolved release regressions |

Do not let two open implementation briefs independently own the same template/copy. Create sequential dependency chains and rebase anchors after each completed phase. Numbered briefs 0071–0086 are now written. Tasks 0067–0070 on current main belong to unrelated TTLock work and must not be overwritten. All task PRs target task/host-navigation-integration; main is held until staging acceptance and promotion approval.

## 9. Verification and release evidence

Executor/CI, not the orchestrator, runs the application tests. From `App/`: `.venv/bin/python -m pytest tests -q`. From repository root: `python3 scripts/context_lint.py`. Provision the repository's supported browser prerequisites before required browser checks; relevant browser/geometry acceptance must have **0 skipped**. A missing browser is not a passing check.

Every phase records its actual command results; the historical 0066 numbers are not a current baseline. If a baseline fails, classify it and issue a separate correction brief before the affected phase's acceptance. Do not change assertions merely to bless clipped actions.

Required widths: **360, 390, 760, 1024, 1280, 1440, 1680, 1920, 2048 CSS px**, EN and CS; expanded/collapsed sidebar, long names/labels and actual component container widths. Screenshots at least 360/390/1280 for each changed page, with measured wide-lane evidence through 2048. Use only demo records, masked secrets and non-real documents.

Check existing suites including property hub/form save/form nav/readiness/copy settings; host property controls, wide geometry, controls, feedback, filters, quiet dashboard and stay actions; invoice stay rules/pages/browser/settings/entity/immutability/VAT/numbering; fee property setup/report guards; privacy/access/CSRF and auth without JavaScript. The implementation brief selects exact relevant tests and still meets required full checks.

Behavior matrix:

- One/many/no properties; incomplete/complete setup; active/archived records; ordinary/admin account; feature available/unavailable.
- Every overview card and old anchor lands in the correct editor; old GET redirects, POST adapters and Search return safely.
- Editing each property section preserves all untouched settings, including unchecked booleans, fee/payment data, entity/controller links, timing, guest PIN and lock assignment. Copy-from-property and address onboarding remain scoped.
- Dirty navigation Save/Discard/Stay; cross-section drafts; failed browser/server validation; safe return; double submit; clipboard unavailable; real success/error feedback once.
- Credentials test/code-list refresh and PIN/link regeneration retain current effects and warnings; no live filings, real emails or lock operations during visual review.
- Shared business edit is reflected in linked properties/future invoices and never rewrites issued snapshots. Invoice settings uses the proper entity and next destination.
- Fee account empty versus omitted versus IBAN-only, optional rate 0, invalid account, copy-from-property, custom period, finalized report and protected guest decisions remain correct.
- Inline guest facts, valid/expired/missing invitation links, expected-slot versus real-guest removal, submitted record restrictions, receipts/errors and report/register access remain intact.
- Focus/keyboard/labels/errors are usable; no floating action bar covers an input; mobile rows are labelled cards; primary/secondary actions keep shared heights and action slots.

## 10. Approved execution and staging-first rollout

1. All five design boards were approved in chat on 2026-10-12; do not request the same approval again.
2. Review the planning PR without merging it to main. Current main CI can automatically deploy production. Initialize/fetch task/host-navigation-integration from the planning branch, then start 0071 with the master Cursor prompt.
3. Execute/review one released brief at a time. Each task PR targets integration; source patches for later blocked contracts are released by the orchestrator against the reviewed predecessor, not improvised by Cursor.
4. Review exact files/CI/reports/screenshots before owner guarded integration merge. No main merge or production workflow action during implementation or preview.
5. 0084 establishes the complete green integration candidate C. 0085 deploys C to Render ubyhost-staging with mock data/configuration and records actual SHA/health/walkthrough evidence. Fix/new candidate requires renewed checks/staging acceptance.
6. Owner explicitly approves the implemented C for production, with the staging acceptance record. Only then release 0086 and perform final reviewed main promotion; current green main CI may deploy production automatically. Verify actual source revision and read-only smoke; owner rollback uses known-good code without replacing data.

Full branch, approval, test, evidence and release rules live in the execution protocol. Design approval does not substitute for staging acceptance or production-candidate approval.

## 11. Ordered brief list

| Brief | Deliverable | Initial state |
|---|---|---|
| [0071](../tasks/0071-host-navigation-readiness.md) | Source/editor inventory and real baseline | replaced by 0091/0094 |
| [0072](../tasks/0072-property-editor-extraction.md) | Exact canonical property/form extraction | replaced by 0094 |
| [0073](../tasks/0073-property-navigation.md) | Property tabs, grouped editor, drafts and validation | replaced by 0094 |
| [0074](../tasks/0074-property-calendars.md) | Calendar tab, connection form and details | replaced by 0094 |
| [0075](../tasks/0075-shared-entity-fields.md) | Shared business/invoice field ownership | blocked |
| [0076](../tasks/0076-canonical-entity-navigation.md) | Canonical entity editor and legacy adapters | blocked |
| [0077](../tasks/0077-canonical-fee-setup.md) | Canonical fee setup and scoped compatibility | blocked |
| [0078](../tasks/0078-properties-overview.md) | Properties list and read-only summaries | blocked |
| [0079](../tasks/0079-daily-work-lists.md) | Quiet dashboard and Stays list | blocked |
| [0080](../tasks/0080-stay-detail-organization.md) | Inline guest facts and stay actions | blocked |
| [0081](../tasks/0081-invoice-navigation.md) | Stay-linked invoice flow and canonical settings | blocked |
| [0082](../tasks/0082-fee-report-navigation.md) | Period/fee report navigation | blocked |
| [0083](../tasks/0083-account-settings-navigation.md) | Account/advanced navigation | blocked |
| [0084](../tasks/0084-host-navigation-integration-acceptance.md) | Full integrated acceptance/CI | blocked until all implementation reviewed |
| [0085](../tasks/0085-host-navigation-staging-review.md) | Actual Render staging deployment/walkthrough | blocked until 0084; owner deployment |
| [0086](../tasks/0086-host-navigation-production-promotion.md) | Exact production approval/promotion/smoke | blocked until staging pass and explicit owner approval |

Use [the Cursor master prompt](host-navigation-cursor-prompt.md), [execution protocol](host-navigation-execution-protocol.md) and [approval record](host-navigation-design-approval.md). Each brief follows the repo template with scope, sources, ordered requirements, checks, stop/report rules and owner steps. A blocked contract without a released patch is never executable.
