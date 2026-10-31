# UbyHost: self-contained CTO plan and executor handoff

## Repository and objective

Repository: https://github.com/jsfpechar-ops/jsfpecharoperations

Review and continue the work introduced by:

- PR #581: host/admin UX improvements.
- PR #582: business metrics and database strategy.

Both PRs were merged when reviewed. Their plans need the corrections below.

All unpublished findings and planning decisions required for this handoff are included here. File paths identify files in the repository; no access to the previous agent’s computer, branch, reports or temporary files is required.

You need repository source access before changing application code. If you cannot access it, report that limitation and request the specific source files needed. Do not invent their contents.

Application implementation remains to be written and verified.

## Execution rules

Read the repository’s AGENTS.md and relevant routing documents. The owner requested Luna for implementation under orchestrator review, overriding the Haiku-only executor choice for this work.

Work in small, separately reviewable tasks. No whole-repository audit, framework rewrite, new dependency without its required decision, production migration or deployment.

Owner retains merges, secrets and server operations.

Do not bypass any publishing/security restriction. Produce the changes and report within the execution environment’s approved capabilities.

## 1. Correct the planning documents

Update these existing files using the decisions below:

```text
docs/plans/ux-smoothness-plan-20261030.md
docs/plans/business-metrics-and-database-plan-20261030.md
docs/context/rules.md — UX and interaction section
```

Keep status, decisions and known issues consistent within their size limits.

Create implementation briefs using `docs/tasks/TEMPLATE.md` and available task numbers. Do not assume unpublished tasks numbered 0451–0454 exist in your checkout.

### UX plan replacement decisions

Keep FastAPI, Jinja, light mode and progressive enhancement.

Preserve:

- Command palette and keyboard navigation.
- Existing server-supported undo.
- Skeletons, offline page and PWA.
- Screen-reader announcements and existing languages.
- Core navigation and server forms without JavaScript.
- Server authorization and existing phone navigation.

Guest, marketing, authentication and legal pages retain their own rules.

Remove unsupported claims about:

- “95% of Wolt.”
- Fivefold development and tenfold maintenance costs.
- One-week delivery.
- Guaranteed sub-200 ms navigation.
- Zero production or filing risk.

A complete stylesheet consolidation, database migration and unrelated backlog are not prerequisites for useful UX work.

Deliver:

1. One demonstrated dashboard or desktop admin-navigation improvement.
2. Further page-specific attention, density, filters, empty states and admin improvements.
3. Style consolidation alongside the affected components.
4. Separately measured prefetch, transition and partial-action pilots.

Each task needs verified source anchors, a small file allowlist, exact changes and concrete acceptance checks.

### Binding UX rules to retain

- Reuse existing tokens/components. Map callers and cascade behavior before removing styles.
- Legacy and justified page-owned styles may coexist during migration.
- Do not delete files merely to reach a three-stylesheet target.
- Prefer one coherent attention area and at most four summary tiles, allowing justified exceptions.
- Preserve warning severity, action, dismissal and visibility. A badge cannot hide a blocking warning.
- Follow MASTER and the changed page’s add-on, including phone More navigation.
- Update the component catalog with changed components.
- Measure performance rather than promise it.

### Performance and interaction requirements

Record route, browser/device, viewport, network, cache state and sample count. Measure cold, warm and back/forward navigation separately. Treat 200 ms as an aspirational warm-navigation target.

Prefetch:

- Explicit allowlist of verified side-effect-free GETs.
- Exclude sign-out, exports/downloads, token creation, action links and payment/authentication destinations.
- Bound/deduplicate requests; respect cache policy and data saving.
- Verify logout, account switching and fresh-data visibility.
- Do not weaken security policy to make caching work.

Transitions:

- Cross-document transitions require same-origin CSS opt-in on both documents.
- `document.startViewTransition()` is for a DOM update within the current document.
- Preserve reduced-motion and unsupported-browser fallbacks.

Partial actions:

- Start with one low-impact action whose server-supported reversal is verified.
- Specify CSRF/roles, duplicate submissions, uncertain mutation results, errors, expired sessions, focus and announcements.
- Preserve the ordinary no-JS form.
- Never blindly retry an uncertain mutation.
- Financial actions require separate durable-result, audit and compensating-action contracts. A toast does not reverse an issued invoice or external payment.

## 2. Do not implement the discarded dashboard severity proposal

A previous preparation pass proposed aggregating every attention line’s severity in the dashboard template.

Additional source review showed that the producer already sorts the lines:

```python
# Existing source in App/app/needs_you.py
lines.sort(key=lambda line: _TONE_RANK.get(line["tone"], 1))
```

The existing rich-dashboard browser fixture also asserts sorted tone ranks and a red first item:

```text
App/tests/test_host_quiet_dashboard_browser.py
Reviewed assertions around lines 323–327.
```

The template’s first-item summary is consistent with that producer contract.

Reverify against current source, but do not add redundant template aggregation or a duplicate regression test without a demonstrated defect.

Choose another useful UX improvement. Start with the relevant sections of:

```text
App/app/templates/base.html
App/app/templates/dashboard.html
App/app/templates/_shell_sidebar.html
App/app/templates/_shell_topbar.html
docs/design/MASTER.md
docs/design/pages/dashboard.md
```

Inspect the specific browser fixtures needed for the selected change.

## 3. Correct the analytics and database plan

Keep production SQLite and its current backup path.

Define and reconcile business metrics before adding infrastructure.

Metabase OSS over a separate analytics copy is the preferred candidate, conditional on capacity, recovery and operational cost. “No additional hosting subscription” is a target, not a zero-cost or zero-risk guarantee.

