# Host app and admin: the smoothness plan (Wolt-merchant-portal benchmark)

Status: plan for the owner, accepted 2026-10-30; revised same day after review to remove unverified claims (see Revision). Written after comparing the app against the Wolt merchant portal (owner screenshots, 2026-10-30) and a code audit of `base.html`, `_shell_sidebar.html`, `_shell_topbar.html`, `dashboard.html`, `admin_home.html` and the ten host stylesheets. The binding rules from this plan are in `docs/context/rules.md` (section "UX and interaction"); this file is the rationale and the work plan.

## Revision (2026-10-30, post-review correction)

This revision removes claims the code cannot support and reframes delivery:

- No "95% of Wolt" claim, no 5x/10x cost multipliers, no one-week delivery promise, no guaranteed sub-200 ms navigation, no zero-risk claim. Each performance layer is a separately measured pilot; 200 ms is an aspirational warm-navigation target (see §1.1, §5).
- The delivery order changes: the plan starts with one demonstrated dashboard or desktop admin-navigation improvement, then page-specific work (density, filters, empty states, admin), then style consolidation alongside affected components, then prefetch / transition / partial-action pilots - each with verified source anchors, a small file allowlist, exact changes and concrete acceptance checks. A full stylesheet consolidation, a database migration and the unrelated backlog are NOT prerequisites for useful UX work.
- The earlier idea of aggregating every attention line's severity in the dashboard template is discarded: `needs_you.py` already sorts lines by tone rank (verified `App/app/needs_you.py:177` and the browser fixture assertions in `App/tests/test_host_quiet_dashboard_browser.py`), so the first-item summary is consistent with the producer contract. No template aggregation and no duplicate regression test.

## Owner decisions (2026-10-30)

- **D1: No dark mode.** Light mode only, no theme toggle, no `prefers-color-scheme` switching. Non-negotiable.
- **D2: Progressive enhancement on the existing FastAPI + Jinja app ("turbo-MPA"). No SPA rewrite.** The owner asked for the most long-term-maintainable route to the Wolt feel; this is it (rationale in §1).
- **D3: Scope is the host app and the admin area.** Guest pages, marketing, auth and legal pages are out of scope except whatever the shared token system fixes for free.
- **D4: The assets UbyHost already does better than Wolt are frozen and must not regress:** the Ctrl+K command palette, keyboard navigation (`g d`, `j/k`), undo toasts, skeleton screens, the offline page, PWA install, screen-reader live regions, and the three UI languages.

## 0. The diagnosis: what "clunky" is, in code terms

| # | Cause | Evidence in the repo | Fixed by |
|---|---|---|---|
| 1 | **Every click is a full page load.** Wolt swaps content in place; UbyHost re-renders the page from the server on every action. | `base.html` is a classic MPA shell; skeletons soften but do not remove the round trip. | W3 |
| 2 | **Attention stacking.** The dashboard can show, stacked: env banner, workspace-deletion banner, billing banner, alert stack, welcome-back banner, onboarding banner, then the "What needs you" card. | `dashboard.html`, `_env_banner.html`, `_billing_banner.html`, `_host_alerts.html` | W2 |
| 3 | **Design-system accretion.** Ten stylesheets across four design generations render the same page: `tokens.css`, `app.css`, `components.css`, `host.css`, `host-controls.css`, `host-design0123.css`, `host2.css`, `workflow.css`, `wizard.css`, `cleaning.css`. Pages built in different eras subtly disagree on spacing, radius and button weight; the eye reads this as "clunky". | `base.html` stylesheet list | W1 |
| 4 | **Admin is hidden.** `/admin/*` links live inside the account `details` menu at the bottom of the sidebar; Wolt puts Faktury and Uživatelé directly in the sidebar. | `_shell_sidebar.html` | W4 |

What is *not* wrong: the shell bones are better than Wolt's (see D4), and `admin_home.html` already implements the Wolt home pattern (stat tiles + queue tables). The gap is discipline and motion, not capability.

