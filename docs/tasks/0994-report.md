# 0994 report

Status: review

## Files changed

`App/app/templates/guest/_fee_estimate.html`, `_fee_pay.html`, `_fee_why.html` (new), `form.html`; `App/app/static/guest.css`; `App/app/i18n.py`, `guest_uk_i18n.py`; `guest/base.html` (`guest.css?v=20261107-0994`); `tests/static_versions.json`, `test_guest_browser_e2e.py`. Step 7 skipped.

## Commands (tail)

- i18n/copy: `46 passed`
- `test_guest_*.py`: `596 passed` (`rm /tmp/d2.db` if UNIQUE on `browser-fee-gbr`)
- browser+geometry `-rs`: `51 passed`, 0 skipped
- `context_lint.py`: OK

## §7

All acceptance items met; `initLegalFeeJump` / `_fee_estimate_inline` absent; screenshots under `docs/tasks/screenshots-0958/` (390/768). Form: large amount, green “You do not pay now.” panel, legal below; hub: “Please pay now.”, radio rails, Revolut `g-btn secondary`, two `g-fee-fold` details.

## Deviations

Step 7 copy buttons skipped. `test_stay_fee_guest_pay_0897.py::test_0960` updated for new copy (required for `test_guest_*.py`; not listed in brief §3).

## Questions

Liable nights ≠ stay nights: copy not decided. Paid status: out of scope.

## Owner steps

Open PR, green CI, UX gate, `merge-pr-on-green.sh`, close or narrow PR 798.
