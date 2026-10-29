# Admin operations & billing: UbyHost operator console

Status: **draft for owner approval** — nothing below is built yet.

Source studies (bounded, this session):
- **InvoiceNinja** (open source, license-clean): read the actual schema/model code
  (`app/Models/Invoice.php`, `RecurringInvoice.php`, `Subscription.php`,
  `CompanyUser.php`, `Webhook.php`, `app/Jobs/Cron/*`). What matters extracted;
  what does not, explicitly dropped.
- **Frontegg** (closed-source SaaS): no reverse engineering — its own terms limit
  REA to software you own or are authorized to examine, and everything that
  matters is public documentation. Extracted the *concept model* only:
  RBAC, entitlements (subscription-linked access), self-service admin portal,
  audit trail. No Frontegg code, no service integration — UbyHost stays
  self-hosted (privacy-first rule).

## 1. What this workstream is

One admin console where the owner (the only admin user today) runs the whole
customer lifecycle, on data UbyHost already stores. It extends the shipped
`/admin/customers` + `/admin/fakturace` surface — it does not replace it, and
it does not touch host or guest pages.

### What exists already (verified against the code — do not rebuild)

| Capability | Where it lives today | Gaps left for this plan |
|---|---|---|
| Dunning (reminders) | `billing_jobs.dunning()`, daily 06:00 job: reminder at due+1, second at due+7, status→`overdue`, read-only pause at due+14; one mail per stage, idempotent via `billing_overdue()` | **None.** Due+3/10/20 in the first draft was wrong — 0417 already shipped due+1/+7/pause-14. Reminder days are tunable constants (`billing_jobs.py:18`), not new code |
| Overdue as derived state | `billing_jobs._unpaid_overdue()` computes from `due_date`/`paid_on`/`voided`; the cockpit derives its watchlists the same way | None — pattern is already InvoiceNinja-grade |
| Recurring generation | `billing_jobs.run()` issues per-period invoices daily; `place`/`change` pro-rate annual | None |
| Activate/deactivate users | `/admin/users/{id}/toggle` in `admin_accounts.py:872` — audited, bumps `session_version` (kills sessions), self-disable blocked | **Surface only:** no one-click action on the customer page; the toggle exists under account support |
| Admin preview | PR #280: full workspace, reason, 24 h, audited (`admin_accounts.py:333`) | **Surface only:** not linked from the customer detail |
| Keyset pagination + search + states | `admin_customers.py` (25-row keyset, literal search, 9 states) | None |
| Snapshot/cockpit | `billing_analytics` + `billing_month_snapshot` daily 06:15 | Reuse as the queue's data source |
| Audit trail | `audit` table, every billing/0448 action writes it | Surface it on the customer detail |

### The actual gaps (what this plan builds)

1. **Payment-received host mail**: marking paid (bank match or operator) is
   silent to the host — `settle()` flips status but sends nothing.
2. **Customer-page action surface**: the operator jumps between /admin/users
   and /admin/customers/{id} to do one user's work. The actions exist; they
   need one surface with audit visible.
3. **The combined queue**: billing state (cockpit) and user state (accounts)
   are on different pages; nothing tells the operator *what needs attention
   today* without opening pages.
4. **Verification resend**: unverified signups rely on the signup mail only.
5. **Enterprise-readiness hardening** (see §4): the one schema-level gap that
   would otherwise need rework at scale.

## 2. What matters from each source (and what we drop)