## 1. Why not a SPA (D2, for whoever asks later)

| | Full SPA rewrite (React/Vite) | Turbo-MPA (this plan) |
|---|---|---|
| Feel achievable | Wolt-level | Most of the Wolt feel; the ceiling is named in §1.1 and each layer is measured, not promised |
| Lines of throwaway work | All 49 templates + routes become JSON APIs | None; each phase ships on top of current pages |
| Toolchains to maintain | Two (Python API + Node build, state mgmt, tokens/auth) | One (Python + a few small vanilla JS files, no build step) |
| Risk to the filing path | High (every route rewritten) | Zero (no `ubyport/`, `reporting.py` or deadline code touched) |
| Solo-operator maintainability | Worse: double review surface, double dependency churn | Same as today |
| Escape hatch if a SPA is ever truly needed | - | W1's token system + W3's partial endpoints are the migration path |

**The feel budget (aspirational targets; each layer is measured per §5, never promised):**

- Warm-navigation perceived click-to-content trending toward ~200 ms on the production host; cold, warm and back/forward navigation are measured and reported separately. Cold navigation is not expected to hit this target.
- Zero white flash on navigation.
- Zero cumulative layout shift on page swap.
- Style consolidation progresses alongside the components each task touches; legacy and justified page-owned styles may coexist during migration. Files are not deleted merely to reach a three-stylesheet target.

### 1.1 What "smooth" decomposes into (the honest ceiling)

The Wolt feel is not one thing. Whoever executes this plan must know which parts of the feel each layer buys, and where the honest ceiling is. Checked against browser support as of 2026-10-30:

| Feel component | Delivered by | Wolt-level? |
|---|---|---|
| 1. Pages appear faster | W3-L1 prefetch on pointerover/focus | Expected to be the biggest contributor to the feel; browser-level, not architecture. Verified by a measured pilot with an explicit side-effect-free GET allowlist before wider rollout |
| 2. No white flash; content morphs | W3-L2 view transitions | Enhancement only. Same-document transitions are Baseline (Chrome 111+, Safari 18+, Firefox 144+). Cross-document morphs ship in Chrome/Edge 126+ and Safari 18.2+ (desktop and iOS); Firefox does not ship cross-document transitions in a stable release and falls back to a fast, prefetched, non-animated navigation. Cross-document transitions require same-origin CSS opt-in on both documents; `document.startViewTransition()` is for a DOM update within the current document. Reduced-motion and unsupported-browser fallbacks are preserved |
| 3. Some actions avoid a full reload | W3-L3 partial swaps + undo toasts | Only for covered low-impact flows whose server-supported reversal is verified; the ordinary no-JS form stays. Financial actions keep separate durable-result, audit and compensating-action contracts - a toast does not reverse an issued invoice or an external payment |
| 4. Consistent visuals, lower density | W1 + W2 | Independent of architecture |
| 5. Client-side state lives in memory | URL state, sessionStorage, fragments | **~70-80%.** The one genuine residual gap; see §1.2 |

### 1.2 The residual gap, named precisely

The only thing an MPA cannot fully replicate is client-side state living in memory: a filter kept perfectly across pages, a half-scrolled modal, wizard state, optimistic UI on every interaction. Mitigations that close most of it: URL state (`_list_filter.html` already does this), sessionStorage for drafts, fragment swaps for actions. The gap only matters on interaction-dense surfaces - drag-and-drop planning, real-time collaboration, offline-first editing - none of which exist in UbyHost today. The dominant interaction pattern (navigate, look, act, confirm) is fully covered by the plan.

### 1.3 The price math

A full SPA rewrite brings two toolchains, npm dependency churn, state management, API contract drift between FastAPI and frontend types, and keyboard and screen-reader support re-implemented from scratch - plus rewrite risk over the filing path, which rule 1 forbids taking lightly. Turbo-MPA adds small vanilla ES modules with no build step and keeps one toolchain with one operator; each layer is a separately reviewable task whose effect is measured. No fixed multiplier or delivery date is claimed; cost is stated per task in executor sessions when briefed.

