# 0932: guest pay panel on the stay hub + form estimate + residence order

Status: todo
Depends on: 0898 | Base commit: `main` after PR #763 merges | Branch: task/0932-stay-fee-guest-panel
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Plan: [docs/plans/stay-fee-guest-payment.md](../plans/stay-fee-guest-payment.md) (read §4, §5)

## 1. Objective

Read-only "money" card on the guest stay hub: when the property collects the
fee and the live `charge_for_reservation()` total is > 0, show total +
per-person breakdown + a rail picker (one control per host-enabled rail).
When the total is 0, show NOTHING — no "no fee due", no reason (owner
decision: exemption secrecy). Plus the form-end estimate card (same rule) and
the residence field reorder (country → city → street). No POST endpoints, no
stored payment state, no CSP change (external pay URLs are plain `<a>` links).

## 2. Context

- Hub: `App/app/routes/guest.py` `stay_overview()` (~1141) builds context for
  `templates/guest/stay.html`, whose fixed card order is status → next action
  → **money** → records → footer (comment at top of stay.html). Add
  `fee_panel` to the context only when
  `config.STAY_FEE_GUEST_PAY and stay_fee_collect and rate>0` and
  `charge_for_reservation()` returns a total > 0 and all expected guests are
  registered (`remaining is None or remaining <= 0`).
- Panel data: total, lines (per guest), rate, rails csv, revolut link,
  cash note, QR payload from `payments.spayd(iban, total, vs, msg)` with
  `iban` from `legal_entity` of the apartment's owner (pattern:
  `payment_request.qr_payload()` ~line 158), VS = `f"{reservation_id:010d}"`,
  QR PNG as data URI via `payments.qr_data_uri()`. If qr/iban enabled but the
  owner has no account, omit those rails at render (plan §9).
- Rail picker: no-JS-friendly — `<details>` per rail or radio group; buttons
  for revolut are `<a class="g-btn" href=... rel="noopener">` (never a
  form POST to an external URL — CSP form-action 'self', cf. 0730 comment in
  routes/payments.py). Cash rail shows the host note (default text if empty).
- Form: `_form_context()` (~1483) in routes/guest.py builds `guest/form.html`
  context; add `fee_notice` (same gate) and `fee_estimate` computed from the
  UN-saved entered values (stay dates + birth date) via the same math; the
  estimate card at the end of form.html renders only when estimate > 0.
- Residence reorder: `templates/guest/form.html` ~194-232 — move the
  `res_country` field ABOVE `res_street`, then `res_city` (keep the existing
  `.g-row` for city+? — new order: country field, then row city+street or
  city then street; keep ids/names/autocomplete/required identical). The
  nationality→residence sync JS (~430) is untouched.
- Guest design rules: Arrival lane (`docs/DESIGN.md` ~387), light mode, one
  coral action per screen, guest i18n keys in `i18n.py` (en/cs/de/es/fr) +
  `guest_uk_i18n.py` (uk) — new keys prefixed `fee_` / `fee_pay_`. Bump the
  `?v=` key in `templates/guest/base.html` for every changed guest CSS/JS.
- Tests: guest-pages rows (`docs/context/rules.md` "Guest pages"):
  `tests/test_guest_browser_e2e.py`, `tests/test_host_geometry.py` — 0 skipped;
  one 390 px screenshot per changed page into `docs/tasks/screenshots-0932/`;
  static_versions via `test_static_versions.py --write`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/guest.py` | edit | `fee_panel`/`fee_notice`/`fee_estimate` context in `stay_overview()` and `_form_context()` |
| `App/app/templates/guest/stay.html` | edit | include the money card in position 3 |
| `App/app/templates/guest/_fee_pay.html` | create | the panel partial |
| `App/app/templates/guest/form.html` | edit | estimate card at the end + residence field reorder |
| `App/app/templates/guest/_fee_estimate.html` | create | small form card partial |
| `App/app/i18n.py`, `App/app/guest_uk_i18n.py` | edit | `fee_*` keys, all 6 guest languages |
| `App/app/templates/guest/base.html` | edit | `?v=` bump if guest css/js changes |
| `App/app/static/guest*.css` / js if needed | edit | panel styles in guest.css (Arrival lane tokens) |
| tests + `App/tests/static_versions.json` + `docs/tasks/screenshots-0932/` | create/extend | guest e2e rows, geometry, screenshots |

No other file may change.

## 4. Steps

1. Context wiring in routes/guest.py (compute once per render; never store).
2. `_fee_pay.html` partial with the rail picker; include from stay.html.
3. form.html: estimate card + residence reorder.
4. i18n keys all 6 languages; base.html `?v=` bump; guest.css tokens.
5. Tests + screenshots (390 px each changed page: stay hub, form).

## 5. Do not touch

`main.py` CSP (no third-party scripts — plain links only), `_legal_notice.html`
(that's 0933), db schema, routes other than guest.py, `docs/context/*`, no
commits/push/PR (leave in working tree).

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_guest_browser_e2e.py tests/test_host_geometry.py -q -rs 2>&1 | tail -30` (0 skipped) plus the stay_fee and guest-form test-map rows; `python3 scripts/context_lint.py 2>&1 | tail -5` from repo root.

## 7. Acceptance

- [ ] Toggle on + signed guests → hub shows the money card with total,
      breakdown and only the enabled rails; total 0 → card absent entirely.
- [ ] Form estimate card appears when estimate > 0, hidden when 0; residence
      order is country → city → street with identical field names.
- [ ] The Revolut button is a plain external links; QR is a data URI; no
      new script-src.
- [ ] Guest e2e + geometry 0 skipped; 390 px screenshots committed;
      lint OK.

## 8. Stop and ask

Per TEMPLATE.md §8.

## 9. Report

`docs/tasks/0932-report.md` (≤600 tokens), `Status: review`.

## Risk list (reviewer)

`routes/guest.py` context diff, `_fee_pay.html`, form.html reorder.

## Owner steps

1. Review screenshots; merge via scripts/merge-pr-on-green.sh.
