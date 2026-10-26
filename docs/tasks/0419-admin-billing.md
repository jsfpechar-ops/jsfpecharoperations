# 0419: Operator billing page (B9): /admin/fakturace, statement upload, accountant export

Status: todo
Depends on: 0413, 0417, 0418 | Base commit: the head of `claude/billing-phase1-impl` | Branch: task/0419-admin-billing
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

An admin-only page `/admin/fakturace` (Czech URL, like `/predplatne`) for the operator:

- **Accounts.** The count per billing status and the unpaid total.
- **Unpaid invoices.** Each row has a PDF link, "Označit jako zaplaceno" with a date, and a storno with a reason. A paid invoice cannot be cancelled. The storno is not mailed, because the invoice mail asks for payment; the host sees it on `/predplatne`.
- **Bank statement.** Upload a ČSOB GPC or CSV file; `bank_import.import_statement` matches it.
- **Payments to sort out.** Unmatched, partial and overpaid payments.
- **Invoices by month.** A month picker, the month's list, and "Stáhnout pro účetní": a ZIP with a CSV (semicolons, BOM, Czech headers) and every stored PDF. The owner's accountant agreed to CSV + PDF.

A host gets 403 on every URL. Everything works without JavaScript. No new dependency (`zipfile` and `csv` are stdlib), no schema change, no outbound request.

## 2. Context

You copy finished files from `docs/plans/billing-0419/` and make small anchored edits.

**Excerpt A**, `App/app/main.py`: in the import line on line 32, the text `, billing as billing_routes,`; and the line `app.include_router(billing_routes.router)`.

**Excerpt B**, `App/app/templating.py`:

```python
    if nav in ("settings", "privacy_requests", "users", "incidents", "operations", "funnel"):
```

**Excerpt C**, `App/app/templates/_shell_sidebar.html`:

```
        <a href="/admin/funnel">{{ t('funnel.title') }}</a>
```

**Excerpt D**, `App/app/host_i18n.py`: `"mail.billing_overdue.action": "Open your plan",` and `"mail.billing_overdue.action": "Otevřít předplatné",` (from 0417; `insert_keys.py` checks them).

If any excerpt is not found verbatim and once, STOP (§8).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/billing_admin.py` | create | copy of `docs/plans/billing-0419/billing_admin.py` |
| `App/app/routes/admin_billing.py` | create | copy of `docs/plans/billing-0419/admin_billing_routes.py` |
| `App/app/templates/admin_billing.html` | create | copy |
| `App/app/main.py` | edit | register the router |
| `App/app/templating.py` | edit | settings tabs on the page |
| `App/app/templates/_shell_sidebar.html` | edit | admin menu link |
| `App/app/host_i18n.py` | edit | 46 keys EN, 46 keys CS (script) |
| `App/tests/test_billing_admin.py` | create | copy |
| `App/tests/test_0419_admin_billing_browser.py` | create | copy |
| `docs/tasks/screenshots-0419/` | create | one screenshot |
| `docs/tasks/0419-report.md` | create | the report |

## 4. Steps

### Step 1. Copy (from the repo root)

```bash
cp docs/plans/billing-0419/billing_admin.py App/app/billing_admin.py
cp docs/plans/billing-0419/admin_billing_routes.py App/app/routes/admin_billing.py
cp docs/plans/billing-0419/admin_billing.html App/app/templates/admin_billing.html
cp docs/plans/billing-0419/test_billing_admin.py App/tests/test_billing_admin.py
cp docs/plans/billing-0419/test_0419_admin_billing_browser.py App/tests/test_0419_admin_billing_browser.py
```

### Step 2. `main.py`

In Excerpt A's import line replace `, billing as billing_routes,` with `, billing as billing_routes, admin_billing as admin_billing_routes,`. After `app.include_router(billing_routes.router)` add the line `app.include_router(admin_billing_routes.router)`.

### Step 3. `templating.py` and the sidebar

3a. In Excerpt B replace `"funnel")` with `"funnel", "billing_admin")`.

3b. After Excerpt C add the line `        <a href="/admin/fakturace">{{ t('billing.admin.title') }}</a>` (same indentation).

### Step 4. Copy keys

From the repo root: `python3 docs/plans/billing-0419/insert_keys.py 2>&1 | tail -3`. Expected: `inserted 46 EN and 46 CS keys`.

### Step 5. Run §6, look at the screenshot once, write the report, `Status: review`, commit.

## 5. Do not touch

`billing.py`, `billing_invoices.py`, `billing_jobs.py`, `bank_import.py`, `reporting.py`, any CSS or JS, migrations.

## 6. Commands

From `App/`:

1. `.venv/bin/python -m pytest tests/test_billing_admin.py tests/test_bank_import.py tests/test_billing_invoices.py tests/test_billing_order.py -q --tb=short -x 2>&1 | tail -30`
2. `.venv/bin/python -m pytest tests/test_design_tokens.py tests/test_privacy_first.py tests/test_dev_ui.py tests/test_host_i18n.py -q --tb=short 2>&1 | tail -30` (test_host_i18n.py has 3 known failures, "no such table: apartment" / Vietnamese language tests; anything else is yours)
3. `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_CAPTURE_0419=1 .venv/bin/python -m pytest tests/test_0419_admin_billing_browser.py tests/test_0416_plan_page_browser.py -q -rs --tb=short -x 2>&1 | tail -30` (0 skipped)

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`. After the runs, `git checkout -- docs/tasks/screenshots-0*` for any screenshot folder other than `screenshots-0419` that changed.

## 7. Acceptance

- [ ] All commands pass, 0 skipped in the browser run.
- [ ] `docs/tasks/screenshots-0419/admin-fakturace-390.png` exists; nothing scrolls sideways.
- [ ] `git diff --stat` shows only the §3 files.

## 8. Stop and ask

- An excerpt is not found once.
- A copied test fails twice: report the assertion and the last 30 lines. One obvious typo fix in a copied file is allowed; name it under Deviations.
- A design test fails on `admin_billing.html`: report it, do not add CSS.

## 9. Report

`docs/tasks/0419-report.md`: files changed, the last 5 lines of each command, §7 ticked, Deviations, Questions.

## Risk list (for the reviewer)

- The ZIP is built in memory; fine for 100 customers (a month is a few MB of PDFs).
- A storno is not mailed to the host; the operator tells them if needed.
- The month input is a native `type="month"` field; on desktop Firefox it shows as a text field that still takes `2026-10`.
