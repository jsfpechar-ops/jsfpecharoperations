# 1867: zero-amount invoices must never show "Pay the invoice" (100% discount / 0 apartments)

Status: review
Depends on: none | Base commit: a509bc33ed7a6959773b3986271a637ed9c68601 (main, PR #1131 merged) | Branch: task/1867-zero-amount-invoices
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Owner set a workspace to 0 subscription cost (discount_percent = 100), yet the host page
still shows the overdue billing banner with "Pay the invoice". Root cause (reproduced in a
test): `billing_invoices.issue()` stores a 0 Kč invoice with `paid_on = NULL`; the daily
dunning (`billing_jobs._unpaid_overdue` / Go `unpaidOverdue`) treats any unpaid invoice past
due as collectible, flips the account to `overdue`, and `billing_trial.banner` then shows the
pay banner. Fix: zero-amount invoices are not collectible — dunning ignores them, `settle`
ignores them, and the daily dunning run settles accounts stuck in `overdue` with only
zero invoices left. Python and Go stay exact-diff mirrors.

## 2. Context

Rules: AGENTS.md rule 1/5/11 (Go-first parity: both `App/` Python and `go/` change together),
test-map row "Platform billing, subscription, trial": `test_billing_*.py`; Go: `go test
./internal/billingjob/... ./internal/web/billing/...` (DB tests skip without
`UBYHOST_TEST_DATABASE_URL`; CI postgres shards run them). No schema change (no migration):
`platform_invoice.paid_via` CHECK stays as is; we never write paid_on for zero invoices.

Repro (confirmed locally): discount 100 → `issue_for_period` → `total_haler = 0, paid_on NULL`
→ set due_date past → `dunning()` → counts `{'overdue': 1, ...}`, status `overdue`,
`billing_trial.banner(owner) == {'kind': 'overdue', 'warning': True, 'date': ''}`.

Verbatim excerpts (STOP, §8, if any is not found):

`App/app/billing_jobs.py` `_unpaid_overdue`:
```
        "WHERE i.kind IN ('invoice', 'supplementary') AND i.voided = 0 AND i.paid_on IS NULL "
        "AND i.due_date < ? AND (? IS NULL OR i.owner_user_id = ?) ORDER BY i.id",
```
`App/app/billing_jobs.py` `dunning` start: `    counts = {"overdue": 0, "reminded": 0, "paused": 0}`
`App/app/billing_jobs.py` `settle` still-query:
```
        "SELECT 1 AS n FROM platform_invoice WHERE owner_user_id = ? AND kind IN ('invoice', 'supplementary') "
        "AND voided = 0 AND paid_on IS NULL AND due_date < ?",
```
`go/internal/billingjob/dunning.go` `unpaidOverdue`:
```
		 WHERE i.kind IN ('invoice', 'supplementary') AND i.voided = 0 AND i.paid_on IS NULL
		   AND i.due_date < $1 AND ($2::bigint = 0 OR i.owner_user_id = $2)
		 ORDER BY i.id`, today.Format(isoDate), r.Owner)
```
`go/internal/billingjob/dunning.go`: `type dunningCounts struct{ overdue, reminded, paused int }`
and dunning's `return c, nil` at the end of the function (after the mail loop).
`go/internal/billingjob/run.go`: `DunningOverdue, DunningReminded, DunningPaused        int` in Counts;
`"dunning_overdue": c.DunningOverdue, "dunning_reminded": c.DunningReminded,
		"dunning_paused": c.DunningPaused,` in Map; Total() sum list; and
`c.DunningOverdue, c.DunningReminded, c.DunningPaused = d.overdue, d.reminded, d.paused`.
`go/internal/web/billing/payer.go` settle still-query:
```
	err = p.pool.QueryRow(ctx, `SELECT 1 FROM platform_invoice WHERE owner_user_id = $1 AND kind IN ('invoice', 'supplementary')
		AND voided = 0 AND paid_on IS NULL AND due_date < $2 LIMIT 1`, owner, day).Scan(&one)