### 1.4 When this decision flips (the reversal triggers)

D2 is a decision with named exit conditions, not a dogma. Revisit it only if one of these happens, and record the trigger in the decision line:

- A drag-and-drop or real-time collaborative surface becomes a real planned feature (live calendar planning, co-editing).
- Offline-first field use becomes a requirement (hosts using the app without connectivity).
- A dedicated frontend engineer joins the project.
- After W1-W3 ship, the owner can **name specific daily interactions that still feel wrong** (for example "the filter resets when I go back"). Evidence beats prediction: use the app for two weeks post-ship and decide from named pain, not from a guess made before shipping.

If reversed: do not start from zero. W1's token system is the design system a SPA needs; W3's `?fragment=` endpoints are proto-API endpoints; the SPA consumes both. The reversal is a continuation, not a rewrite.

### 1.5 The insurance policy

The plan is deliberately the migration path to a SPA. Tokens (W1) and fragment endpoints (W3-L3) keep the option open at zero carrying cost. The owner pays for the SPA option only if a §1.4 trigger fires. Any executor proposing a SPA rewrite before a trigger fires should be pointed at this section.

## 2. Workstreams

Each workstream is independently shippable as small, separately reviewable tasks. The first task ships one demonstrated dashboard or desktop admin-navigation improvement (complete brief, screenshots, checks); later tasks add page-specific density, filters, empty states and admin improvements, fold style consolidation into the components they touch, and run the prefetch / transition / partial-action pilots separately. Suggested order: first-demonstrated-improvement → W2/W4 page work → W1 incremental → W3 → W5.

### W1: One design system — Effort M · Risk MEDIUM (visual regressions)

