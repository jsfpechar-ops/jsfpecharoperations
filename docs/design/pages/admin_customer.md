# Page: Customers (`/admin/customers/{id}`, template `admin_customer.html`)

Master version: 2.0.0.

## Identity
- nav: `users`
- body_kind: `detail`
- title key: `workspace display name`; meta: recorded account status
- back link: customers.title -> /admin/customers

## Header
- primary action: none
- secondary actions: customers.manage -> existing account support; customers.payments -> existing billing page
- tabs: none

## Toolbar
- search: none
- filters: none
- actions: none

## Body
- detail sections: account facts, subscription facts, latest ten invoices
- badges: neutral recorded status; action unverified or overdue
- row menus: none
- all reads are admin-only; existing pages retain mutations

## Empty state
- customers.invoice_none; filters remain available

## Tests
- test_admin_customers.py; admin routes in test_design_guardrails_browser.py
- Browser checks and screenshot inspection remain required before release.