```

Do NOT change `billing_invoices.issue()` / Go `issue()`: auto-paying zero invoices at issue
would break `apply_discount`'s reissue-if-unpaid path (it only reissues `paid_on IS NULL`
invoices; a paid zero invoice would block re-billing after the discount is removed).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/billing_jobs.py` | edit | `_unpaid_overdue` + `settle` add `total_haler > 0`; `dunning` counts gain `settled` and a post-loop settle of stuck `overdue` accounts |
| `go/internal/billingjob/dunning.go` | edit | `unpaidOverdue` + `total_haler > 0`; `dunningCounts` gains `settled`; post-loop settle of overdue accounts not in the positive list |
| `go/internal/billingjob/run.go` | edit | Counts/Map/Total gain `DunningSettled`; assignment line |
| `go/internal/web/billing/payer.go` | edit | settle still-query + `total_haler > 0` |
| `App/tests/test_billing_jobs.py` | edit | new zero-amount test; update exact-count assertions if any |
| `go/internal/billingjob/run_test.go` | edit | Counts test covers `dunning_settled` if it asserts Map/Total exactly |
| `docs/context/decisions.md` | edit | one append-only decision line |
| `docs/tasks/1867-report.md` | new | report |

No other file may change. No migration, no schema change.

## 4. Steps

1. `App/app/billing_jobs.py`:
   - In `_unpaid_overdue`, change the WHERE to
     `... AND i.paid_on IS NULL AND i.total_haler > 0 AND i.due_date < ? ...`
     (1867: a zero-amount invoice — 100% discount, 0 apartments — is not collectible.)
   - In `settle`, add `AND total_haler > 0` to the still-overdue query.
   - In `dunning`, `counts = {"overdue": 0, "reminded": 0, "paused": 0, "settled": 0}` and,
     just before `return counts`, add:
     ```python
     # 1867: accounts stuck 'overdue' with only zero-amount invoices left (e.g. a 100%
     # discount applied after the invoice) settle back to active on this run.
     for row in db.query(
         "SELECT owner_user_id FROM billing_account WHERE status = 'overdue' AND plan IS NOT NULL "
         "AND (? IS NULL OR owner_user_id = ?)",
         (owner_user_id, owner_user_id),
     ):
         if settle(int(row["owner_user_id"]), today=today):
             counts["settled"] += 1
     ```
2. `go/internal/billingjob/dunning.go`: `AND i.total_haler > 0` in unpaidOverdue (same comment);
   `type dunningCounts struct{ overdue, reminded, paused, settled int }`; after the mail loop,
   before `return c, nil`:
   ```go
   // 1867: accounts stuck "overdue" with only zero-amount invoices left (e.g. a 100%
   // discount applied after the invoice) settle back to active on this run.
   positive := make(map[int64]bool, len(list))
   for _, inv := range list {
       positive[inv.owner] = true
   }
   rows, err := r.Pool.Query(ctx,
       `SELECT owner_user_id FROM billing_account WHERE status = 'overdue' AND plan IS NOT NULL
          AND ($1::bigint = 0 OR owner_user_id = $1)`, r.Owner)
   if err != nil {
       return c, err
   }
   var owners []int64
   for rows.Next() {
       var o int64
       if err := rows.Scan(&o); err != nil {
           rows.Close()
           return c, err
       }
       owners = append(owners, o)
   }
   rows.Close()
   if err := rows.Err(); err != nil {
       return c, err
   }
   for _, o := range owners {
       if positive[o] {
           continue
       }
       changed, err := setStatus(ctx, r.Pool, o, "active", "system")
       if err != nil {
           return c, err
       }
       if changed {
           c.settled++
       }
   }
   ```
3. `go/internal/billingjob/run.go`: add `DunningSettled` to the Counts struct next to the other
   Dunning fields, `"dunning_settled": c.DunningSettled,` in Map, `+ c.DunningSettled` in Total,
   and `c.DunningSettled = d.settled` on the assignment line.
