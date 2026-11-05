# 0958: guest pay, guest-side fixes (executor: Haiku 5.5, alone)
Status: review

## 1. Objective
Guest-side fixes for guest pay of the stay fee.

## 2. Context (research done; do not redo)
Read AGENTS.md, docs/context/executor.md, this brief. Touch only: `App/app/routes/guest.py`,
`App/app/templates/guest/_fee_pay.html`, `_fee_estimate.html`, `App/app/i18n.py`,
`App/app/guest_uk_i18n.py`, `render.yaml`, `App/tests/test_stay_fee_guest_pay_0897.py`,
`App/tests/test_guest_browser_e2e.py`, static-version keys. Do NOT touch host files
(`stay_fees.py`, `_stay_fee_fields.html`, `stay-fee-guest-pay.js`, `host_i18n.py`, `app2.css`): brief 0959 owns them.

## Diagnosis (done by the orchestrator, reproduced with real POST /save flows)
The card hides or empties for two reasons: (1) rails `qr` only + a guest who is not CZ/SK -> `_fee_pay_panel`
returns a card with no methods ("no rails" text), and no `#fee-pay` anchor; (2) a Czech resident (res_country CZE)
whose city equals the property's `addr_obec` is auto-exempt, total is 0, card silently absent. (2) is correct
behaviour, keep it. Also `render.yaml` lacks the flag, so staging never shows the feature.

## 3. Files
Listed in the touch list above.

## 4. Steps
1. **One bank method.** In `_fee_pay_panel` treat stored `qr` as `iban` (a property that stored `qr,iban` or `qr`
   gets one `iban` rail). The `iban` rail carries `iban`, `payee`, and `qr` (data URI) only when `account` and
   `qr_ok` (CZ/SK guest). Template `_fee_pay.html`: for the `iban` rail show the QR image above the details when
   `rail.qr`, details always. Drop the separate `qr` branch. Default-first order: map stored default `qr` to `iban`.
   Rail order is now iban, revolut, cash.
2. **Estimate card copy** (`fee_estimate_body`, all six languages in `i18n.py` and `guest_uk_i18n.py`): drop
   "About"/its translation: "150 CZK for you (3 counted nights x 50 CZK) ...". Keep the caveat that the form
   estimate cannot know later host exemptions and the stay summary total is final.
3. **"?" legal explanation** next to the amount on the estimate card and on the hub fee card: a small `<details>`
   or `title`-free inline disclosure (no JS) reusing key `legal_notice_fee_body` and the link
   https://www.e-sbirka.cz/sb/1990/565 as in `templates/guest/_legal_notice.html`. Add a `fee_what_is_this`
   aria label key in all six languages.
4. **Render staging.** In `render.yaml` add env `UBYHOST_STAY_FEE_GUEST_PAY` value `"on"` for `ubyhost-staging`
   only, with a one-line comment "Staging only; production stays off until 0897 gaps are closed".
5. **Tests.** Update `test_stay_fee_guest_pay_0897.py` and `test_guest_browser_e2e.py` (-k fee) for 3 rails (was 4)
   and the merged method. Add one TestClient test per scenario, driven through the real
   `POST /l/{token}/{id}/save` (see `tests/test_endtoend.py`: `guest_form_data`, `passport_files`;
   `tests/conftest.py: complete_guest_claim`; seed a stay like `_seed` in `test_guest_browser_e2e.py`):
   (a) 1 guest GBR, rails `iban`: redirect ends `#fee-pay`, page has IBAN and no QR; (b) 1 guest CZE (res_country
   GBR): IBAN and QR; (c) 2 declared guests: card absent after first, present after second; (d) CZE resident of
   the property obec: no card. Do not leave `test_zz_*` files.
6. Bump `?v=` keys for any changed static file, then `.venv/bin/python tests/test_static_versions.py --write`.

## 5. Do not touch
Host files owned by brief 0959.

## 6. Commands
`.venv/bin/python -m pytest tests/test_stay_fee_guest_pay_0897.py tests/test_static_versions.py -q --tb=short -x -p no:cacheprovider 2>&1 | tail -30`
and, with `UBYHOST_REQUIRE_BROWSER=1`, `tests/test_guest_browser_e2e.py -k fee`. Add one 390 px screenshot of the
hub fee card and of the form estimate card to the report. Write `docs/tasks/0958-report.md` (10 lines max).
Commit, push to the current branch only. No PR.

## 7. Acceptance
Listed tests pass with 0 skipped; 390 px screenshots in the report.

## 8. Stop and ask
If a step needs a file outside the touch list, stop and ask.

## 9. Report
Write `docs/tasks/0958-report.md` (10 lines max) with a Status line.
