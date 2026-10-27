# Page: Customers (`/admin/customers`, template `admin_customers.html`)

Master version: 2.0.0.

## Identity
- nav: `users`
- body_kind: `list`
- title key: `customers.title`; meta: recorded account status
- back link: none

## Header
- primary action: none
- secondary actions: customers.payments -> existing billing page
- tabs: none

## Toolbar
- search: workspace, email and username; literal substring
- filters: recorded account status and ordered plan
- actions: customers.apply

## Body
- list columns: workspace, active properties, ordered plan, status, billing interval, open
- badges: neutral recorded status; action unverified or overdue
- row menus: none
- all reads are admin-only; existing pages retain mutations

## Empty state
- customers.empty; filters remain available

## Tests
- test_admin_customers.py; admin routes in test_design_guardrails_browser.py
- Browser checks and screenshot inspection remain required before release.
