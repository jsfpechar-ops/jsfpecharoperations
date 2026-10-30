# Host app and admin: the Wolt-level smoothness plan

Status: plan for the owner, accepted 2026-10-30. Written after comparing the app against the Wolt merchant portal (owner screenshots, 2026-10-30) and a code audit of `base.html`, `_shell_sidebar.html`, `_shell_topbar.html`, `dashboard.html`, `admin_home.html` and the ten host stylesheets. The binding rules from this plan are in `docs/context/rules.md` (section "UX and interaction"); this file is the rationale and the work plan.

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
| Feel achievable | Wolt-level | Wolt-level (§1.1 says exactly how much) |
| Lines of throwaway work | All 49 templates + routes become JSON APIs | None; each phase ships on top of current pages |
| Toolchains to maintain | Two (Python API + Node build, state mgmt, tokens/auth) | One (Python + a few small vanilla JS files, no build step) |
| Risk to the filing path | High (every route rewritten) | Zero (no `ubyport/`, `reporting.py` or deadline code touched) |
| Solo-operator maintainability | Worse: double review surface, double dependency churn | Same as today |
| Escape hatch if a SPA is ever truly needed | - | W1's token system + W3's partial endpoints are the migration path |

**The feel budget (the definition of done for "smooth like Wolt"):**

- Perceived click-to-content under ~200 ms on the production Lightsail host.
- Zero white flash on navigation.
- Zero cumulative layout shift on page swap.
- One design system rendering every pixel of the host and admin surfaces.

### 1.1 What "smooth" decomposes into (the honest ceiling)

The Wolt feel is not one thing. Whoever executes this plan must know which parts of the feel each layer buys, and where the honest ceiling is. Checked against browser support as of 2026-10-30:

| Feel component | Delivered by | Wolt-level? |
|---|---|---|
| 1. Pages appear instantly (~100 ms) | W3-L1 prefetch on pointerover/focus | **100%.** The single biggest contributor to the feel; browser-level, not architecture |
| 2. No white flash; content morphs | W3-L2 view transitions | **~95%.** Same-document transitions are Baseline (Chrome 111+, Safari 18+, Firefox 144+). Cross-document morphs ship in Chrome/Edge 126+ and Safari 18.2+ (desktop and iOS); Firefox does not ship cross-document transitions in a stable release and falls back to a fast, prefetched, non-animated navigation. The morph is always enhancement, never requirement |
| 3. Actions never reload the page | W3-L3 partial swaps + undo toasts | **100%** for the covered flows (the top 5 by frequency) |
| 4. Consistent visuals, low density | W1 + W2 | **100%.** Not architecture-dependent at all |
| 5. Client-side state lives in memory | URL state, sessionStorage, fragments | **~70-80%.** The one genuine residual gap; see §1.2 |

### 1.2 The residual gap, named precisely

The only thing an MPA cannot fully replicate is client-side state living in memory: a filter kept perfectly across pages, a half-scrolled modal, wizard state, optimistic UI on every interaction. Mitigations that close most of it: URL state (`_list_filter.html` already does this), sessionStorage for drafts, fragment swaps for actions. The gap only matters on interaction-dense surfaces - drag-and-drop planning, real-time collaboration, offline-first editing - none of which exist in UbyHost today. The dominant interaction pattern (navigate, look, act, confirm) is fully covered by the plan.

### 1.3 The price math

Full SPA = 100% of the feel for roughly 5x the cost and ~10x the long-term maintenance (two toolchains, npm dependency churn, state management, API contract drift between FastAPI and frontend types, keyboard and screen-reader support re-implemented from scratch) - plus rewrite risk over the filing path, which rule 1 forbids taking lightly. Turbo-MPA = ~95% of the perceptible feel for roughly a week of executor sessions and zero architectural change, with one operator maintaining one toolchain. The last 5% costs more than the first 95%.

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

Each workstream is independently shippable. Suggested order: W1 → W2 → W3 → W4 → W5.

### W1: One design system — Effort M · Risk MEDIUM (visual regressions)

