# Signup pricing handoff

Draft implementation for the owner's explicitly authorized self-service journey.

## Implemented

- Plan, month/year interval, apartment forecast (1–50) and TTLock preferences
  survive public signup links, language switches, no-JavaScript form submission,
  validation errors, replacement verification emails and verification on another
  device. Values are allowlisted both before persistence and when read.
- Preferences are stored only on new or still-pending accounts. An anonymous
  signup with an existing verified email cannot overwrite that owner's choices.
- A scanner GET never activates the account. The existing nonce-based,
  single-use verification POST remains responsible for activation.
- A signup with preferences opens /onboarding after verification. The existing
  optional security prompt offers a passkey on supported devices and Later;
  email login remains available. The existing property setup checklist is reused.
- Onboarding shows the saved selection and links to subscription review.
  An unordered subscription form prefills plan, interval and TTLock. This is
  advisory only: no order, invoice, founder grant or payment is created.
  Actual active apartment count remains the source for quotes and invoices.
  An existing order takes precedence over saved preferences.
- Migration 0025 adds one nullable JSON column. Retention follows account deletion
  (including seven-day pending signup purge). Open PR file lists were inspected:
  none reserves migration 0025.

## Validation

Not run: the managed workspace repeatedly fails with
`managed network requirements require sandbox enforcement`.
Changes were assembled through the connected GitHub tools. No local Python,
context lint, app server, browser, geometry or screenshot validation ran.

Added test_signup_selection.py covering cross-device verification, scanner GET,
replay, no-JS fields, validation errors, invalid/oversized input, pending retries,
verified-email overwrite protection, owner scoping, order precedence and absence
of invoices. Required: this file, signup/auth/security, onboarding/property,
billing and migration test-map rows; public signup tests; context lint.
UI release requirements remain browser/geometry tests with zero skips and
390 px screenshots of signup and onboarding.

## Dependencies and remaining work

Merge with #537 for activation-based trials and retirement of new founder grants.
The edits to signup.register and billing_order.form_values are separate from
#537's activation and founder logic. Existing pricing calculator buttons use plan, interval, apts and ttlock;
this implementation accepts apts as an alias for the canonical apartments field.
No pricing URL migration is required.
No frontend or end-to-end passkey ceremony was exercised, and no browser claim is
made. Existing property-setup, passkey and billing components were reused; full
signup-to-setup-to-confirmed-bank-transfer-order evidence remains outstanding.
No flags were enabled, production deployed, dependencies added or outbound
requests introduced. Help/guide and non-CS/EN translations still need review.
