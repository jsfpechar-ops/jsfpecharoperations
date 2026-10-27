# Self-service signup, billing and operator dashboard

Status: planning, 2026-10-27. No implementation or live rollout is implied by this document.
Scope: customer onboarding, recurring invoices, scalable admin, and alignment with the pricing brief on this branch. Preserve existing hosts as free. Owner approved bank transfer for launch; card payments deferred.

## Owner decisions

- A 30-day trial begins when a new customer opens an account. Interpret account opening as successful email verification and activation: submitting an unverified email or a mail scanner opening a link does not start the clock. This is the first point at which the host has an active account. Do not restart on login, property setup or UbyPort connection. Communicate the rule consistently.
- Existing hosts stay free, including after feature flags are enabled; do not auto-create billable accounts for them or change their entitlements.
- Monthly subscriptions invoice monthly; annual subscriptions invoice annually. Payment by bank transfer. No card gateway yet.
- Remove founding host offers for new orders both in marketing and checkout. Preserve any existing confirmed agreement. No new discounts or pricing changes.
- Additions during a period may incur a prorated supplementary charge; reductions take effect at renewal, with an explicit preview and confirmation. Preserve graduated marginal tiers and show exact amounts and effective dates.
- Host explicitly orders a paid subscription before an invoice is issued. Free trial has no automatic card collection.
- Design pricing and administration to feel premium and approachable. Avoid invented savings, false urgency, or overstating AI capabilities.

## What exists on main (inspect current code and deployments again before building)

- Signup exists in App/app/routes/signup.py and App/app/signup.py, behind UBYHOST_SIGNUP_ENABLED; an explicit POST verifies the email and opens the session.
- Passkey and onboarding components exist. Current successful signup redirects to /, so the end-to-end prompt and onboarding handoff still require verification.
- Billing is implemented and switched off according to docs/context/status.md; PR #528 is merged. Billing uses bank-transfer invoices; the ČSOB statement is uploaded manually, with exceptions handled by the operator. The production configuration and subsequent work remain unverified.
- billing_trial.py currently starts at UbyPort verification or after seven days and must be changed to the owner decision. A seven-day fallback would violate the new decision.
- billing_order.py quote/place currently may automatically claim a founder slot for a new annual order. Merely hiding its marketing banner is insufficient.
- billing_admin.py and routes/admin_billing.py already list invoices, upload statements, manually mark paid, issue storno, and export documents. unpaid() loads all unpaid invoices; a scalable customer dashboard requires bounded queries and pagination.

## Customer flow

1. Pricing: one decision area for interval, apartment count, plan, volume tiers and add-ons. The existing companion pricing brief covers comparison, alignment, Leon and Havel copy and TTLock placement. Update all trial-start claims to account verification; reconcile FAQ structured data and other public copy.
2. Trial CTA passes selected plan, period, count and TTLock to signup. Treat them as untrusted preselection, validate allowlists and bounds on the server, preserve across verification without leaking secrets, and show the choice again before paid ordering. No query string alone authorizes a paid order.
3. Signup: email and terms, safe verification with rate limiting, generic responses for existing addresses and a resend/recovery path. After successful verification, atomically provision workspace and trial once; ensure retries and concurrent requests cannot create duplicate workspaces or restart dates. Prompt for passkey with accessible skip and email-link recovery. Return users with existing accounts go through safe login.
4. Onboarding: resume wizard; create first property and configure UbyPort. Preserve session, language and selected plan through email verification and the passkey prompt. If interrupted, provide an obvious way to resume.
5. Subscription: during trial show dates and choices. Before conversion require explicit order confirmation and billing information. Clearly disclose exact billing date and amount, annual billing where selected, bank transfer and cancellation. No order means no invoice. Verify all messages and existing terms against actual behavior.
6. Count active properties from the existing billing source of truth; show a preview before changes, and reconcile actual active count with ordered count. Invoice snapshots record plan, interval, active count, additions and fixed period. Display final amount, exact annual invoice, per-property add-on and account-wide white label correctly.

## Admin dashboard

Add an admin-only operator overview, linked from existing administration, with Czech and English labels and mobile usable layout.