Goal: exactly three layers for host+admin: `tokens.css` (colors, spacing, radii, shadows, type scale), `components.css` (every `ui_*` macro's styles), `host.css` (app-surface layout). Guest and marketing stylesheets are untouched (D3).

Tasks:

1. Inventory every class used by the host/admin templates; map legacy classes (host-design0123, host2, host-controls) to `ui_*` equivalents. Output: a mapping table in the workstream's task file.
2. Fold `host-controls.css`, `host-design0123.css`, `host2.css` into `components.css`/`host.css`; feature styles (`workflow.css`, `wizard.css`, `cleaning.css`) are folded or kept only if a page genuinely owns them; delete what is folded.
3. Re-point `base.html` to the consolidated set; bump every `?v=` cache key.
4. Freeze the component inventory on `dev_ui.html`: every `ui_*` component in every state (default, hover, focus, disabled, empty, error) lives on that page. A component not on `dev_ui.html` does not exist.

Acceptance:

- No template or stylesheet references the deleted files (`grep -r` clean).
- `App/tests/test_host_geometry.py` passes; before/after 390 px screenshots of the 12 key pages (dashboard, stays, stay detail, reservations, cleaning, housebook, settings, predplatne, admin home, fakturace, customers, customer detail) reviewed by the owner.
- No visual change is *intended* in W1 — this is consolidation, not redesign. Where legacy layers disagreed, `components.css` wins.

### W2: Density discipline — Effort S · Risk LOW

Goal: one attention surface per page. The dashboard's "What needs you" card (comment 0241) becomes the app-wide pattern: the card is *the* place where attention demands live.

Tasks:

1. Banner inventory: list every `ui_banner` / stack currently reachable on each host page.
2. Env banner (`_env_banner.html`) becomes a topbar badge, not a page banner.
3. Billing banner (`_billing_banner.html`) and host alert stack (`_host_alerts.html`) fold into the page's needs-you card (or a topbar badge where no card exists).
4. Onboarding and welcome-back banners appear only in true empty states (no apartments / first visit), never on a working dashboard.
5. `ui_stats` is capped at 4 tiles per page; more than that becomes a second `ui_section` table.

Acceptance: no host or admin page shows more than one banner above its first content section; the dashboard with data shows exactly one attention surface (the needs-you card).

### W3: Instant feel (the motion layer) — Effort M · Risk MEDIUM

Goal: Wolt's click feel without a rewrite. Three layers, each a separate task/PR, in this order. All JS is vanilla ES modules served from `App/app/static/`, no framework, no build step. Every layer is progressive enhancement: with JS off, the app behaves exactly as today.

**L1 — Prefetch (Effort S).** On `pointerover`/`focusin` of a same-origin link, inject `<link rel="prefetch">`. After `requestIdleCallback`, prefetch the sidebar destinations. Respect `Save-Data` and never prefetch POST targets. Expected effect: most sidebar clicks render from cache in <100 ms. This is the single highest-leverage layer of the whole plan (§1.1, component 1).

**L2 — View transitions (Effort S).** Wrap navigations in the View Transitions API (`document.startViewTransition` / cross-document `@view-transition` where supported). Shared-element classes on the shell (sidebar, topbar, page title, primary card) so the content area morphs instead of flashing. Honor `prefers-reduced-motion` (fall back to plain navigation). Fallback where unsupported: today's behavior - and remember the browser matrix in §1.1: Firefox users get the L1-fast navigation without the morph, which is acceptable.

**L3 — Partial swaps (Effort M).** Extend the existing `data-toggle-panel` / `data-dashboard-refresh` patterns into one tiny helper (`App/app/static/app.js`, target ~150 lines): a `data-swap` action fetches the re-rendered fragment and swaps it in place, then posts the existing undo toast. Cover the top ~5 high-frequency flows first: archive/delete stay, mark cleaning done, admin mark-paid, admin storno, plan-change confirm. Server side: the route already re-renders the page; add a `?fragment=…` mode returning the relevant include. Skeleton screens (already built) cover the fetch. These `?fragment=` endpoints are also the proto-API of the §1.5 insurance policy - design their payloads so a future SPA could consume them.

Acceptance (all of W3):

- Playwright tests for the 5 flows assert the swap and the undo path.
- A no-JS walkthrough of the same flows completes them identically.
- Keyboard navigation and screen-reader live regions behave exactly as today through every swap (announce the swap region).
- Perf budget verified on staging: p95 perceived navigation < 200 ms, zero layout shift on L2 morphs.

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
4. `dev_ui.html` is the acceptance surface for all component work; a PR that changes a component's look updates it in the same PR.

## 3. Sequencing and effort

| Phase | Ships | Effort | Risk |
|---|---|---|---|
| W1 design system | alone, first | M (2-3 sessions) | MEDIUM (visual) |
| W2 density | after W1 | S | LOW |
| W3 L1 + L2 | any time after W1 | S+S | MEDIUM (motion) |
| W3 L3 | after L1/L2 | M | MEDIUM |
| W4 admin surface | after W1 (parallel with W3) | M | LOW |
| W5 standard | last | S | LOW |

Total: roughly a focused week of executor sessions spread over 2-3 weeks of owner review. No schema changes, no new dependencies, no new outbound requests, no guest-page changes.

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