### From InvoiceNinja — keep
| Concept | Their shape | UbyHost mapping |
|---|---|---|
| Overdue is derived | `STATUS_OVERDUE = -1` computed from due_date vs now, never stored | Same rule in a query helper; the stored status stays (no new migration for this) |
| Reminder ladder | `reminder1_sent..reminder3_sent` + `UpdateReminders` job driven by per-company settings | `invoice_reminder` schedule: D+N from due date per invoice, max 3, capped mail kinds — reuse `mail.enqueue` idempotency |
| Recurring engine | `RecurringInvoicesCron` generates dated invoices from a frequency template | We already issue per-period; add the **scheduler hook** that fires it on `period_end` (today it's implicit) |
| Auto-bill | `AutoBillCron` + `auto_bill` (off/always/optin) | Out of scope until a card rail exists (0410/#517); keep the field decision parked |
| Webhooks | `Webhook` table, typed events | Not needed — one admin, in-app notifications suffice; revisit if an integration asks |
| Credits | `Credit` model applied to invoices | Founder-price/discount already covers the need (0448 decisions); drop |
| Quotes, projects, tasks, vendors, expenses | half the app | Not UbyHost's product. Drop entirely |

### From Frontegg — keep (concept only)
| Concept | Their shape | UbyHost mapping |
|---|---|---|
| Entitlements = access from subscription state | feature access derived from the plan, not a separate flag wall | Already true: `billing.account()` + plan gate the paid features; extend the pattern to new features via one helper, not scattered checks |
| Admin portal for end-customers | users manage their own team | Out of scope: hosts are single-owner workspaces today. Drop until multi-user hosts exist |
| RBAC granularity | per-user permission JSON | One admin (the owner). We add **operator actions with audit**, not roles. A second admin can reuse `role='admin'`; no permission matrix |
| Audit trail | every admin action logged | We have the `audit` table; this plan ensures every new operator action writes it (0448 already does) |
| User lifecycle (invite, deactivate, impersonate) | core CIAM | The "sort out my users" slice: activate/deactivate, verification resend, **admin preview-as-user with an audited, expiring session** (we already have admin preview per PR #280 — extend it) |

## 3. What we build (build order)

### Slice A — close the billing mail gaps
1. **Payment-received mail** (`billing_jobs.settle()` hook + `mail_notify.build_billing_paid()`): plain Czech "Faktura VS… byla zaplacena, děkujeme" on bank match and operator mark-paid; sent to **both** the invoice buyer e-mail and the account e-mail (owner decision §7.2; one copy when identical); idempotent per invoice. Nothing else — dunning exists (0417), do not touch its schedule.

### Slice B — one user-action surface ("sort out my users")
3. `/admin/customers/{id}` operator card: **activate/deactivate via the existing `/admin/users/{id}/toggle` route** (link/form, no new logic), resend verification (reuse the existing token flow), and the existing account-support link — POST + CSRF as 0448 did. New *surface*, not new *actions*.
4. Admin preview (PR #280's flow) linked from the customer detail; the audit trail card shows recent operator actions for this user (last 20, bounded) — including the toggle the surface uses, so every action stays auditable.
5. Per-user activity card: last logins, last mails, billing events — all from existing tables, bounded to the latest 20 rows.

### Slice C — the combined console ("billing + operations in one place")
6. `/admin` home for the admin role: today's snapshot cards (MRR, overdue count,
   trials ending — the cockpit queries reused), plus an **operations queue**:
   overdue invoices needing a reminder, unverified signups, expiring trials,
   unresolved support alerts. Each links to the existing page for the action.
   No new queries — the cockpit's snapshot job (06:15) feeds it.
7. Daily operator digest mail (one mail to the admin, 06:30): the same queue,
   plain Czech, zero if nothing needs attention.

## 4. Scalability at enterprise level (decisions now so nothing is reworked later)

The owner's constraint: build so nothing must change at enterprise scale.
Three structural rules, applied from brief 1:

1. **Every new list is keyset-paginated with a covering index.** The existing
   pages already follow this (`admin_customers.py`); the queue cards and audit
   card inherit the pattern: `ORDER BY id` seeks, `LIMIT` bounded, and new
   indexes added in the brief's migration (e.g. `platform_invoice (paid_on,
   due_date)` partial-style via `WHERE kind` for the queue's "unpaid overdue"
   query — today only `idx_platform_invoice_owner` exists).
2. **No table scans in request paths.** The /admin queue reads the 06:15
   `billing_month_snapshot` plus bounded per-card queries (each `LIMIT ≤ 25`);
   counts come from the snapshot, not live aggregates. The digest (0443) uses
   the same functions the page uses — one code path.
3. **Idempotency keys everywhere a mail or status change fires** (`billing_overdue`
   already does this). Payment-received mail: `billing_paid:{invoice_id}`.
   New operator actions write `audit` — the enterprise trail is the audit table,
   designed in from brief 1, not bolted on.

What deliberately does NOT scale (and why that's correct at enterprise too):
- **No roles matrix**: one admin user today; `role` check stays. If a second
  admin appears, the existing `role='admin'` gate covers it. Frontegg-style
  per-user permission JSON is deferred until a real customer needs it — adding
  it later is additive (a join table), not a rework.
- **No per-tenant config tables**: InvoiceNinja's `GroupSetting`/`CompanySettings`
  pattern exists because they serve many companies with self-service settings.
  UbyHost is one company; reminder days and plans are code constants/env.
  If enterprise brings custom schedules, the constants move to a table —
  additive migration, no rework.
- **SQLite→Postgres portability is preserved** (rule 5): all new queries via
  `db.py` helpers; new indexes in a numbered migration (next free: 0032).

### Explicitly out of scope
- Card auto-bill, Stripe subscriptions (0410/#517 track it).
- Multi-user host teams, permission matrices, SSO/SCIM (Frontegg's enterprise
  half — no customer asks for it; privacy-first says don't store it).
- Any third-party identity or billing service: no Frontegg, no InvoiceNinja
  embedding. Both were studies, not vendors.
- Guest-side anything.

## 4. Privacy & legal (rule 2/5 compliance)

- Reminders and digests mail **hosts** (business context, existing lawful basis
  — contractual). Digest goes to the one admin. No new personal-data fields;
  no `retention.py` additions needed; no new outbound requests beyond SES mail.
- Every operator action writes `audit` with actor `operator:<username>`.
- Unsubscribe: reminder mails carry the existing host mail footer (host account
  mail is transactional-contractual; no marketing toggle introduced).

## 5. i18n, design, tests

- New copy in `_ADMIN_*` string blocks (CS lead, EN parity, VI where the
  customers page already carries it) — remember the #565 lesson: CS lines go
  into the CS dict.
- Templates reuse `ui_section`/`ui_form_actions`/`ui_button`; light mode only;
  browser/geometry rows for every changed page, 390px screenshot per page.
- Test-map rows: operator customer dashboard, billing, mail. New tests:
  reminder idempotency + schedule derivation, operator action authorization
  (host gets 403), digest content, activity card bounds.

## 6. Build order (briefs, next free task numbers)

| # | Brief | Depends on |
|---|---|---|
| 1 | 0437: payment-received host mail (settle hook + idempotency + tests) | — |
| 2 | 0438: customer-page operator card: toggle surface + verification resend, reusing existing routes | — |
| 3 | 0439: preview link + audit/activity cards on the customer detail (bounded, keyset) | 0438 |
| 4 | 0440: /admin operations home: queue cards (snapshot-fed, `LIMIT ≤ 25` per card, migration 0032 adds the unpaid-overdue index) | — |
| 5 | ~~0441: daily operator digest mail~~ dropped (owner decision §7.3) | — |

## 7. Owner decisions (2026-10-29, chat) — resolved

1. **Dunning schedule: keep as is** (0417's due+1/+7, pause-14; no retune).
2. **Payment-received mail: both** — the buyer e-mail on the invoice *and* the
   host's account e-mail. One mail kind, two recipients, one idempotency key
   per invoice; if the addresses are identical, one recipient (no duplicate).
3. **Digest: not built now** — brief 0441 (digest mail) dropped from this plan;
   the in-app queue on /admin remains in scope (brief 0440).
4. **Second admin: not now** — single-admin stands; the `role='admin'` gate
   already covers adding one later. No invite flow in any brief.

## 8. Fit for what UbyHost admin needs today (verified)

Checked against the code this session: dunning (0417), overdue derivation,
recurring issuance, activate/deactivate, admin preview, keyset pagination,
9-state filters, cockpit + snapshot — all exist and are reused, not rebuilt.
This plan adds exactly three things the admin lacks today: payment-received
mail (both recipients, per decision §7.2), one user-action surface, a
needs-attention queue (in-app only, per §7.3), and the audit/activity view —
each additive, each with its enterprise-scale pattern decided in §4.
