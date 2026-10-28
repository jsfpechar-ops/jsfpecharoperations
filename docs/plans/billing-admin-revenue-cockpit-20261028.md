# Billing admin: from invoice list to a revenue cockpit

Status: draft v2 for owner review. Written 2026-10-28 after reviewing `/admin/fakturace` (brief 0419), `billing.py`, `billing_admin.py`, `admin_customers.py`, migration 0023.
Owner decisions made 2026-10-28: **(D1) yes, a discount applies to already-issued unpaid invoices — the invoice is reissued with the discount;** (D2) the target is a corporate-level system: the operator must be able to *see everything, analyse it, and edit what needs to be done* — an executive cockpit, not a lean page. v2 adds §3 analytics layer, §5 expanded actions, §11 execution notes.
Risk: MEDIUM (money math, migrations, admin-only UI). Owner: Josef.

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

## 3. The target pages (corporate layer)

Corporate system layout: one cockpit page plus one customer money page. Everything is visible in at most two hops; every figure is clickable down to the customers behind it.

**A. Revenue snapshot (cockpit top)** — MRR (monthly-normalized, split month/year interval, Standard/Max), ARR, billed vs collected this month (separate figures), unpaid total, overdue total, worst debtor age, discount giveaway total, net revenue vs list revenue. **Trend row:** last 12 months of MRR, billed and collected as a CSS bar strip (no JS, no chart library — the repo has none and rules forbid new dependencies without a decision).

