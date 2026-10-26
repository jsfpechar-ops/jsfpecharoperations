# 0420: Paid plans in the Terms and Privacy; ČSOB import fitted to the real export (B10)

Status: todo
Depends on: 0418, 0419 | Base commit: the head of `claude/billing-phase1-impl` | Branch: task/0420-billing-legal-csob
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

1. **Legal copy (owner decision, 2026-10-26).** The owner acts as counsel and approved the text in `docs/privacy/drafts/billing-terms.md`. No hosts are on the platform officially, so it joins the pending 1.7 release with no extra notice and no version bump.
   - Terms § 15 (EN and CS) is replaced with the paid-plan text, and the CS title becomes "15. Ceny a platby".
   - Privacy § 11 (EN and CS) gains one sentence: invoices and their payments are kept for 10 years, and billing details are shared with the accountant.
2. **ČSOB import.** The owner sent a real ČSOB CSV export. The parser already reads it; this brief makes two changes:
   - The counter-account now includes its bank code, taken from the separate "kód banky protiúčtu" column (`1234567890/0800`).
   - A credit whose variable symbol cannot be a UbyHost invoice (Booking.com payouts, card refunds, tax refunds) is skipped and **not stored**. Before, it filled "Payments to sort out" with the operator's private income. The import counts these as `ignored`, and the admin flash text says so.

## 2. Context

All new code is finished in `docs/plans/billing-0420/`. You copy two files and run one script.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/bank_import.py` | replace | copy of `docs/plans/billing-0420/bank_import.py` |
| `App/tests/test_bank_import.py` | replace | copy of `docs/plans/billing-0420/test_bank_import.py` |
| `App/app/terms_i18n.py` | edit (script) | § 15 EN + CS |
| `App/app/privacy_policy_i18n.py` | edit (script) | § 11 EN + CS |
| `App/app/host_i18n.py` | edit (script) | `billing.admin.statement.done` EN + CS |
| `docs/tasks/0420-report.md` | create | the report |

## 4. Steps

### Step 1. Copy (from the repo root)

```bash
cp docs/plans/billing-0420/bank_import.py App/app/bank_import.py
cp docs/plans/billing-0420/test_bank_import.py App/tests/test_bank_import.py
```

### Step 2. Legal copy and flash text (from the repo root)

`python3 docs/plans/billing-0420/apply_legal.py 2>&1 | tail -3`. Expected: `terms § 15 EN+CS, privacy § 11 EN+CS, 2 flash texts: done`. An `AssertionError` means an anchor moved: STOP (§8).

### Step 3. Run §6, write the report, `Status: review`, commit.

## 5. Do not touch

Legal versions in `config.py`, `docs/privacy/drafts/`, templates, CSS, `reporting.py`, migrations. Never add a real bank statement to the repository.

## 6. Commands

From `App/`:

1. `.venv/bin/python -m pytest tests/test_bank_import.py tests/test_billing_admin.py tests/test_billing_invoices.py -q --tb=short -x 2>&1 | tail -30`
2. `.venv/bin/python -m pytest tests -q --tb=short -p no:randomly -k "terms or privacy or legal or retention" 2>&1 | tail -30`

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`, and `cd App && .venv/bin/python -m ruff check app tests tools --select E9,F63,F7,F82,F401,F841 2>&1 | tail -5`.

## 7. Acceptance

- [ ] All commands pass.
- [ ] `git diff --stat` shows only the §3 files.

## 8. Stop and ask

- The script's assertion fails, or a copied test fails twice: report the message and the last 30 lines.

## 9. Report

`docs/tasks/0420-report.md`: files changed, the last 5 lines of each command, §7 ticked, Deviations, Questions.

## Risk list (for the reviewer)

- A real payment with a mistyped VS (not 8 digits starting `20`) is skipped. The operator finds it in the bank and marks the invoice paid by hand.
- GPC lines carry no separate bank code field the parser reads, so GPC counter-accounts stay without `/bank`.
