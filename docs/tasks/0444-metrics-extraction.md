# 0444: read-only business-metrics extraction (current values only)

Status: todo
Depends on: none (metric definitions: business-metrics-and-database-plan-20261030.md §5a) | Base commit: 8b5317d0 | Branch: task/0444-metrics-extraction
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Implement a small, read-only extraction module for the verified business metrics: current portfolio values and invoice issue/paid aggregates, with meanings verified against source. It serves the operator's morning checklist and the future analytics copy without touching the production database, the scheduler, or the cockpit.

## 2. Context

The rules that apply, pasted in. Exact code excerpts, each with its file path. If an excerpt isn't found verbatim, STOP (§8).

Metric meanings (docs/plans/business-metrics-and-database-plan-20261030.md §5a, verified against source 2026-10-30):

- **Current portfolio values** (`billing_analytics.portfolio()`): quote-derived from `billing.quote` per account; net of recurring `discount_percent`; includes `carry_czk`; MRR states `("active", "overdue", "canceling")` (`MRR_STATES`, App/app/billing_analytics.py:16); annual normalization rounds whole-Kč (`_monthly`, App/app/billing_analytics.py:33). VAT: `config.BILLING_VAT_STATUS` (App/app/config.py:334, default `non_payer`) — prices are final, VAT is not line-itemized.
- **Invoice issue aggregates** (`revenue_totals()`): sum `total_haler` (integer minor units) over `voided = 0` invoices in the month, then truncate to whole CZK (`// 100`). Storno marks the corrected invoice `voided = 1` (App/app/billing_invoices.py:160) and requires it unpaid (App/app/billing_invoices.py:207-216), so voided invoices already leave issue aggregates; the storno document itself has negative items and `kind='storno'`.
- **Invoice paid aggregates**: `paid_on` in month, `voided = 0`. This is invoice-paid STATUS, not a cash-allocation ledger. The only allocation evidence is `bank_payment.matched_invoice_id` (App/app/migrations/0023_billing.sql:75-85, set by `App/app/bank_import.py:199-208`).
- No partial payments, refunds or allocation ledger exist in source; reports must label paid aggregates as "invoice-paid", not "collected cash".

Schema (verified):

```sql
-- App/app/migrations/0023_billing.sql
CREATE TABLE IF NOT EXISTS billing_account (... status TEXT ... CHECK (status IN
  ('trial_pending','trialing','active','overdue','canceling','paused')) ...);
CREATE TABLE IF NOT EXISTS platform_invoice (... kind TEXT NOT NULL CHECK (kind IN
  ('invoice','supplementary','storno')), total_haler INTEGER NOT NULL, voided INTEGER
  NOT NULL DEFAULT 0, paid_on TEXT, paid_via TEXT ...);
CREATE TABLE IF NOT EXISTS bank_payment (bank_tx_id TEXT PRIMARY KEY, received_on TEXT
  NOT NULL, amount_haler INTEGER NOT NULL, vs TEXT, ..., matched_invoice_id INTEGER
  REFERENCES platform_invoice(id), status TEXT NOT NULL CHECK (status IN
  ('matched','unmatched','partial','overpaid')));
```

Snapshot coverage: `write_month_snapshot()` (App/app/billing_analytics.py:236) is called daily for the CURRENT month (`App/app/scheduler.py:407-421`, `_job_billing_snapshot`) and by billing mutations (`App/app/routes/admin_customers.py:149,168,249`). Historical months are NOT backfilled; missing history is unavailable, never zero.

Binding rules:

- SQL only through `App/app/db.py` helpers, parameterised; no SQLite-only syntax (`docs/context/rules.md` §Database).
- Never log personal data; log ids and counts only (§Privacy). Contact/name/email fields from `portfolio()` queries do NOT enter the extraction output.
- Money: integer minor units internally; whole-Kč only at presentation boundaries, truncation stated explicitly. Currencies stay separate (CZK only today). Business dates Europe/Prague.
- Preserve existing cockpit behavior; no route changes; no new dependency; no scheduler registration; no migration; no container.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/metrics_extract.py | create | Read-only extraction: `current_metrics()` returning verified current values with explicit availability flags |
| App/tests/test_metrics_extract.py | create | Fixtures and assertions per §4 step 5 |
| docs/tasks/0444-report.md | create | The report per TEMPLATE §9 |

No other file may change.

## 4. Steps

1. Create `App/app/metrics_extract.py`:

