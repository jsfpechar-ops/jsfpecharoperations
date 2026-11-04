# 0933: fee legal-notice section + guest i18n + guest RÚIAN autocomplete (CZ)

Status: todo
Depends on: 0897 | Base commit: `main` after PR #763 merges | Branch: task/0933-stay-fee-legal-ruian
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Plan: [docs/plans/stay-fee-guest-payment.md](../plans/stay-fee-guest-payment.md) (read §5, counsel draft in §10)

## 1. Objective

Three independent pieces, all guest-facing copy/UX plumbing:
1. The conditional `legal_notice_fee_*` section in the guest form's legal
   notice (`templates/guest/_legal_notice.html`, pattern = the passport
   section gated on `apartment.passport_photo_policy`), with keys in all 6
   guest languages, using the counsel-draft copy in plan §10 (human lawyer
   sign-off is an owner gate before merge — see Owner steps).
2. Guest-facing RÚIAN autocomplete in the residence card when country = CZ:
   new token-scoped route `GET /l/{token}/ruian-suggest?q=...` reusing
   `ruian.suggest()`, rate-limited, progressive enhancement only (plain inputs
   work without JS). Picking a suggestion fills `res_city` with the
   suggestion's `addr_obec` (the obec, e.g. "Praha" — never the část obce
   "Praha 5" / `addr_obec_cast`) and `res_street` with street + number, so
   the same-obec match in 0898 compares official names, not typing.
3. Nothing else. The fee amount UI is 0932; do not touch it here.

## 2. Context

- Legal notice: `templates/guest/_legal_notice.html` — add after the passport
  `{% if %}` block:
  `{% if fee_notice %}<h3>{{ t('legal_notice_fee_title') }}</h3><p>{{ t('legal_notice_fee_body') }}</p>{% endif %}`.
  `fee_notice` comes from `_form_context()` (routes/guest.py): true when
  `config.STAY_FEE_GUEST_PAY and apartment.stay_fee_collect and rate > 0`.
  The single existing `legal_ack` checkbox covers it; `UBYHOST_GUEST_NOTICE_VERSION`
  must be bumped at deploy (owner step; rule in docs/ENVIRONMENT.md:86).
  Copy rules: state the duty, the payee (the host), that the host remits to
  the municipality, the base (commenced days except arrival), the cap
  (50 Kč/person/day, Act 565/1990 Sb. §3d), statutory exemptions exist
  (e.g. under 18, §3b), >60 consecutive days out of scope (§3a), and that
  UbyHost does not process the payment and does not record whether it was
  paid. **Never mention the residence/permanent-residence criterion** — that
  is the secret exemption (plan §9). Use the counsel draft in plan §10.
- i18n: guest keys live in `App/app/i18n.py` STRINGS en/cs/de/es/fr and
  `App/app/guest_uk_i18n.py` for uk. New keys: `legal_notice_fee_title`,
  `legal_notice_fee_body`, plus ruian suggest keys (`ruian_suggest_label`,
  `ruian_suggest_hint`, `ruian_suggest_none`).
- RÚIAN: `App/app/ruian.py` — `enabled()`, `usable_query(q)`,
  `rate_limited(owner_user_id)`, `record_lookup(owner_user_id)`, `suggest(q)`.
  Host route pattern: `routes/admin.py:1297` `/apartments/ruian-suggest`.
  Guest route: `GET /l/{token}/ruian-suggest` in `routes/guest.py` with the
  same guards as other guest GETs (`_open_link`, `_require_pin`), plus
  `rate_limit.record("ruian_guest", token + "|" + client_ip)` and
  `ruian.rate_limited(apartment["owner_user_id"])` + `record_lookup`. Return
  `JSONResponse(ruian.suggest(q))`; 404/429 when disabled/limited.
  JS: small progressive-enhancement snippet in form.html (datalist or fetch
  + dropdown) active only when `res_country` value is CZ; no-JS fallback =
  the existing plain inputs. Bump `?v=` in `templates/guest/base.html`.
- Tests: guest-pages rows (`test_guest_browser_e2e.py`, `test_host_geometry.py`,
  0 skipped), i18n completeness test if one exists in the test-map (all
  languages must have the new keys), screenshots-0933 390 px for the form.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/guest/_legal_notice.html` | edit | conditional fee section |
| `App/app/routes/guest.py` | edit | `fee_notice` in `_form_context()`; new `/l/{token}/ruian-suggest` GET |
| `App/app/templates/guest/form.html` | edit | ruian autocomplete JS (CZ only) |
| `App/app/templates/guest/base.html` | edit | `?v=` bump for changed guest js |
| `App/app/i18n.py`, `App/app/guest_uk_i18n.py` | edit | new keys, all 6 languages |
| `App/app/rate_limit.py` usage only | — | call `rate_limit.record`; no edit |
| tests + screenshots-0933 | create/extend | e2e/geometry 0 skipped, 390 px form screenshot, i18n key parity |

No other file may change.

## 4. Steps

1. Add the conditional section to `_legal_notice.html`.
2. `fee_notice` in `_form_context()` per the gate above.
3. i18n keys in all 6 languages from plan §10 draft (cs + en verbatim; de/es/fr/uk
   translated faithfully, legal terms kept).
4. Guest RÚIAN route + JS (progressive enhancement) + `?v=` bump.
5. Tests + screenshots.

## 5. Do not touch

CSP in main.py (the suggest call is same-origin fetch — fine), db schema,
payment rails UI (0932), `docs/context/*`, no commits/push/PR.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_guest_browser_e2e.py tests/test_host_geometry.py -q -rs 2>&1 | tail -30` plus guest-form and i18n test-map rows; repo root `python3 scripts/context_lint.py 2>&1 | tail -5`.

## 7. Acceptance

- [ ] Legal-notice fee section renders only when the gate is true; `legal_ack`
      still one checkbox; all 6 languages have the keys.
- [ ] Guest RÚIAN route: 404 when ruian disabled, 429 when rate-limited,
      suggestions only for the token's apartment; no-JS form unchanged.
- [ ] Picking a suggestion puts `addr_obec` (not `addr_obec_cast`) into
      `res_city`; typing freely without picking still saves as today.
- [ ] The fee section ends with a link to the full Act
      (`https://www.e-sbirka.cz/sb/1990/565`, `rel="noopener"`) in all 6
      languages (counsel condition, plan §1 decision 10).
- [ ] Copy contains no residence-criterion wording (grep the strings).
- [ ] e2e/geometry 0 skipped; lint OK.

## 8. Stop and ask

Per TEMPLATE.md §8 — and STOP if the counsel draft in plan §10 looks legally
wrong; write it in the report instead of improvising copy.

## 9. Report

`docs/tasks/0933-report.md` (≤600 tokens), `Status: review`.

## Risk list (reviewer)

`_legal_notice.html` diff, i18n key parity, the new guest route's guards.

## Owner steps

1. Send the plan §10 counsel draft + final strings to the lawyer; merge only
   after sign-off.
2. Bump `UBYHOST_GUEST_NOTICE_VERSION` in prod env at deploy.
3. Merge via scripts/merge-pr-on-green.sh.
