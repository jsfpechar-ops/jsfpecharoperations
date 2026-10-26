# 0418: ČSOB statement import (B7): read the bank export, match payments to invoices

Status: todo
Depends on: 0413, 0417 | Base commit: the head of `claude/billing-phase1-impl` | Branch: task/0418-bank-import
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

UbyHost banks with ČSOB and has no bank API token. The operator downloads a statement from ČSOB internet banking (GPC/ABO or CSV) and uploads it; the admin page comes in 0419. This brief adds the module behind it, `App/app/bank_import.py`:

1. **Parse.** GPC (`074` header, one `075` line per transaction, credits only) or CSV (header found by its Czech or English column names, cp1250 or UTF-8).
2. **Match.** A payment whose variable symbol is an unpaid invoice's VS:
   - the exact amount marks the invoice paid (`bank_auto`);
   - more than the amount is `overpaid` and also marks it paid;
   - less is `partial` and waits for the operator.

   Any other payment is `unmatched`.
3. **Settle.** A paid invoice calls `billing_jobs.settle()`, so an overdue or read-only account opens again.
4. **Repeats.** The same statement uploaded twice records nothing new (`bank_tx_id` is the key).
5. **By hand.** `mark_paid_manually()` is the operator's "Označit jako zaplaceno".

No outbound request, no new dependency, no schema change (`bank_payment` exists since 0411).

## 2. Context

Both files are finished in `docs/plans/billing-0418/`. You copy them and run the tests. Nothing else changes.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/bank_import.py` | create | copy of `docs/plans/billing-0418/bank_import.py` |
| `App/tests/test_bank_import.py` | create | copy of `docs/plans/billing-0418/test_bank_import.py` |
| `docs/tasks/0418-report.md` | create | the report |

## 4. Steps

### Step 1. Copy (from the repo root)

```bash
cp docs/plans/billing-0418/bank_import.py App/app/bank_import.py
cp docs/plans/billing-0418/test_bank_import.py App/tests/test_bank_import.py
```

### Step 2. Run §6, write the report, `Status: review`, commit.

## 5. Do not touch

Everything else, in particular `billing.py`, `billing_invoices.py`, `billing_jobs.py`, `reporting.py`, migrations.

## 6. Commands

From `App/`:

1. `.venv/bin/python -m pytest tests/test_bank_import.py tests/test_billing_jobs.py tests/test_billing_invoices.py -q --tb=short -x 2>&1 | tail -30`
2. `.venv/bin/python -m pytest tests/test_privacy_first.py tests/test_retention_alignment.py -q --tb=short 2>&1 | tail -30` (if a file does not exist, `ls tests | grep -i retention | tail -30` and run those instead)

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`

## 7. Acceptance

- [ ] All commands pass.
- [ ] `git diff --stat` shows only the §3 files.

## 8. Stop and ask

- A copied test fails twice: report the assertion and the last 30 lines. One obvious typo fix in a copied file is allowed; name it under Deviations.

## 9. Report

`docs/tasks/0418-report.md`: files changed, the last 5 lines of each command, §7 ticked, Deviations, Questions.

## Risk list (for the reviewer)

- The CSV column names are a guess at ČSOB's export; the owner sends one real file (account numbers blurred) to confirm before launch. GPC is the documented ABO layout.
- A payment for an invoice that is already paid is `unmatched`: the operator refunds or credits it by hand.
- A partial payment never marks the invoice paid; the operator decides (mark paid by hand, or wait for the rest).
