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

The gap today (after #561, #565, #568/0448):
- Billing events happen (invoice issued, paid, overdue, plan changed) but the
  operator must notice them by opening pages. No reminders, no digests.
- InvoiceNinja-grade lifecycle mechanics that matter at UbyHost's scale:
  **dunning** (reminder schedule on unpaid invoices), **status derivation**
  (overdue is computed, not stored), **pro-rated changes**, **recurring
  generation** already exist in part (0448 assigns; `billing_order.change`
  pro-rates annual). What's missing is the *time-driven* layer and the
  *combined* operator view.
- "Sort out my users": users are already sorted (role admin|host, states
  legacy/unverified/disabled/trial/active/overdue/canceling/paused, keyset
  pagination, search). What's missing is **actions**: activate/deactivate,
  resend verification, impersonate-with-audit, and a per-user activity view.

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

### Slice A — invoice reminders (dunning) — the billing-matters slice
1. `billing_reminders.py` + scheduler job (daily, e.g. 07:00): for each unpaid,
   unvoided invoice, send reminder at due+3, due+10, due+20 (owner-tunable
   constants, env overridable). Idempotent per `(invoice_id, n)`; mail kinds
   `billing.reminder.1/2/3`; hosts get plain Czech ("Faktura VS… je nezaplacená,
   splatnost byla …"). Overdue state is derived (§2), and the cockpit watchlist
   already shows it — reminders are the *mail* half of the same truth.
2. Payment-received mail on bank-match (today marking paid is silent to the host).

### Slice B — operator user actions ("sort out my users")
3. `/admin/customers/{id}` action row additions: activate/deactivate (writes
   `user_account.active`, audited, mails the user in Czech), resend verification
   link (reuse existing token flow), each behind POST + CSRF as 0448 did.
4. Admin preview (PR #280's 24h-reason flow) linked from the customer page and
   the audit row surfaced on the customer detail ("previewed 2026-10-29: reason").
5. Per-user activity card on the detail page: last logins, last mails, billing
   events, audit trail — all from existing tables, bounded to the latest 20.

### Slice C — the combined console ("billing + operations in one place")
6. `/admin` home for the admin role: today's snapshot cards (MRR, overdue count,
   trials ending — the cockpit queries reused), plus an **operations queue**:
   overdue invoices needing a reminder, unverified signups, expiring trials,
   unresolved support alerts. Each links to the existing page for the action.
   No new queries — the cockpit's snapshot job (06:15) feeds it.
7. Daily operator digest mail (one mail to the admin, 06:30): the same queue,
   plain Czech, zero if nothing needs attention.

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
| 1 | 0437: invoice reminder engine + scheduler + mail kinds + tests | — |
| 2 | 0438: payment-received host mail on bank match | — |
| 3 | 0439: operator actions (activate/deactivate, resend verification) + audit | — |
| 4 | 0440: preview link + audit surface on customer detail | 0439 |
| 5 | 0441: user activity card (bounded reads) | — |
| 6 | 0442: /admin operations home + queue cards | 0437–0441 shipped |
| 7 | 0443: daily operator digest mail | 0442 |

## 7. Open items for the owner (decide, don't build)

1. Reminder days: due+3/10/20 as defaults — keep or change?
2. Should a deactivated host's unpaid invoices keep dunning, or stop?
3. Digest by mail (07:30) or in-app-only queue on /admin?
4. Second admin account now (family/staff) or stay single-admin?
