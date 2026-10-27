# Operator customer dashboard implementation report

Status: review, draft. No deployment or feature enablement.

## Implemented

- Admin-only /admin/customers list and /admin/customers/{id} detail, linked
  from existing account administration. Read-only links lead to existing
  account support and billing/payment actions.
- Fixed 25-row keyset pagination in both directions with unique id ordering.
  Workspace/email/username search is parameterized, length-limited and treats
  SQL wildcard characters literally. State and plan filters run before LIMIT.
- Distinguish legacy free, unverified signup, disabled account, trial pending,
  trial, active subscription, overdue, canceling and paused. Active subscription
  means stored subscription status, not proof of a settled bank payment.
- Global aggregate counts link to matching lists. Trial ending soon means an
  active account with trialing status and end date from today through seven
  days ahead in the configured timezone. Billing-off banner explains effective
  free access despite stored subscription statuses.
- Active property counts use the billing source (active = 1), batched for the
  bounded list rather than one query per customer. Detail fetches one customer
  and at most ten recent invoices, with links to existing PDF delivery.
- Czech and English strings, existing design components, page design documents,
  access/search/pagination/status tests and admin browser guard routes included.
  No guest data, login tokens, credentials, billing writes or new dependencies.

## Verification and limits

The managed environment remains unavailable ("managed network requirements
require sandbox enforcement"). No local tests, context lint or browser screenshots
were run or inspected. GitHub CI must verify this draft. Applicable test-map rows:
operator customers, host UI/browser guard and copy translations.

The customer query bounds returned rows and uses id seek rather than OFFSET.
Aggregate metrics and literal substring search may scan host accounts in the
database. No load-tested scale or query-plan benchmark is claimed and no index
migration was added without evidence. Existing account support and billing pages
retain their earlier unbounded lists; links do not make those pages scalable.

## Remaining

- Inspect CI browser results and screenshots, including long account names,
  Czech and English controls, empty state, phone and wide layouts.
- Onboarding progress, async mail/invoice job exception queues, customer-specific
  payment reconciliation, pending subscription-change details, invoice history
  pagination beyond the latest ten, and operational freshness indicators remain
  separate delivery slices.
- Public signup/pricing/passkey/wizard flow and recurring billing validation are
  tracked separately. This dashboard does not enable billing or collect payment.
