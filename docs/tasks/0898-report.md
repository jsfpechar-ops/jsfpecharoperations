# 0898 report: stay-fee charge computation + same-obec exemption

Status: review
Branch: vibe/stay-fee-guest-payment-plan-73df64 (no commits made)

## Files changed
- `App/app/stay_fee.py`: host decision now wins over the same-obec rule. `obec_auto` applies only when `fee_host_decision` is None (`charge` makes the guest liable even on a city match; `exempt` stays exempt). Minor rule untouched. `local_hint` untouched.
- `App/tests/test_stay_fee_obec_0898.py`: new test `test_host_charge_decision_beats_a_same_obec_match`.
- Earlier (unchanged this run): `App/app/routes/stay_fees.py`, `App/app/templates/stay_fee_detail.html`, `App/app/host_i18n.py`, `App/app/stay_fee.py`.
- Screenshots: `docs/tasks/screenshots-0898/` (4 PNG, see below).

## Tests
- `App/`: `.venv/bin/python -m pytest tests/test_stay_fee*.py -q --tb=short -x`: 195 passed, 0 failed, 0 skipped.
- `UBYHOST_REQUIRE_BROWSER=1 ... test_layout_lint_browser.py test_host_geometry.py -q -rs`: 4 passed, 0 skipped.
- `python3 scripts/design_lint.py`: OK.
- `python3 scripts/context_lint.py`: OK (WARN lines about open briefs only).

## Screenshots (stay-fee detail, guests: Adult, G1 Praha 5 auto-exempt, G2 "Prha" near miss)
- `docs/tasks/screenshots-0898/stay-fee-detail-en-390.png`: "Check residence" badge (grey) + "?" on G2 only; G1 shows grey "Exempt" pill, 0 Kc. No sideways scroll.
- `docs/tasks/screenshots-0898/stay-fee-detail-en-768.png`: same; guest rows fit, no truncation of the badge.
- `docs/tasks/screenshots-0898/stay-fee-detail-en-1280.png`: same; clean.
- `docs/tasks/screenshots-0898/stay-fee-detail-cs-390.png`: "Zkontrolujte bydliste" grey badge + "?"; "Osvobozen/a" for G1. Fits.
- Help popover closed in all captures. Fixed bottom tab bar appears mid-page in full-page captures: capture artifact of a fixed element, not a layout defect.

## Section 5 checklist (design-system.md)
- [x] Badge grey, never coral; explanation only under "?"
- [x] Tokens only; no `style=` in `stay_fee_detail.html`
- [x] No sideways scroll at 390/768/1280 and cs 390
- [x] No nested card added
- [x] No new truncation from this change (pre-existing input placeholders clip at 1280 and 390; not changed, out of scope)

## Deviations and questions
- Country code uses `validation.CZECH_CODE` ("CZE") per orchestrator answer 1.
- Same-obec rule now applies only when the host has no decision (orchestrator answer 2). Report of 0898 earlier said `charge` also exempted; that is reversed.

## Owner steps left
- Host comms note: live fee periods drop same-obec residents after deploy (unsealed periods only).
