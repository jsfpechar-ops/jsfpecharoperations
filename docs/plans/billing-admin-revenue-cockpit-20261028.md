# Billing admin: from invoice list to a revenue cockpit

Status: draft plan for owner review. Written 2026-10-28 after reviewing `/admin/fakturace` (brief 0419), `billing.py`, `billing_admin.py`, `admin_customers.py`, migration 0023.
Risk: MEDIUM (money math, one migration, admin-only UI). Owner: Josef.

## 0. Read this first

The page in the screenshot is an **accounts-payable tool**: it answers "which of MY invoices are unpaid, what did the bank send me, what goes to the accountant." That is correct and it is done. What it does not answer — and what an operator actually running a SaaS needs every morning — are the **CRM and revenue questions**:

- Who are my users, what does each one pay me, and what do I collect in total? (MRR/ARR, per plan, per interval)
- Who has a price I set by hand (founder, agreed discount) and how much am I giving away?
- Who is about to upgrade/downgrade, and what does that do to the next invoice and to my MRR?
- Who is quietly dying (trial ending, overdue, ends with this period) so I can act before the money is lost?

Nothing on `/admin/fakturace` answers those today. `/admin/customers` answers "who exists" but shows no amounts. The plan below builds the missing layer **on top of** the existing `billing_account` / `platform_invoice` / `bank_payment` model — no re-pricing, no gateway, no change to what hosts see.

## 1. What exists today (verified in code)

| Need | Today | Verdict |
|---|---|---|
| My unpaid invoices, bank statement import, mark paid, storno, accountant ZIP | `/admin/fakturace` (0419) | done, keep as-is |
| Customer list with billing status, plan, trial, period | `/admin/customers` (admin_customers.py) | has "who", missing "how much" |
| Pricing engine | `billing.quote()` — graduated bands, Standard/Max, month/year, TTLock add-on, founder price | works, is the single source of truth |
| Hand-set prices | only `founder` flag (locked price) + `carry_czk` rounding remainder | **no general discount exists** |
| Upgrade/downgrade | `billing.apply_change()` with preview: `now` vs `next_period`, supplementary invoice vs carry; host self-service on `/predplatne` | works, invisible to the operator |
| One change at a time, CHANGE_COLUMNS whitelist, status machine | `billing.py` TRANSITIONS | works; operator has no way to drive it for a customer |

## 2. Design principles (UX + accounting)

1. **One page, four questions.** Money in (MRR/ARR), money owed (receivables), money at risk (churn watchlist), money per customer (drill-down). The current sections stay but drop below the new top layer.
2. **Never two sources of amounts.** Every crown shown is either read from `platform_invoice.total_haler` (billed/paid) or computed by `billing.quote()` (recurring). No hand-typed numbers anywhere in the UI.
3. **Accounting hygiene.** Recurring (MRR) and invoiced (cash/accrual) are always shown as *separate* figures with separate labels — MRR is a run rate, invoices are booked revenue. Discounts appear as "list price − discount = net" on every surface where a price is touched, so the discount is auditable and visible on the invoice itself (Czech practice: a discount is printed on the invoice, not silently netted).
4. **CRM safety.** Every operator action on a customer's money (discount, upgrade, downgrade, pause) is a plain form post with a preview ("what happens, when, what amount"), writes a `db.audit` row with the acting operator, and reuses `billing.apply_change` — no new mutation paths parallel to the host self-service flow.
5. **Light mode, works without JavaScript**, existing `ui_*` components, 390 px screenshot per changed page (repo rule 7).

## 3. The target page (top layer of `/admin/fakturace`)

**A. Revenue snapshot** (new, replaces the bare status string)
- `MRR` — sum of normalized monthly net across `active`/`overdue`/`canceling` accounts (yearly ÷ 12), split Standard / Max, month vs year interval.
- `ARR` = MRR × 12, shown once as a sub-figure.
- `Billed this month` (from `platform_invoice`, issue month, excluding storno) and `Collected this month` (paid_in month). Distinct labels, never summed together.
- `Unpaid total` (exists) + `Overdue total` (subset, due date < today) + worst debtor age.

**B. Portfolio table: "What users, how much"** (new section "Customers / Zákazníci")
One row per `billing_account` with a plan, columns: customer (link to `/admin/customers/{id}`), status badge, plan + interval, apartments billed, list price, discount (badge if any), **net period price**, period end, next pending change (e.g. "→ Standard on 2026-12-01", from `pending_change_json`), carry, unpaid amount for that customer, and "Trial ends in N days" for trials. Sortable by net price; filter by status/plan (reuse the `/admin/customers` filter vocabulary; aggregate sums only — never materialize the full table in Python, same rule as admin_customers.py).

