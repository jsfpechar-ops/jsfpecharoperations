# 0452: Read-only legacy billing analytics extract

Status: blocked
Depends on: none | Base commit: verify at execution | Branch: task/0452-read-only-billing-extract
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add a small, read-only export that reports the existing quote-derived portfolio and non-void invoice totals for an explicit month range. This gives an auditable, privacy-minimized source copy while keeping legacy quote figures and invoice paid markers separate from approved finance KPIs.

## 2. Context

The source schema and relevant writers were verified. Apply these constraints:

- `App/app/billing_analytics.py:38-82`: `portfolio()` queries plan-bearing billing accounts joined to user accounts, includes names/contact details, computes values through `billing.quote()`, adds `carry_czk`, and counts `active`, `overdue`, `canceling` in its MRR/ARR. Annual monthly normalization is per-account `round(net / 12)`. Do not call this function from the extract because it selects PII and uses separate helper queries.
- `App/app/billing_analytics.py:86-101, 319-332`: invoice summaries use `total_haler`, `voided = 0`, `issue_date` or `paid_on`; paid-date totals are invoice totals marked paid, not payment allocations. Existing trend rows are incomplete as a calendar series. Reproduce only the bounded aggregate and label the paid-date measure precisely.
- `App/app/billing.py:66-104`: `quote()` accepts apartment count, plan, interval, add-on flags, founder and discount percent. It returns whole-Kč list/discount/net values; do not relabel that legacy result as reconciled subscription MRR or add VAT assumptions.
- `App/app/migrations/0023_billing.sql:14-40,42-68`: billing account and invoice fields. `total_haler` is integer; invoices include `kind`, `corrects_id`, `voided`, and `paid_on`. Keep source query semantics at `voided = 0`; do not silently remove storno/supplementary kinds.
- `App/app/migrations/0031_billing_discount_snapshot.sql:1-29`: snapshot includes derived whole-Kč values and account/month primary key; it is not required by this export. Avoid it.
- `App/app/scheduler.py:411-420`: current monthly snapshot refresh runs daily and upserts through `write_month_snapshot()`. `rg` also found snapshot calls in `routes/admin_customers.py:149,168,249`; do not invoke them. This extract must not change snapshot state.
- `App/app/db.py:888-900,1354-1364`: `db.cursor()` supplies a deferred transaction; use one cursor for all SELECTs so both output sections share one read transaction. Use only parameterized SELECT statements.

Output schema, version 1:

1. `portfolio_quote.csv`: `as_of_date,status,plan_account_count,legacy_quote_monthly_czk,legacy_quote_annual_czk`. One row per status, including statuses with no rows only if convenient; omit zero-only rows for a simpler implementation. Counts include only `plan IS NOT NULL`. The legacy amounts sum each account's current quote net plus `carry_czk`; monthly plans use monthly net × 12 for annual amount; annual plans use per-account `round(net / 12)` for monthly and annual net for annual amount. Only `active`, `overdue`, and `canceling` contribute amounts. Name columns and export manifest must say “legacy quote”; do not assert VAT treatment.
2. `invoice_month_totals.csv`: `month,basis,nonvoid_invoice_count,total_haler`. `basis` is `issue_date` or `paid_on`; each query includes only `voided = 0` rows in requested inclusive month range. `paid_on` rows must be labeled in manifest/report as **invoice totals marked paid by paid_on**, never cash collections. Keep integer minor-unit aggregate exact; no whole-Kč truncation.
3. `manifest.json`: `schema_version`, UTC `generated_at`, `from_month`, `through_month`, and fixed text definitions for both metric groups. Do not include account IDs, invoice IDs/numbers, contact/name data, bank references, or free text.

### Exact proposed code/diff

Only add `App/scripts/export_billing_analytics.py` and `App/tests/test_billing_analytics_export.py`. Do not modify `billing_analytics.py`, database schema, scheduler, routes, retention records, config, dependencies, or production data.

In the script:

1. Add stdlib-only CLI arguments `--from-month YYYY-MM`, `--through-month YYYY-MM`, and `--output-dir PATH`. Validate month strings with `date.fromisoformat(f"{value}-01")`, reject invalid or reversed ranges, and create output dir only after validation. Write the three outputs to temporary sibling files and atomically replace target files after all extraction succeeds.
2. Compute explicit Prague `as_of_date` with `datetime.now(ZoneInfo("Europe/Prague")).date()` and manifest `generated_at` in UTC. Use stdlib `zoneinfo`; add no dependency.
3. Within `with db.cursor() as cur:`, query only these account fields, without IDs or user joins: `status, plan, billing_interval, apartments_billed, addon_ttlock, addon_whitelabel, founder, carry_czk, discount_percent` from `billing_account WHERE plan IS NOT NULL`. For each row call `billing.quote()` with those inputs, add `carry_czk` to returned `total`, reproduce the legacy per-account monthly/annual rounding and status inclusion rules above, and aggregate by status. Do not select `discount_reason`, pending changes, buyer/contact fields, trial dates, or payment method.
4. In the same cursor transaction, run two separate bounded aggregates. For issue basis: `SELECT substr(issue_date,1,7) AS month, COUNT(*) AS n, COALESCE(SUM(total_haler),0) AS h FROM platform_invoice WHERE voided = 0 AND issue_date >= ? AND issue_date < ? GROUP BY substr(issue_date,1,7)`. For paid basis, substitute `paid_on` and add `paid_on IS NOT NULL`. Bind the first day of `from_month` and the first day after `through_month`; construct those dates using Python `date`, not SQL string interpolation. Keep results integer-valued.
5. Emit stable UTF-8 CSV with headers above and JSON manifest. Use no account/invoice row export, no BI destination, no scheduler, no database writes, and no implicit broad date range.

