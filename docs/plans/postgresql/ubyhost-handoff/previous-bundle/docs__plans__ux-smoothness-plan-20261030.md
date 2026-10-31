# Host and admin UX improvement plan

Status: owner-directed plan, 2026-10-30. This plan records product preferences and a staged way to improve host/admin workflows. It does not promise parity with another product, a delivery date, a particular navigation speed, or absence of production or filing risk. Guest, marketing, authentication and legal pages retain their own rules.

## Owner preferences and scope

- Keep FastAPI, Jinja, light mode and progressive enhancement. Do not plan a SPA rewrite.
- Preserve the command palette, keyboard navigation, server-supported undo, skeletons, offline page, PWA, screen-reader announcements, existing languages, core navigation, server authorization and phone navigation.
- Improve the host and admin experience through small, page-specific work that can be reviewed and measured.
- Do not make a complete stylesheet consolidation or unrelated backlog work a prerequisite for useful page improvements.

These are scope and product preferences. They do not establish that the current app is “95% of Wolt,” that a SPA has a particular cost multiplier, or that any change can ship in a week or without risk.

## Work sequence

### 1. Demonstrate one useful improvement

Choose one dashboard or desktop admin-navigation improvement after reviewing the named template, page add-on, component guidance and relevant browser fixtures. Describe the observed problem and its source anchor. Keep the implementation limited to the smallest set of templates, styles, scripts and tests needed for that improvement. Keep existing phone navigation and admin authorization intact.

Do not add dashboard severity aggregation to the template by default. Before selecting that work, verify the current producer and browser fixture. If the producer already sorts attention lines and the fixture covers that contract, choose another demonstrated improvement unless a current defect is shown.

### 2. Continue with page-specific improvements

Address attention, information density, filters, empty states and admin navigation in separate, reviewable tasks. Each task must name verified source anchors, a small file allowlist, exact changes, preservation rules and concrete acceptance checks. Do not require unrelated routes or backlog items to be completed first.

Prefer one coherent attention area and no more than four summary tiles where that fits the page. Allow a documented page-specific exception when it improves the task. Preserve warning severity, action, dismissal and visibility; moving a warning must not hide a blocking issue behind a badge or another interaction.

### 3. Consolidate styles alongside affected components

Reuse existing tokens and components. Before removing or moving styles, map the callers and inspect cascade behavior for the affected page. Legacy and justified page-owned styles may coexist while work proceeds. Consolidate styles when a component or page change makes that safe and reviewable. Do not delete files just to reach a three-stylesheet target, and do not make a global CSS consolidation a gate for UX work.

Follow the applicable component guidance and page add-on. Update the component catalog when a component changes. Preserve guest, marketing, authentication and legal page-specific styling rules.

### 4. Treat interaction pilots as separate work

Prefetch, view transitions and partial actions need their own source review, allowlist, implementation brief and measurements. They are optional pilots, not prerequisites for the dashboard or page-specific work.

For any performance comparison, record route, browser/device, viewport, network, cache state and sample count. Measure cold, warm and back/forward navigation separately. A 200 ms warm-navigation result is an aspirational measurement target, not a guarantee or acceptance promise. Record the observed results and regressions; do not weaken security policy to improve a result.

**Prefetch:** allow only verified, side-effect-free same-origin GET destinations. Exclude sign-out, exports/downloads, token creation, action links, and payment or authentication destinations. Bound and deduplicate requests, respect cache policy and data-saving preferences, and verify logout, account switching and fresh-data visibility.

**Transitions:** cross-document transitions require same-origin CSS opt-in on both documents. `document.startViewTransition()` applies to a DOM update in the current document. Preserve reduced-motion behavior and a plain-navigation fallback for unsupported browsers. Do not rely on an unverified browser-support matrix.

**Partial actions:** begin with one low-impact action whose server-supported reversal is verified. Specify CSRF and roles, duplicate submissions, uncertain mutation results, errors, expired sessions, focus and announcements. Keep the ordinary no-JS server form. Never blindly retry an uncertain mutation. Financial actions need separate durable-result, audit and compensating-action contracts; a toast does not reverse an issued invoice or external payment.

## Acceptance and verification

- Every task is based on current source inspection and has a bounded allowlist, exact patch intent, and checks for the changed page and preserved behavior.
- Host/admin template or CSS changes follow repository browser and geometry requirements, including the required viewport screenshots in the task report.
- Verify keyboard use, screen-reader announcements, authorization, core and phone navigation, warning behavior, and no-JS forms where the change can affect them.
- Run only the applicable test-map rows for the change. Do not run the full suite by default.
- Report measured performance and any unresolved risks; do not state guaranteed speed, zero risk or an unsupported percentage of another product.

## Non-goals

- Dark mode or a SPA rewrite.
- Mandatory global stylesheet consolidation.
- Changes to guest, marketing, authentication or legal pages without a separate scoped plan.
- Third-party scripts, fonts or CDNs unless separately reviewed under privacy rules.
- Changes to UbyPort filing behavior as part of a UX task.