- Overview: active, trial, trial ending soon, unpaid/overdue and exceptions. Define each metric, exclude free legacy accounts from paid revenue metrics, and label dates. Link each metric to a filtered list.
- Action queue: unverified signups needing attention, onboarding stalled based on actual recorded state (not inferred completion), trial-ending customers, failed email/invoice jobs, overdue invoices and unmatched/partial payments. Show source, last update and actionable destination; no speculative status.
- Customers: server-side search by workspace/email and filters for free legacy, trial, active, overdue, paused, signup/verification and plan. Stable ordering and bounded pagination at every size; filter and sort before pagination. Minimum necessary account data only.
- Customer detail: account verification and creation dates, onboarding progress where recorded, last activity if available, active property count, plan, period, add-ons, trial dates, pending changes, invoices and payments. Link to existing actions and billing pages; do not put guest personal data into the overview.
- Operator actions: reuse existing admin-protected services for resend invoice, statement upload, manual payment recording, correction/storno and accountant export. Where no safe existing action exists, specify/build it as a separate reviewed task. Every mutating action needs authorization, CSRF, input validation, an audit trail, error feedback and safeguards against duplicate actions.
- Account support: access recovery, disabling or re-enabling accounts, and any support-mode action must reuse existing security policy and audit logging. Never expose login links or guest data in the list.
- Large-scale behavior: bounded page sizes, indexed lookups justified by measured plans, no full-table materialization in request handlers, no N+1 per customer. Empty, loading, partial-failure and stale job states must be understandable. Record freshness for asynchronous job and email status.
- Success: an operator can find a customer quickly, determine their actual status and next step, process an unmatched bank payment, locate an invoice, and export the month's books without visiting a database.

## Delivery slices

A. Verify current signup, passkey, onboarding and billing paths; reconcile open branches and changed deployments. Split work into non-overlapping numbered briefs using the repo's workflow. Resolve the current pricing brief's overlap with signup and billing.
B. Correct trial lifecycle at activation; remove seven-day/UbyPort triggers for new accounts without resetting existing trials, and preserve legacy free accounts. Add race, retry, time boundary and no-order tests. Update all public and in-app trial copy.
C. Persist and validate pricing choices end to end; avoid provisioning duplicate accounts and protect against signup enumeration. Verify passkey skip, recovery, on-device flow and wizard resume.
D. Retire new founder eligibility in both quote and order paths; ensure published prices equal the invoice and existing agreements are preserved. Verify active-property changes and all tier boundaries with snapshots, retries and concurrent jobs.
E. Build scalable admin overview, paginated customers and detail, delegating actual payment and invoice operations to existing services. Use existing design tokens and role checks. Introduce indexes only after assessing queries and migrations.
F. Review recurring invoice and outbox idempotency, retries, rollover, payment matching, dunning, paid-state restoration and accounting exports. Alerts surface failures to operators. Bank transfer reconciliation remains statement upload, not a fictitious automatic bank integration.
G. Finish pricing page, customer help, terms and privacy copy consistent with implementation. Ship feature-flagged to staging and a small pilot; only enable public signup/billing once end-to-end evidence, payment and operational readiness are confirmed.

## Acceptance and checks

- An unverified signup does not activate or consume a trial. Verified account gets one 30-day trial starting at activation, even with retries or UbyPort delays; exact date boundary and Prague timezone are consistent across UI, reminders and jobs.
- Every existing free host remains free and uninvoiced even with both feature flags on.
- Selecting either plan and billing period survives signup and yields the same reviewed total at ordering, using actual current property count; TTLock charges only standard. No founder slot is automatically applied.
- One invoice per period despite retries, concurrent workers and restarts; mail failures remain retriable and visible. A duplicate bank statement does not record duplicate payments. Partial, unmatched and overpaid cases remain actionable.
- Pricing tiers, Czech/English copy, exact billing frequency and trial start match the engine. CTA alignment holds at desktop and plans stack without overflow on phones.
- Dashboard queries are role-protected, paginated and filtered server-side. Free hosts are visibly distinguishable. Pagination has no duplicate or missing rows with stable data. Operator actions enforce authorization and leave audit records.
- Test existing applicable auth, signup, passkeys, onboarding, billing, invoices, bank import, privacy and browser/geometry suites using the repository test-map. Browser checks have zero skips; capture and inspect 390 px screenshots for each changed page. Run context lint. Do not gate UbyPort reporting on payment.
- Before launch, verify mail delivery, real ČSOB export matching, operator invoice details, accounting/tax wording and any necessary legal review using staging and a pilot.

## Limitations of this plan

The managed workspace failed to start with "managed network requirements require sandbox enforcement". Repository inspection used connected GitHub read access; no code was changed and no application, security, billing, browser or production tests were run. This is a plan and cannot establish that a production flow works.
