# Business metrics and database direction

Status: staged plan, 2026-10-30. Production remains on SQLite and its current backup path. Metric definitions and source verification come before new analytics infrastructure. UX work and metric-contract work may proceed independently.

## Owner direction and limits

The owner wants a system that can scale without frequent tool changes, prefers staying on a free tier where feasible and using the existing Lightsail capacity where suitable, and has asked that a production database migration be left for a future CTO unless a real need arises. Those preferences guide evaluation; they do not prove available capacity, zero incremental cost, zero risk, or a particular migration effort. Metabase OSS over a separate analytics copy remains a candidate, subject to the conditions below.

Do not change the production database, backups, scheduler, dependencies, containers or production configuration as part of defining metrics. Keep guest and contact data out of extracts unless a specific metric requires a field and that need is documented.

## Metric contract required before implementation

Agree the metric meaning, grain, date rules, currency handling, source fields, exclusions and reconciliation checks before adding an extract or dashboard. Use integer minor units or exact decimals. Keep currencies separate until an FX policy is approved. Use `Europe/Prague` for business dates. Missing history is unavailable, not zero.

| Metric | Required meaning |
|---|---|
| Subscription MRR | Effective recurring platform price, net of VAT and recurring discounts, normalized monthly. Exclude trials, one-off fees and guest/merchant payment volume. |
| Issued invoices | Separate count and amount; define currency, tax, voids, credits and replacement invoices. |
| Overdue invoices | Define due date, qualifying status and remaining-balance rules. |
| Collections | Distinguish an invoice marked paid from cash actually collected or allocated. |
| MRR movement | Opening + new + expansion − contraction − churn = closing. Define reactivation and require sufficient history. |
| Account churn | Eligible paying accounts lost divided by eligible accounts at period start. Cancellation request is distinct from effective end. |
| Trials and account counts | Define grain, eligibility and dates; prevent joins from multiplying accounts. |

## Source observations and verification gaps

The supplied source review records the following observations for re-verification before implementation; they are not production reconciliation results or proof of historical completeness:

- `billing_analytics.py` `portfolio()` derives current portfolio values from quotes and includes `active`, `overdue` and `canceling` accounts.
- Annual normalization uses whole-CZK rounding. Invoice aggregates sum `total_haler`, then truncate to whole CZK.
- Paid aggregation uses invoice `paid_on`; this alone does not establish a cash-allocation ledger.
- Existing-row trends do not prove a complete series of historical months. Snapshot helpers do not prove historical coverage or complete effective-state history.
- Movement, reactivation and churn are not yet verified historical business metrics.
- Portfolio queries include contact/name fields. Do not automatically include them in an extract.
- The defining migrations for `billing_account`, `platform_invoice` and `billing_month_snapshot` still need to be identified and inspected.

Before writing the extraction brief, inspect only relevant ranges and exact symbol matches in:

- `App/app/billing.py` for quote, discount, tax and effective cancellation semantics.
- `App/app/migrations/` for the exact definitions of the three billing tables above; do not audit unrelated migrations.
- Relevant payment, refund or allocation source if collections must mean cash collected.
- Relevant scheduler and mutation call sites for snapshot timing and historical coverage.
- `App/app/db.py` for the existing consistent-read contract.
- Relevant billing tests for source semantics and fixture setup.

Update each observation if current source differs. If a field, policy or history guarantee remains unverified, mark the metric unavailable and keep that gap explicit. Do not infer a cash claim from `paid_on`, zero-fill missing months, or publish movement/churn claims without adequate history.

## First implementation: bounded read-only extraction

After source contracts are verified, prepare a separate implementation brief for a small, read-only extraction of current portfolio values and invoice issue/paid aggregates. Keep the scope limited to the verified fields and definitions. Preserve existing billing-cockpit behavior unless a demonstrated defect requires a compatible correction.

The initial extraction excludes scheduler registration, new drivers or dependencies, schema migrations, containers, Metabase deployment, secrets, production queries and historical movement/churn claims. Use `db.py` helpers and a consistent read. Minimize fields; contact and name data do not enter by default.

Fixtures and reconciliation checks must cover trials, discounts, tax, effective cancellation, credits/refunds, replaced invoices, repeated extraction, date boundaries and missing history. Validate count and amount separately, currency by currency, and compare against the existing source outputs without claiming production reconciliation unless it was actually performed.

## Later analytics architecture candidate

Metabase OSS over a separate analytics copy is a candidate, conditional on verified metric contracts, measured capacity, recovery rehearsal, privacy review and operating cost. “No additional hosting subscription” is a target to evaluate, not a guarantee of zero cost or zero risk. Do not deploy it as part of the metric-definition or extraction work.

If approved later, the data path should be:

```text
Production source
  -> consistent minimal snapshot
  -> isolated analytics load
  -> validated published generation
  -> Metabase reporting
```

The implementation brief must define:

- SQL through `db.py` helpers and a consistent extraction boundary.
- A minimal field allowlist with a reason for every personal-data field.
- Staging generations with run ID, schema version and source timestamp.
- Validation before transactional publication, idempotent retries, and correction/deletion propagation.
- Failed refresh behavior that retains the last successful generation and marks it visibly stale.
- Last successful source time, expected refresh, and independent freshness/missed-heartbeat checks.
- A read-only BI reporting role and private database networking.
- Metabase’s persistent production application database for dashboards, users and configuration, separate from its reporting connection; do not use embedded H2 in production.
- Off-host backups for configuration/application data and a demonstrated restoration of a dashboard and access settings.
- Measured RAM, CPU, disk growth and I/O alongside the app, workers, monitoring and backups before choosing resource limits. Previously proposed Postgres and Metabase memory caps are unverified.

## Production database migration: deferred

Reconsider PostgreSQL only for an actual requirement, such as another app/worker host, harmful write contention, or stronger availability obligations. A future migration plan must verify compatibility and filing/money behavior, define downtime and RPO/RTO, identify owners, and rehearse both data reconciliation and recovery.

Before cutover, quiesce web mutations, workers, schedulers and callbacks, then perform a final reconciliation before destination writes. Rehearse post-write recovery and reconcile external side effects. An untouched SQLite file is not a sufficient rollback plan after PostgreSQL has accepted authoritative writes.

## Verification and deliverables

- Keep documentation and extraction work within the repository’s task and test-map rules.
- A future extraction brief must list verified source fields, financial policies, exact file allowlist, fixtures and matching/reconciliation checks.
- A future infrastructure brief must include capacity, failure, stale-publication, security, backup and restore criteria.
- Run only applicable test-map rows when implementation is requested; documentation-only work does not imply application tests or production validation.
- Record unresolved definitions and owner decisions as blockers instead of filling gaps with estimates.