Goal: host+admin styling converges on `tokens.css` (colors, spacing, radii, shadows, type scale), `components.css` (every `ui_*` macro's styles) and `host.css` (app-surface layout). Guest and marketing stylesheets are untouched (D3). Consolidation is incremental: map callers and cascade behavior before removing styles, do it alongside the components a task already touches, and never delete a file merely to reach a three-stylesheet target - legacy and justified page-owned styles may coexist while the migration is in progress.

Tasks:

1. Inventory every class used by the host/admin templates; map legacy classes (host-design0123, host2, host-controls) to `ui_*` equivalents. Output: a mapping table in the workstream's task file.
2. Fold `host-controls.css`, `host-design0123.css`, `host2.css` into `components.css`/`host.css` where a task already touches those components; feature styles (`workflow.css`, `wizard.css`, `cleaning.css`) are folded or kept if a page genuinely owns them. Nothing is deleted without a verified caller map and cascade check.
3. Re-point `base.html` to the consolidated set; bump every `?v=` cache key.
4. Freeze the component inventory on `dev_ui.html`: every `ui_*` component in every state (default, hover, focus, disabled, empty, error) lives on that page. A component not on `dev_ui.html` does not exist.

Acceptance:

- Where files were folded away, no template or stylesheet references them (`grep -r` clean). Coexisting legacy layers are listed in the task report with their justification.
- `App/tests/test_host_geometry.py` passes; before/after 390 px screenshots of the 12 key pages (dashboard, stays, stay detail, reservations, cleaning, housebook, settings, predplatne, admin home, fakturace, customers, customer detail) reviewed by the owner.
- No visual change is *intended* in W1 — this is consolidation, not redesign. Where legacy layers disagreed, `components.css` wins.

### W2: Density discipline — Effort S · Risk LOW

Goal: one attention surface per page. The dashboard's "What needs you" card (comment 0241) becomes the app-wide pattern: the card is *the* place where attention demands live. Folding a banner never removes its warning severity, action, dismissal or visibility: a badge may draw attention to a warning but cannot hide a blocking one, and the producer's tone ordering (`needs_you.py` sorts by tone rank) stays the contract the template renders.

Tasks:

1. Banner inventory: list every `ui_banner` / stack currently reachable on each host page.
2. Env banner (`_env_banner.html`) becomes a topbar badge, not a page banner.
3. Billing banner (`_billing_banner.html`) and host alert stack (`_host_alerts.html`) fold into the page's needs-you card (or a topbar badge where no card exists).
4. Onboarding and welcome-back banners appear only in true empty states (no apartments / first visit), never on a working dashboard.
5. `ui_stats` is capped at 4 tiles per page; more than that becomes a second `ui_section` table.

Acceptance: no host or admin page shows more than one banner above its first content section; the dashboard with data shows exactly one attention surface (the needs-you card).

### W3: Instant feel (the motion layer) — Effort M · Risk MEDIUM

Goal: Wolt's click feel without a rewrite. Three layers, each a separate task/PR, in this order. All JS is vanilla ES modules served from `App/app/static/`, no framework, no build step. Every layer is progressive enhancement: with JS off, the app behaves exactly as today.

**L1 — Prefetch (Effort S, measured pilot first).** On `pointerover`/`focusin` of a same-origin link, inject `<link rel="prefetch">`. After `requestIdleCallback`, prefetch sidebar destinations from an explicit allowlist of verified side-effect-free GETs. Never prefetch sign-out, exports/downloads, token creation, action links, or payment/authentication destinations. Bound and deduplicate in-flight requests, respect cache policy and `Save-Data`, and verify logout, account switching and fresh-data visibility still behave correctly. Never weaken a security policy (e.g. Cache-Control) to make caching work. Measured as a pilot on a few verified routes before wider rollout.

**L2 — View transitions (Effort S).** Same-document updates use `document.startViewTransition()` (a DOM update within the current document). Cross-document transitions use `@view-transition` only with the same-origin CSS opt-in present on both documents. Reduced-motion and unsupported-browser fallbacks are preserved. Shared-element classes on the shell (sidebar, topbar, page title, primary card) so the content area morphs instead of flashing. Honor `prefers-reduced-motion` (fall back to plain navigation). Fallback where unsupported: today's behavior - and remember the browser matrix in §1.1: Firefox users get the L1-fast navigation without the morph, which is acceptable.

**L3 — Partial swaps (Effort M, one low-impact action first).** Extend the existing `data-toggle-panel` / `data-dashboard-refresh` patterns into one tiny helper (`App/app/static/app.js`, target ~150 lines): a `data-swap` action fetches the re-rendered fragment and swaps it in place, then posts the existing undo toast. Start with ONE low-impact action whose server-supported reversal is verified, and specify for it: CSRF and role checks, duplicate-submission handling, uncertain mutation results, error and expired-session paths, focus and screen-reader announcements. Preserve the ordinary no-JS form. Never blindly retry an uncertain mutation. Financial actions (mark-paid, storno, invoice issue) are out of scope until each has separate durable-result, audit and compensating-action contracts - a toast does not reverse an issued invoice or an external payment. Server side: the route already re-renders the page; add a `?fragment=…` mode returning the relevant include. Skeleton screens (already built) cover the fetch. These `?fragment=` endpoints are also the proto-API of the §1.5 insurance policy - design their payloads so a future SPA could consume them.

Acceptance (all of W3):

- Playwright tests for the 5 flows assert the swap and the undo path.
- A no-JS walkthrough of the same flows completes them identically.
- Keyboard navigation and screen-reader live regions behave exactly as today through every swap (announce the swap region).
- Performance measured, not promised: record route, browser/device, viewport, network, cache state and sample count; report cold, warm and back/forward navigation separately. 200 ms warm is an aspirational target, not an acceptance gate. Zero layout shift on L2 morphs.

### W4: Admin surface, Wolt patterns — Effort M · Risk LOW

Goal: the admin area becomes the Wolt portal the owner fell in love with. Content comes from the revenue cockpit plan (`docs/plans/billing-admin-revenue-cockpit-20261028.md`); this workstream supplies the *surface patterns*.

Tasks:

1. `_shell_sidebar.html`: an "Administrace" nav group, visible only to admin accounts: Fakturace, Customers, Funnel, Operations, Users. Remove the admin links from the account `details` menu. Nothing admin is more than one click from the shell.
2. Read-only card + "Upravit" pattern: every settings block and the admin customer money page render as summary cards with an edit affordance; editing opens a preview-then-confirm form (reuses the existing preview components). The principle already in the cockpit doc (§2.4) becomes the standard for all admin forms.
3. Per-row action menus (`row_menu` macro) on every admin table; status badges reuse the existing `ui_badge` tones.
4. Every admin list gets: the shared search/filter bar, a month/year selector where applicable (`_date_range.html` / the Wolt year dropdown pattern), a download menu (PDF/CSV/XLSX via existing exports), and a proper `ui_empty` state with icon and one-line guidance.
5. Motion: admin flows join L3 in the same order of priority (mark-paid and storno are in the first five).

Acceptance: every admin page passes the same checklist as host pages (screenshots, geometry, no-JS); the owner can reach any admin function in one click from the sidebar; every admin list has an empty state.

### W5: The standard, enforced — Effort S · Risk LOW

1. The binding rules are already added to `docs/context/rules.md` (section "UX and interaction", same commit as this plan). That section is the single source of truth; this plan is the rationale.
2. Fold the overlapping design notes in `docs/DESIGN.md` to point at the rules section (one editing task, no rule changes beyond the pointer).
3. Add to `.github/PULL_REQUEST_TEMPLATE.md`: "UX and interaction rules checked (rules.md §UX): tokens-only styling, one banner, ui_* component, dev_ui.html updated if a component changed."
4. `dev_ui.html` is the acceptance surface for all component work; a PR that changes a component's look updates it in the same PR, including the component catalog entry in `docs/design/`.

## 3. Sequencing and effort

| Phase | Ships | Effort | Risk |
|---|---|---|---|
| First demonstrated improvement (dashboard or desktop admin navigation) | alone, first - a complete small task before anything else | S | LOW |
| W1 design system | alongside affected components, incrementally | M (several sessions) | MEDIUM (visual) |
| W2 density | page by page, alongside W1 where touched | S per page | LOW |
| W3 L1 + L2 | measured pilots, after their safety rules are briefed | S+S | MEDIUM (motion) |
| W3 L3 | one verified-reversible low-impact action first | M | MEDIUM |
| W4 admin surface | after the first demonstrated improvement | M | LOW |
| W5 standard | last | S | LOW |

Total effort is stated per task when briefed; the order above is the suggested sequence and any phase may pause between tasks. No schema changes, no new dependencies, no new outbound requests, no guest-page changes.

## 4. Non-goals

- No dark mode (D1).
- No SPA rewrite, no JS framework, no build step (D2). The reversal conditions for D2 are in §1.4; until one fires, an executor proposing a SPA rewrite is off-plan.
- No changes to guest pages, marketing, auth or legal surfaces (D3).
- No new third-party scripts, fonts or CDNs (privacy rules unchanged).
- No regression of the D4 assets, ever.
- The filing path (`ubyport/`, `reporting.py`, deadlines) is not touched by any task in this plan.

## 5. Verification (from the standing rules)

- `.venv/bin/python -m pytest tests -q`
- `.venv/bin/python -m pytest tests/test_host_geometry.py -q -rs` — 0 skipped for host template/CSS changes
- Playwright browser tests for W3 flows and W4 admin pages (pattern exists in `test_guest_browser_e2e.py`)
- Before/after 390 px screenshots per changed page, in the PR
- Merge only via `scripts/merge-pr-on-green.sh`; a merge never deploys