UX and metric-contract work proceed independently.

### Required metric definitions

| Metric | Required meaning |
|---|---|
| Subscription MRR | Effective recurring platform price, net of VAT and recurring discounts, normalized monthly. Exclude trials, one-off fees and guest/merchant payment volume. |
| Issued invoices | Separate count and amount, with currency, tax, voids, credits and replacements defined. |
| Overdue invoices | Explicit due-date, status and remaining-balance rules. |
| Collections | Distinguish invoice-paid status from actual cash/payment allocations. |
| MRR movement | Opening + new + expansion − contraction − churn = closing; explicit reactivation policy and sufficient history. |
| Account churn | Eligible paying accounts lost divided by eligible accounts at period start; cancellation request differs from effective end. |
| Trials/account counts | Explicit grain, eligibility and dates; joins cannot multiply accounts. |

Use integer minor units or exact decimals. Keep currencies separate until an FX policy exists. Define business dates with `Europe/Prague`.

Missing history means unavailable, not zero.

## 4. Analytics source findings already established

The previous source inspection covered:

```text
App/app/billing_analytics.py
App/app/db.py — relevant ranges
App/tests/test_billing_analytics.py
```

Findings to reverify against current source:

- `portfolio()` calculates current quote-derived portfolio values.
- It includes `active`, `overdue` and `canceling`.
- Annual normalization uses whole-CZK rounding.
- Invoice aggregates sum `total_haler`, then truncate to whole CZK.
- Paid aggregation uses invoice `paid_on`; this does not establish a cash-allocation ledger.
- Existing-row trends do not prove a complete historical month series.
- Snapshot helpers do not establish historical coverage or complete effective-state history.
- Movement/reactivation/churn are not yet verified historical business metrics.
- Portfolio queries include contact/name fields that must not automatically enter the extract.
- Billing-table definitions were not found in the inspected baseline schema; their defining migrations remain to be inspected.

These are source observations, not production reconciliation results.

### Resolve these gaps next

Inspect only the relevant sections of:

```text
App/app/billing.py
    Quote, discount, tax and cancellation semantics.

App/app/migrations/
    Exact migrations defining billing_account,
    platform_invoice and billing_month_snapshot.

Relevant payment/refund/allocation source
    If the metric must represent collected cash.

Relevant scheduler and mutation call sites
    Snapshot timing, updates and historical coverage.

App/app/db.py
    Existing consistent-read/snapshot contract.

Relevant existing billing tests
    Source semantics and fixture setup.
```

Grep exact symbols/table names before reading ranges. Do not audit all migrations or routes.

Then write a complete implementation brief containing verified fields, exact patch, minimal allowlist, financial policies, reconciliation and matching checks.

### First application implementation

Implement a small, read-only extraction for current portfolio values and invoice issue/paid aggregates after their meanings are verified.

Initially exclude:

- Scheduler registration.
- New drivers/dependencies.
- Schema migrations.
- Containers and Metabase deployment.
- Secrets and production queries.
- Historical movement/churn claims.

Preserve existing cockpit behavior unless a verified defect requires a compatible correction.

Include fixtures for trials, discounts, tax, effective cancellation, credits/refunds, replaced invoices, repeated extraction, date boundaries and missing history.

## 5. Later analytics infrastructure

Target architecture:

```text
Production source
  -> consistent minimal snapshot
  -> isolated analytics load
  -> validated published generation
  -> Metabase reporting
```

Requirements:

- SQL through `db.py` helpers.
- Consistent extraction and explicit field minimization.
- Staging generations with run ID, schema version and source timestamp.
- Transactional publication after validation.
- Idempotent retries and correction/deletion propagation.
- Failed refresh retains the last successful generation, visibly stale.
- Display last successful source time and expected refresh.
- Independent freshness/missed-heartbeat checks.
- Read-only BI reporting role and private database networking.

Metabase requires a persistent production application database for dashboards/users/configuration, separate from its reporting connection. Do not use embedded H2 in production.

Back up configuration/application data off-host and demonstrate restoration of a dashboard and access settings.

Measure RAM, CPU, disk growth and I/O alongside the app, workers, monitoring and backups before choosing limits. Earlier 512 MB Postgres and 1 GB Metabase caps were unverified.

## 6. Production migration stays deferred

Reconsider PostgreSQL for an actual requirement: another app/worker host, harmful write contention or stronger availability obligations.

A future migration needs:

1. Verified compatibility and filing/money rehearsals.
2. Exact reconciliation and tested recovery.
3. Defined downtime, RPO/RTO and ownership.
4. Quiescence of web mutations, workers, schedulers and callbacks.
5. Final reconciliation before destination writes.
6. Rehearsed post-write recovery and external-side-effect reconciliation.

An untouched SQLite file is insufficient rollback after PostgreSQL accepts new authoritative writes.

## 7. Verification and deliverables

Run only applicable rows from `docs/context/test-map.md`.

Host changes require relevant browser checks, geometry/design guardrails with zero skipped, before/after 390 px screenshots and required layout/touch/WebKit checks.

Billing changes require the applicable billing tests and new fixtures.

Run documentation lint and whitespace checks:

```bash
set -o pipefail
python3 scripts/context_lint.py 2>&1 | tail -30
git diff --check 2>&1 | tail -30
```

Deliver:

1. Corrected plans and binding UX guidance.
2. A verified metric source contract with explicit gaps.
3. One complete UX implementation brief and one complete extraction brief.
4. Implementation of each brief only after its source contracts are complete.
5. Exact diff, checks actually run, screenshots where applicable, remaining blockers and owner steps.

Do not equate source inspection with passing tests, merged code with deployment, or invoice-paid status with reconciled cash.