# 0993 report

Status: review

## Files changed

- `App/app/templates/guest/_fee_estimate.html`, `_fee_pay.html`, `_fee_why.html` (new), `form.html` (estimate before legal notice)
- `App/app/static/guest.css` (`.g-fee-box` system)
- `App/app/i18n.py`, `App/app/guest_uk_i18n.py` (new keys; removed `fee_intro`, `fee_estimate_*`, `fee_choose`, `fee_what_is_this`)
- `App/app/templates/guest/base.html` (`guest.css?v=20261107-0993`)
- `App/tests/static_versions.json`, `test_guest_browser_e2e.py`, `test_stay_fee_guest_pay_0897.py` (`test_0960` copy)

## Commands (last lines)

- i18n/copy: `46 passed`
- `test_guest_*.py`: `594 passed` (after `rm /tmp/d2.db`; executor VM uses `UBYHOST_DB=/tmp/d2.db`)
- browser+geometry: `51 passed in 254.79s`
- `context_lint.py`: `context lint: OK`
- `test_static_versions.py`: `3 passed`

## §7 acceptance

- [x] `#fee-estimate` is `section.g-fee-box`, before `#legal-notice`, "You do not pay now." visible
- [x] `#fee-pay` amount line, "Please pay now." panel, rails + per-guest + why folds
- [x] No `?` toggle, no badge, no `text-transform`; Step 7 skipped (no copy JS)
- [x] Six-language i18n; dead keys removed from templates
- [x] `initLegalFeeJump` / `_fee_estimate_inline`: none
- [x] Cache `20261107-0993` in `base.html` + manifest
- [x] Section 6 green; browser `-rs` 0 skipped
- [x] Screenshots: `docs/tasks/screenshots-0958/form-estimate-390.png`, `guest-hub-fee-card-390.png` (when `UBYHOST_0958_SHOTS=1`)

**Screenshots (390):** Form shows large amount, green “You do not pay now.” panel, calm grey box, legal block below; hub shows group total, ink-bordered pay panel, radio-style rails, no horizontal scroll; Revolut uses `g-btn secondary` (hub also has coral `g-btn`).

## Deviations

- Step 7 skipped (tool budget; `.g-sr-only` exists but optional).
- Updated `test_stay_fee_guest_pay_0897.py::test_0960` (not listed in brief §3) so `test_guest_*.py` passes with new copy.
- Test DB: clear `/tmp/d2.db` if `browser-fee-gbr` UNIQUE errors appear.

## Questions

- Liable nights differ from stay nights: copy not decided (out of scope).
- Paid status: out of scope.

## Owner steps

1. Open PR from `task/0993-guest-stay-fee-clear`. 2. Wait for green CI. 3. UX gate per workflow. 4. `scripts/merge-pr-on-green.sh <PR>`. 5. Close or rebase PR 798.
