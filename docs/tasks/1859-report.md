# 1859 report

Status: review

## Files changed

`App/app/config.py`, `main.py`, `templating.py`, `scheduler.py`; host templates (`_shell_*`, `menu`, `reservation_detail`, `reservations`); `docs/ENVIRONMENT.md`; `App/tests/test_payments_hidden.py`; brief.

## Commands (last lines)

- `pytest tests/test_payments_hidden.py tests/test_booking_site_host.py tests/test_payments_dashboard.py tests/test_stripe_connect.py -q` → 58 passed
- `pytest tests/test_layout_lint_browser.py -q` → 4 passed, 0 skipped (~228s)
- `python3 scripts/context_lint.py` → OK

## Acceptance §7

- Flag default off; hidden mode tested with monkeypatch.
- Webhook `POST /webhooks/stripe` → 200 + `ignored` when hidden and stripe off.
- Guide `/guide?lang=en` still shows Payments section.
- Layout lint green with hidden off (production default).

## UX gate

Layout lint 4/4, no skips. Nav change is behind `UBYHOST_PAYMENTS_HIDDEN=1` only; screenshots at default (flag off) unchanged from main.

## Owner steps

See brief § Owner steps.

## Deviations

None.