```python
"""Read-only business-metrics extraction (brief 0444).

Current portfolio values and invoice issue/paid aggregates only. Meanings are
defined in docs/plans/business-metrics-and-database-plan-20261030.md §5a and
verified against billing.py, billing_analytics.py and migration 0023/0031.
Paid aggregates are invoice-paid status, NOT a cash-allocation ledger. History
that was never snapshotted is unavailable (None), never zero.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from . import billing_analytics, db


def current_metrics(today: Optional[date] = None) -> Dict[str, Any]:
    """Today's verified values. No writes, no history claims."""
    day = today or date.today()
    month_start = f"{day:%Y-%m}-01"
    portfolio = billing_analytics.portfolio(day)

    issued = db.query_one(
        "SELECT COUNT(*) AS n, COALESCE(SUM(total_haler), 0) AS h FROM platform_invoice "
        "WHERE voided = 0 AND issue_date >= ? AND issue_date < date(?, '+1 month')",
        (month_start, month_start),
    )
    paid = db.query_one(
        "SELECT COUNT(*) AS n, COALESCE(SUM(total_haler), 0) AS h FROM platform_invoice "
        "WHERE voided = 0 AND paid_on >= ? AND paid_on < date(?, '+1 month')",
        (month_start, month_start),
    )
    storno = db.query_one(
        "SELECT COUNT(*) AS n FROM platform_invoice WHERE voided = 0 AND kind = 'storno' "
        "AND issue_date >= ? AND issue_date < date(?, '+1 month')",
        (month_start, month_start),
    )
    # Invoice-paid status; a cash-allocation ledger does not exist (plan §5a).
    allocated = db.query_one(
        "SELECT COALESCE(SUM(amount_haler), 0) AS h FROM bank_payment "
        "WHERE matched_invoice_id IS NOT NULL AND received_on >= ? "
        "AND received_on < date(?, '+1 month')",
        (month_start, month_start),
    )

    # MRR movement needs snapshot history; current-month-only coverage means
    # movement/churn are unavailable, never zero (plan §5a).
    snapshot_months = db.query_one(
        "SELECT COUNT(DISTINCT month) AS n FROM billing_month_snapshot"
    )
    history_available = int(snapshot_months["n"]) >= 2

    return {
        "as_of": day.isoformat(),
        "mrr_czk": portfolio["mrr_czk"],
        "arr_czk": portfolio["arr_czk"],
        "by_status": portfolio["by_status"],
        "issued_invoices": {
            "count": int(issued["n"]),
            "total_haler": int(issued["h"]),
            "total_czk_truncated": int(issued["h"]) // 100,
        },
        "invoice_paid": {  # invoice-paid status, not reconciled cash
            "count": int(paid["n"]),
            "total_haler": int(paid["h"]),
            "total_czk_truncated": int(paid["h"]) // 100,
        },
        "storno_in_month": int(storno["n"]),
        "bank_allocated_haler_month": int(allocated["h"]),  # matched only
        "movement": {"available": history_available},
        "account_churn": {"available": history_available},
    }
```

2. Verify every symbol the module uses still matches source (`billing_analytics.portfolio`, `db.query_one`, the three table names). If any excerpt in §2 is not found verbatim, STOP (§8).
3. Sanity-run: `python3 -c "from app import metrics_extract" 2>&1 | tail -5` from `App/` (or the repo's conftest pattern if imports need the app root).
4. Create `App/tests/test_metrics_extract.py` with fixtures covering, at minimum: a trial account (excluded from MRR), a recurring discount account (net, not list), an annual account (monthly normalization whole-Kč rounding), an effective cancellation (status canceling counts; `cancel_at_period_end` alone does not), a voided invoice (excluded from issue aggregates), a storno document (counted in `storno_in_month`, not in issued totals), an invoice paid in-month and one paid outside the month, a matched and an unmatched `bank_payment` (only matched enters `bank_allocated_haler_month`), repeated extraction (idempotent, no writes), a month boundary (day 1 vs last day), and a single-snapshot-month database (movement/churn unavailable, not zero). Base fixture setup on `App/tests/test_billing_analytics.py`'s existing helpers; if its fixture shape differs from this list, adapt the tests to the helpers you find and note the deviation.
5. Run the commands in §6.

## 5. Do not touch

- `App/app/billing_analytics.py`, `App/app/billing.py`, `App/app/billing_invoices.py`, `App/app/bank_import.py` (existing cockpit behavior; no compatible correction has a demonstrated defect yet).
- `App/app/scheduler.py`, `App/app/routes/` (no registration, no route).
- `App/app/migrations/` (no schema change; `db.SCHEMA` frozen).
- `requirements.txt` / `requirements.lock` (no new dependency).
- Any personal-data field: contact/name/email stay out of the output.

## 6. Commands

From `App/`, each ending `2>&1 | tail -30`:

```
python3 -m pytest tests/test_metrics_extract.py -q --tb=short -x
python3 -m pytest tests/test_billing_analytics.py -q --tb=short -x
python3 -m pytest tests/test_billing_core.py tests/test_billing_admin.py -q --tb=short -x
```

Expected: all pass; the existing suites prove no cockpit regression.

## 7. Acceptance

- [ ] `metrics_extract.current_metrics()` returns only verified current values; no historical movement/churn numbers.
- [ ] Paid aggregates labeled as invoice-paid status; `bank_allocated_haler_month` only over `matched_invoice_id IS NOT NULL`.
- [ ] Missing history returns `available: False`, never zero-valued history metrics.
- [ ] All fixtures in §4 step 4 exist and pass.
- [ ] No writes to any table during extraction (tests prove idempotence).
- [ ] Existing billing suites pass unchanged.
- [ ] Output contains no personal-data fields (no name/email/username keys).

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/0444-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/metrics_extract.py` (new, read-only)
- `App/tests/test_metrics_extract.py` (new)

## Owner steps

1. Review the PR diff (two new files only).
2. Merge with `scripts/merge-pr-on-green.sh <pr>`; no deploy required for a read-only module until a surface consumes it.