4. `go/internal/web/billing/payer.go`: settle still-query add `AND total_haler > 0`.
5. `App/tests/test_billing_jobs.py`: append
   ```python
   def test_zero_amount_invoice_is_never_dunned_and_a_stuck_overdue_settles(owner):
       """1867: 100% discount -> 0 Kč invoice; it is not collectible, never duned, and an
       account stuck 'overdue' only because of it settles on the next run."""
       db.execute(
           "UPDATE billing_account SET discount_percent = 100, discount_reason = 'free pilot' "
           "WHERE owner_user_id = ?",
           (owner,),
       )
       _period(owner, TODAY - timedelta(days=20), TODAY + timedelta(days=9))
       invoice_id = billing_invoices.issue_for_period(
           owner, (TODAY - timedelta(days=20)).isoformat(), (TODAY + timedelta(days=9)).isoformat(),
           today=TODAY - timedelta(days=20))
       inv = [i for i in _invoices(owner) if i["id"] == invoice_id][0]
       assert inv["total_haler"] == 0 and inv["paid_on"] is None
       db.execute("UPDATE platform_invoice SET due_date = ? WHERE id = ?",
                  ((TODAY - timedelta(days=20)).isoformat(), invoice_id))
       counts = billing_jobs.dunning(TODAY, owner)
       assert counts == {"overdue": 0, "reminded": 0, "paused": 0, "settled": 0}
       assert billing.account(owner)["status"] == "active"
       assert _kinds(owner).count("billing_overdue") == 0
       db.execute("UPDATE billing_account SET status = 'overdue' WHERE owner_user_id = ?", (owner,))
       counts = billing_jobs.dunning(TODAY, owner)
       assert counts["settled"] == 1
       assert billing.account(owner)["status"] == "active"
       db.execute("UPDATE billing_account SET status = 'overdue' WHERE owner_user_id = ?", (owner,))
       assert billing_jobs.settle(owner, today=TODAY) is True
   ```
   and fix any exact-dict count assertions (`test_nothing_runs_while_billing_is_off` expects
   `{"rolled": 0, "invoiced": 0, "apartments": 0, "errors": 0}` — it gains
   `"dunning_settled": 0` plus the other dunning/trial keys it already had; update to match
   the real keys).
6. `go/internal/billingjob/run_test.go`: extend the Counts test if it asserts Map/Total.
7. `docs/context/decisions.md`: append
   `- 2026-11-20 [billing] zero-amount invoices (100% discount, 0 apartments) are never dunned and never mark the account overdue; the daily run settles accounts whose overdue invoices are all zero | owner | 1867`
8. Run §6, write the report, set Status: review, open the PR.

## 5. Do not touch

`billing_invoices.issue()` / Go `issue()` (see §2 — reissue path depends on paid_on IS NULL),
`billing_trial.banner` / Go `billingBanner` (status-driven; the status is corrected by the run),
any migration, i18n, templates, CSS.

## 6. Commands

From `App/` (each `2>&1 | tail -30`):
- `.venv/bin/python -m pytest tests/test_billing_*.py -q --tb=short -x`
- `.venv/bin/python -m pytest tests/test_0414_billing_banner_browser.py -q --tb=short` (browser, if playwright present)
From `go/`: `go build ./... && go vet ./internal/billingjob/ ./internal/web/billing/ && go test ./internal/billingjob/... ./internal/web/billing/... 2>&1 | tail -30` (DB tests skip without UBYHOST_TEST_DATABASE_URL; CI postgres runs them)
From repo root: `python3 scripts/context_lint.py`

## 7. Acceptance

- [ ] New test passes; whole `test_billing_*.py` green.
- [ ] Go builds, vets, and non-DB tests pass; Counts Map/Total include `dunning_settled`.
- [ ] Repro from §2 now ends with status `active` and no banner line after dunning.
- [ ] `context_lint.py` OK.

## 8. Stop and ask

Stop if an excerpt is not found, a §6 command fails twice, or the Go/Python parity is unclear.

## 9. Report

`docs/tasks/1867-report.md` (≤600 tokens), Status: review, one PR from `task/1867-zero-amount-invoices`.

## Risk list (for the reviewer)

- `App/app/billing_jobs.py` and `go/internal/billingjob/dunning.go` (the dunning filter + auto-settle)
- `go/internal/web/billing/payer.go` (settle filter)

## Owner steps

1. Merge when green via `scripts/merge-pr-on-green.sh`.
2. The affected zero-cost workspace self-heals on the next 06:00 billing run; to clear it
   immediately, re-save the discount (or mark the 0 Kč invoice paid) in `/admin/customers`.