**B. Movement (the accountant's waterfall)** — month-over-month MRR change decomposed into: new business, expansion (upgrades, more apartments), contraction (downgrades), reactivation, churn (canceling/paused leaving), discount effect. Computed by diffing consecutive months' snapshot (see §6 `billing_month_snapshot`). Each line links to the customers who caused it.

**C. Portfolio table: "What users, how much"** (new section "Customers / Zákazníci")
One row per `billing_account` with a plan, columns: customer (link to `/admin/customers/{id}`), status badge, plan + interval, apartments billed, list price, discount (badge if any), **net period price**, period end, next pending change (e.g. "→ Standard on 2026-12-01", from `pending_change_json`), carry, unpaid amount for that customer, and "Trial ends in N days" for trials. Sortable by net price; filter by status/plan; **the whole table is editable** (see §5): inline per-row action menu (open, discount, change plan, status). Aggregate sums only — never materialize the full table in Python, same rule as admin_customers.py. CSV export of the current view.

**D. Churn & growth watchlist** — trials ending ≤ 7 days, invoices overdue (days late), accounts `canceling`/`ends with this period`, payments unmatched > 7 days, and a **forecast block**: expected collections next 30 days (open invoices by due date) and projected MRR next period (active net + pending changes − scheduled cancellations).

**E. Money at a discount** — list revenue, net revenue, giveaway; per-customer breakdown with reason and who set it.

**F. Receivables aging** — buckets 0–7, 8–30, 31–90, 90+ days past due, per customer drill-down; reconciled against §A's unpaid total.

**G. Trial funnel** — signups → verified → trial started → trial ended → converted to paid, with conversion rate; monthly cohorts with retention over months 1–6.

**H. Existing sections** (statement upload, payments to sort, month browser + export) stay below, unchanged in behavior; only visual reordering.

### The target page (original v1 scope, kept as §3 core)

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

**D1 answered — discounts apply to unpaid invoices.** When an operator sets a discount while the customer has an issued, unpaid, non-voided invoice, the flow is: automatic storno of that invoice (reason: "discount", operator name) → reissue for the same period with the discount applied → the *new* number and VS are what the host sees and pays. Rules:
- Only `kind='invoice'`, `voided=0`, `paid_on IS NULL` invoices are reissued; paid/voided/supplementary invoices are never touched (booked revenue is immutable; a discount reaching a paid invoice becomes a credit note — out of scope, owner can storno manually if ever needed).
- Any paid amount already matched to the old invoice is carried to the new one by the existing bank-matching logic (VS-based), so no double payment.
- The reissue is one atomic transaction with an audit row; the host is not mailed again (the storno notice already exists on `/predplatne`).
- Both numbers stay in history: storno and reissue are two rows, so the accounting trail is complete.

## 6. Data model

Migrations (`App/app/migrations/`):
- `billing_account.discount_percent INTEGER NOT NULL DEFAULT 0 CHECK (0..100)`, `billing_account.discount_reason TEXT` (business info, follows the row's retention; `retention.py` line added).
- `billing_month_snapshot` table: one row per (month, owner_user_id) with plan, interval, apartments, addons, discount, net monthly-normalized price, status — written by the scheduler at each month close and at any `apply_change`/discount mutation for the current month. This is what makes §3 B (movement), §3 G (cohorts) and the trend row possible without recomputing history, and it gives the accountant a monthly audit of what each customer was on.
- No other new tables. `snapshot_json` already prints items, so the discount shows on new invoices automatically once `quote()` applies it.

## 6a. "Everything editable" — the corporate edit surface

The user wants to operate, not only watch. Every editable field routes through one guarded path:

| What the operator edits | Path | Guard |
|---|---|---|
| Discount % + reason | new form → `billing.apply_discount()` → reissue-if-unpaid per D1 | 0–100, reason required ≥ 0 %, audit row with operator username |
| Plan (Standard↔Max), interval, apartments, add-ons | `billing.apply_change(..., actor='operator:<username>')` | CHANGE_COLUMNS whitelist, one at a time, preview shown before confirm |
| Status (pause/resume/cancel/resume-from-cancel) | `billing.set_status` | existing TRANSITIONS machine, no bypass |
| Unpaid invoice: mark paid / storno | existing routes | unchanged |
| Unmatched bank payment | existing decision flow | unchanged |

No free-text editing of booked invoice amounts, no editing of paid history — corrections go storno-first (accounting integrity, unchanged rule). Every edit shows a preview: what changes, when it takes effect, which invoice is reissued for how much, what the new MRR is.

## 6b. Analysis surface

- Every number in §3 is a link to the filtered portfolio table behind it (e.g. click MRR of Max-year → customers with that plan+interval).
- Month selector (existing `mesic` param) drives §3 A/B/F/G for the chosen month; trend row always shows ±12 months.
- CSV exports: portfolio view, movement month, aging, funnel. Same data as the screen, no new export pipeline beyond a CSV response per table (accountant's ZIP untouched).
- No JS charts: CSS bars, tables, badges from the existing `ui_*` kit; works without JavaScript (rule 6).

## 7. Briefs (order)

- **0440 Revenue snapshot + portfolio table** (§3 A core + C, CSV export): `billing_admin.py` aggregate queries (SQL-side sums), template sections, i18n cs/en/vi/uk. Tests: test-map rows 11 + 32 + browser/geometry for the changed page.
- **0441 Watchlists + forecast + aging** (§3 D + F).
- **0442 Customer money view + edit forms** (§4 + §6a rows 2–3): the operator can change plan/interval/add-ons/status from the customer page with previews.
- **0443 Discount + reissue** (§5 + §6 + D1): migration, `quote()` change, invoice line, operator form, storno+reissue of unpaid invoices. D1 decided — no longer blocked.
- **0444 Movement, funnel, trend, monthly snapshot** (§3 B + G + §6 `billing_month_snapshot`, scheduler hook).
- **0445 Click-through + CSV everywhere** (§6b): every figure links to its filtered table; movement/aging/funnel CSV.

0440–0442 safe to run in sequence after approval; 0443–0445 follow. Each brief fits one Haiku session.

## 8. Do not touch

- Pricing numbers in `billing.py` (PRICE tables) — reporting and discounts only.
- Host self-service flow (`billing_order.py`) — the operator path mirrors it, never diverges.
- Bank import / paid-matching / export ZIP logic.
- The status machine (TRANSITIONS).

## 9. Acceptance (per brief, checked on staging)

- [ ] `/admin/fakturace` answers, in one screen: total MRR, who pays what (top list), who is at risk, who has a discount, expected collections next 30 days.
- [ ] MRR figure matches a manual `SUM` over `billing_account` recomputed via `billing.quote()` in a REPL check (document the command in the brief).
- [ ] Movement decomposition for a test month sums to the total MRR change.
- [ ] Aging buckets sum to the unpaid total shown in §A.
- [ ] Discount math visible: list − discount = net on the host plan page, the invoice PDF, and the operator table.
- [ ] D1 flow: discount on an account with an unpaid invoice → old invoice voided, new one issued with the discount, host sees only the new number, matched payments carry over.
- [ ] Every operator money action produces a `db.audit` row with the operator's username.
- [ ] Every §3 figure links to its filtered customer table; CSV downloads open in a spreadsheet.
- [ ] 390 px screenshots of the changed pages; browser/geometry rows 0 skipped.

## 11. Execution notes (for the briefs)

- All new queries live in `billing_admin.py` (operator finance) or `admin_customers.py` (CRM detail); routes stay thin. SQL only through `db.py` helpers, Postgres-portable.
- New personal-data-adjacent fields (`discount_reason`, snapshot rows): add the `retention.py` line in the same brief (rule 2).
- i18n: every new label goes into `host_i18n.py` for cs/en/vi/uk in the same brief.
- The cockpit page must stay usable with hundreds of accounts: SQL aggregates, LIMIT + seek pagination on the portfolio table (reuse the admin_customers cursor pattern), never a full-table render.
- No new dependencies: CSS bars only. If a real chart is ever wanted, that is an owner decision line in decisions.md.
- Complexity control: the cockpit grows in briefs; each brief ships a page that is complete without the later ones.