Exact path handles 

- `App/scripts/`: add the standalone CLI.
- `App/tests/test_billing_analytics_export.py`: add focused stdlib/pytest tests.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/scripts/export_billing_analytics.py` | Add | Bounded, read-only source extraction and local CSV/JSON output. |
| `App/tests/test_billing_analytics_export.py` | Add | CLI validation, allowlist/query behavior, aggregation, privacy and labels. |

No other file may change.

## 4. Steps

1. Inspect only the existing `App/scripts` naming conventions and the relevant billing test fixture helpers; use `rg` first. Confirm there is no conflicting script/test name. If a different existing pattern is required, stop and report before adding files.
2. Add the script as specified in §2. Keep source queries inside one `db.cursor()` transaction and call `billing.quote()` directly. Do not invoke `portfolio()`, `write_month_snapshot()`, `movement()`, `funnel()`, routes, or scheduler jobs.
3. Add tests with a temporary test database and explicit fixtures: exact MRR inclusion/exclusion for each status; monthly/yearly quote normalization and carry; query projections contain no PII/IDs; requested month bounds and empty periods; paid-date label/column; invalid/reversed month ranges fail before files are created; output contains no identifiers or free-text fields; source tables remain unchanged.
4. Run only the §6 commands. Inspect the final diff and ensure only §3 files changed.

## 5. Do not touch

- No App routes, templates, scheduler, existing dashboard analytics, migrations, snapshot tables, invoices, payment/refund matching, retention, analytics infrastructure, containers, hosting, deployment or database files.
- No raw account, invoice, payment, or user identifiers in output. Do not add a new personal-data field.
- No cash collections, revenue, VAT-exclusive/inclusive, FX-normalized MRR, issued-invoice policy beyond current non-void totals, credits, churn, movement, history coverage, or forecast claims.
- No third-party request, dependency, secrets, or production database access. Export target must be explicitly supplied by the operator.

## 6. Commands

From repo root, inspect only needed conventions before coding:

```sh
rg --files App/scripts App/tests | rg 'billing|export' | head -50
```

From `App/`, run the focused new test and existing source regression file:

```sh
.venv/bin/python -m pytest tests/test_billing_analytics_export.py tests/test_billing_analytics.py -q --tb=short -x 2>&1 | tail -30
```

From repo root:

```sh
python3 scripts/context_lint.py 2>&1 | tail -30
```

Do not run the full suite. Do not run the exporter against production. Tests must use a temporary database and temporary output directory.

## 7. Acceptance

- [ ] The extractor uses one read transaction and only the approved column projections and date-bounded aggregates.
- [ ] The source database is unchanged after extraction; snapshots are not touched.
- [ ] Portfolio columns and manifest call amounts `legacy_quote`; invoice paid-date totals are called invoice totals marked paid by `paid_on`.
- [ ] No identifiers, contact fields, bank references, buyer fields, or free-text fields appear in outputs.
- [ ] Integer `total_haler` sums remain exact; no currency conversion or tax assumptions are added.
- [ ] Tests cover all cases in §4 and pass; context lint passes.
- [ ] Diff contains only §3 files.

## 8. Stop and ask

This brief is blocked before implementation: standalone script import conventions and DB test fixture setup were not inspected, and those exact patterns are needed to provide a verified patch and executable fixture-specific tests. The metrics are intentionally limited to the labels in §2; finance-policy questions do not block this narrow extract, but any request to broaden its financial meaning does. Executor must inspect only the relevant script convention and billing test fixture helper, then replace this proposed implementation with an exact code diff and concrete tests/expected outputs before changing App files. Also stop if the source schema differs from cited migrations, a new dependency or file outside §3 is needed, or an output needs a financial label not supported here.

## 9. Report

Write `docs/tasks/0452-report.md` (600 tokens at most), set this brief to `Status: review`, and report files changed, exact commands and last five output lines, §7 checklist, deviations, questions, and owner steps. No owner action is required to review the local-only output; do not publish or deploy it.

## Risk list (for the reviewer)

Read both added files. Confirm no source table writes or unapproved fields, and verify the explicit legacy/paid-marked labels survive in CSV and manifest.

## Owner steps

1. Review the added script and focused tests.
2. If approved, run it only against an explicitly chosen non-production/test database and output directory. Production use requires a separate owner decision and a controlled environment.
