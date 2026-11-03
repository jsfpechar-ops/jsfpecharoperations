# 0897: stay-fee guest pay — phase 0: schema, kill switch, property toggle

Status: todo
Depends on: none | Base commit: 0ece616a (branch vibe/stay-fee-guest-payment-plan-73df64) | Branch: task/0897-stay-fee-phase0
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Plan: [docs/plans/stay-fee-guest-payment.md](../plans/stay-fee-guest-payment.md) (read §1, §3, §5, §7 phase 0)

## 1. Objective

Add the five host-config columns on `apartment` (migration `0036` + pg twin
`00006`), the global kill switch `UBYHOST_STAY_FEE_GUEST_PAY` (default `off`),
and the per-property toggle + rail checkboxes + two validated link fields +
cash note in the fee section of the property editor — which automatically
appears on the property page AND the onboarding wizard's property step,
because both render `templates/_stay_fee_fields.html`. No guest-facing
change yet; nothing is collected from guests in this brief.

## 2. Context

- Migration pattern: `App/app/migrations/0035_apartment_ocr_scan.sql` (SQLite)
  and its twin `App/migrations_pg/00005_apartment_ocr_scan.sql` — the pg twin
  has `-- +goose Up`, `IF NOT EXISTS`, and
  `INSERT INTO schema_migrations (version, name, applied_at) VALUES (35, 'apartment_ocr_scan', ...) ON CONFLICT (version) DO NOTHING;`
  — copy that exactly for version 36.
- Env-flag pattern: `App/app/config.py:343` (`STRIPE_MODE = os.environ.get(...)`);
  document in `.env.example` (see the STRIPE block ~line 81) and
  `docs/ENVIRONMENT.md` (one table row, cf. `UBYHOST_GUEST_NOTICE_VERSION` row).
- Fee settings UI lives in `App/app/templates/_stay_fee_fields.html`, included
  from `templates/_property_editor.html:374` (property page + wizard property
  step). Persisted via `fee_form_values()` in `App/app/routes/stay_fees.py:215`
  and the apartment save in `App/app/routes/admin.py` (see ~1553-1560
  `_STAY_FEE_FIELDS`-style list and the `"stay_fee_rate_czk" in form` branch
  ~1726). Passport/OCR toggles are the pattern for a checkbox:
  `_property_editor.html:196-200` (`ocr_scan`).
- Link validation: accept only `https` URLs whose host is `revolut.com` or a
  subdomain (for the Revolut link) / `stripe.com` or a subdomain (Stripe link) —
  a pasted arbitrary URL on a later guest page would be phishing. Use
  `urllib.parse.urlparse`; reject everything else with a flash error.
- Rules: SQL only via `db.py` helpers / numbered migration files; never edit
  SCHEMA/ADDED_COLUMNS in db.py (see db.py:1500 comment); no new dependency;
  light mode; EN+CS host copy in the same commit (all host languages in
  `App/app/host_i18n.py`).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/migrations/0036_stay_fee_guest_pay.sql` | create | the 5 ALTERs from plan §3 |
| `App/migrations_pg/00006_stay_fee_guest_pay.sql` | create | goose twin + schema_migrations insert for 36 |
| `App/app/config.py` | edit | `STAY_FEE_GUEST_PAY = os.environ.get("UBYHOST_STAY_FEE_GUEST_PAY", "off").strip().lower() == "on"` near line 343 |
| `.env.example` | edit | document the flag (default off) |
| `docs/ENVIRONMENT.md` | edit | one table row |
| `App/app/templates/_stay_fee_fields.html` | edit | toggle + rails checkboxes + 2 link inputs + cash note textarea, all inside `{% if ... %}` disabled state when kill switch off |
| `App/app/routes/stay_fees.py` | edit | extend `fee_form_values()`: parse `stay_fee_guest_rails` csv (allowed: qr, iban, revolut, stripe, cash), validate links, trim note (max ~300 chars) |
| `App/app/routes/admin.py` | edit | make the apartment save persist the 5 new fields (add to the fee field list ~1553 and the save branch ~1726); when kill switch off, force defaults (0 / '' / None) so a stale POST cannot enable it |
| `App/app/host_i18n.py` | edit | host labels/hints for the new controls, all host languages |
| tests (test-map rows for stay_fees / property form) | extend | save-path tests: defaults when off, validation of bad links, rails csv normalisation |

No other file may change.

## 4. Steps

1. Write the two migration files exactly per plan §3 SQL and the 00005 twin
   pattern. Next free SQLite version is 36, pg version 00006 (lint prints them).
2. `config.py`: add the flag next to STRIPE_MODE. `.env.example` + ENVIRONMENT.md rows.
3. `_stay_fee_fields.html`: add the block at the end of the fee section —
   checkbox `stay_fee_collect` (role=switch style like ocr_scan), checkboxes
   for rails named `stay_fee_guest_rails` values `qr iban revolut stripe cash`
   (checked if in stored csv), text inputs `stay_fee_guest_revolut_link`,
   `stay_fee_guest_stripe_link`, textarea `stay_fee_guest_cash_note`. When
   `config.STAY_FEE_GUEST_PAY` is false, render the whole block disabled with a
   one-line hint "turned off on this deployment".
4. `fee_form_values()`: only when the kill switch is on; else return the
   defaults. Normalise rails to a sorted csv of allowed values; validate links
   (https + host allow-list) raising ValueError -> admin save shows the existing
   fee flash error path (`flash.stay_fees.account_invalid`-style, add a new key).
5. Wire the admin save path (both the plain apartment form and the wizard
   `stay_fee` step save) to pass the new fields through.
6. Tests: extend the stay_fees/property-form test-map rows.

## 5. Do not touch

`App/app/db.py` SCHEMA/ADDED_COLUMNS; anything under `App/app/templates/guest/`;
`main.py` CSP; `docs/context/*` (orchestrator owns those); no commits/push/PR
(owner override from 0896 still applies unless told otherwise: leave changes in
the working tree).

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_stay_fees*.py tests/test_property*.py -q --tb=short -x 2>&1 | tail -30` (only the test-map rows for these areas), then `python3 scripts/context_lint.py 2>&1 | tail -5` from the repo root. Also boot-check migrations: start the app once locally (run.sh) and confirm no migration error, or run the migration unit path used by test-map for db.

## 7. Acceptance

- [ ] `0036` applies on SQLite and `00006` is valid goose SQL (see 00005).
- [ ] With `UBYHOST_STAY_FEE_GUEST_PAY` unset, the fee block renders disabled
      and a POST with the fields set does NOT enable them.
- [ ] With it `on`, toggling persists; a non-https or non-revolut.com /
      non-stripe.com link is rejected with a flash error.
- [ ] Rails csv round-trips (`qr,cash` etc.).
- [ ] Test-map rows pass; context lint OK.

## 8. Stop and ask

Per TEMPLATE.md §8 (missing excerpt, test fails twice, >25 tool calls / ~50k
tokens, new dependency, file outside §3, unclear step, push/secrets/deploy).

## 9. Report

Write `docs/tasks/0897-report.md` (≤600 tokens), set `Status: review`.

## Risk list (reviewer)

`App/app/routes/admin.py` save branch, `fee_form_values()`, both migration files.

## Owner steps

1. Set `UBYHOST_STAY_FEE_GUEST_PAY=off` in prod env (default off anyway).
2. Merge via scripts/merge-pr-on-green.sh after CI.