**C. Churn & growth watchlist** (new)
Three short lists, max ~10 rows, each with one action: trials ending ≤ 7 days, invoices overdue (days late), accounts `canceling`/`ends with this period`. Purpose: the operator opens the page and knows whom to call today.

**D. Money at a discount** (new, small)
Total MRR given away through founder prices and discounts: list price sum, net sum, difference — and the list of customers who have one. This is the number an accountant asks for when pricing is reviewed.

**E. Existing sections** (statement upload, payments to sort, month browser + export) stay below, unchanged in behavior; only visual reordering.

## 4. Per-customer money view (`/admin/customers/{id}`)

Extend `admin_customers.detail()` (read-only today — keep that boundary for the *view*, add separate *action* posts):
- Money card: current plan, interval, apartments, list price, discount (reason + amount), net, period start/end, carry.
- Lifecycle: trial dates, pending change with the same wording the host sees, cancel-at-period-end.
- Invoice history: extend from 10 rows to a full list with totals (billed / paid / unpaid / voided).

## 5. Operator actions (the CRM part)

All admin-only, all plain form posts, all previewed before confirmation, all audited:

| Action | Where | How |
|---|---|---|
| Set / change / remove a discount | customer detail | new migration column `discount_percent` (whole percent, 0–100) + `discount_reason` (short text). Applied inside `billing.quote()` so *every* surface (host plan page, next invoice, MRR) uses the same number. Printed on the invoice as "sleva X % (reason)". |
| Upgrade / downgrade / interval / add-ons for a customer | customer detail | a form that calls `billing.apply_change(..., actor='operator:<username>')`. The operator sees the same preview the host would: when it takes effect, supplementary invoice or carry, and the resulting period price. The host is not mailed on downgrade; the change shows on `/predplatne`. |
| Pause / resume / status change | customer detail | `billing.set_status` with the existing TRANSITIONS machine — no new states, no bypassing it. |
| Adjust a billed amount | only where it already exists: storno + reissue. No free-text amount editing of a booked invoice (accounting integrity). An admin-set discount changes *future* invoices; correcting a booked one stays storno-first. |

**Decision needed from owner (blocker for §5):** does a discount ever apply to an already-issued but unpaid invoice (reissue with discount), or only from the next invoice? Recommend: only the next invoice; storno already covers the rare correction.

## 6. Data model

One migration (`App/app/migrations/00XX_billing_discount.sql`):
- `billing_account.discount_percent INTEGER NOT NULL DEFAULT 0 CHECK (0..100)`
- `billing_account.discount_reason TEXT` — shown on invoices; retention line in `retention.py` (personal data? reason is business info, stays with the row's existing retention).
- No new tables. `snapshot_json` already prints items, so the discount shows on new invoices automatically once `quote()` applies it.

## 7. Briefs (order)

- **0440 Revenue snapshot + portfolio table** (§3 A+B): `billing_admin.py` new aggregate queries (SQL-side sums), template sections, i18n cs/en/vi/uk. Tests: test-map rows 11 + 32 + browser/geometry for the changed page.
- **0441 Watchlists** (§3 C+D): pure queries over existing columns.
- **0442 Customer money view** (§4): extend `admin_customers.detail()` + template.
- **0443 Discount** (§5 + §6): migration, `quote()` change, invoice line, operator form. **Blocked on the §5 owner decision.**
- **0444 Operator plan changes** (§5 row 2–3): forms over `apply_change`/`set_status`, preview rendering.

0440–0442 are safe to run in sequence after approval; 0443–0444 after the decision.

## 8. Do not touch

- Pricing numbers in `billing.py` (PRICE tables) — reporting and discounts only.
- Host self-service flow (`billing_order.py`) — the operator path mirrors it, never diverges.
- Bank import / paid-matching / export ZIP logic.
- The status machine (TRANSITIONS).

## 9. Acceptance (per brief, checked on staging)

- [ ] `/admin/fakturace` answers, in one screen: total MRR, who pays what (top list), who is at risk, who has a discount.
- [ ] MRR figure matches a manual `SUM` over `billing_account` recomputed via `billing.quote()` in a REPL check (document the command in the brief).
- [ ] Discount math visible: list − discount = net on the host plan page, the invoice PDF, and the operator table.
- [ ] Every operator money action produces a `db.audit` row with the operator's username.
- [ ] 390 px screenshots of the changed pages; browser/geometry rows 0 skipped.
