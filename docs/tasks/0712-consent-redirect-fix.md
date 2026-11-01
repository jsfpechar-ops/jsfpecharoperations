# 0712: Consent "Continue to Stripe" hangs on a blank page (CSP form-action)

Status: review
Depends on: none | Base commit: 02ebb6eb | Branch: task/0712-consent-redirect-fix (already exists, check it out)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Production bug (owner, 1 Nov 2026, 21:12): ticking the consent box on `/payments/consent` and pressing Continue shows a blank page and then falls back to the consent page. The consent POST answers 303 to `/payments/connect/start`, which answers 303 to `connect.stripe.com`. Our CSP has `form-action 'self'`, and the browser blocks a form submission that redirects to another origin. Fix: after recording consent, redirect to `/payments` (same origin) with a short message. The host then opens Stripe with the existing link button, which is a plain link and not a form, so the CSP does not block it.

## 2. Context

- `App/app/main.py` `_csp()` contains `"form-action 'self'; …"`. **Do not change the CSP.**
- `App/app/routes/payments.py`, end of `payments_consent_accept`:
  ```python
      payments_consent.record(int(workspace["id"]))
      return RedirectResponse("/payments/connect/start", status_code=303)
  ```
  `_back` and `_flash` are already imported in that file.
- `App/app/host_i18n.py` anchor lines: English `        "payments.err.consent": "Tick the box to continue.",` and Czech `        "payments.err.consent": "Pro pokračování zaškrtněte souhlas.",` (Czech is raw UTF-8).
- `App/tests/test_payments_consent.py`, `test_post_with_tick_records_and_continues_to_stripe` has `    assert response.headers["location"] == "/payments/connect/start"`.
- `App/app/templates/payments_consent.html` line 20: `    {{ ui_button(t('payments.consent.continue'), 'primary', type='submit') }}`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/routes/payments.py | edit | redirect to /payments with a message |
| App/app/host_i18n.py | edit | `payments.consent.saved` en + cs; button label |
| App/tests/test_payments_consent.py | edit | expected location |
| docs/tasks/0712-report.md | new | report |
| docs/tasks/0712-consent-redirect-fix.md | edit | Status line only |

No other file may change.

## 4. Steps

1. `git checkout task/0712-consent-redirect-fix`. Set line 3 to `Status: in-progress`, commit `0712 start`.
2. `App/app/routes/payments.py`: replace the `return RedirectResponse("/payments/connect/start", status_code=303)` line in `payments_consent_accept` with:
   ```python
       # 0712: never redirect a form POST to Stripe. The CSP form-action 'self'
       # blocks a form whose redirect chain leaves our origin (blank page). Back
       # to /payments, where "Open Stripe" is a plain link.
       return _back("/payments", msg=_flash(request, "payments.consent.saved"))
   ```
3. `App/app/host_i18n.py`: under the English anchor add `        "payments.consent.saved": "Saved. Now tap Open Stripe to set up your account.",`; under the Czech anchor add `        "payments.consent.saved": "Uloženo. Teď klepněte na Otevřít Stripe a nastavte účet.",`. Change the values of `payments.consent.continue` to `"Agree and continue"` (en) and `"Souhlasím a pokračuji"` (cs): the button no longer goes straight to Stripe.
4. `App/tests/test_payments_consent.py`: replace the `== "/payments/connect/start"` assert with `    assert response.headers["location"].startswith("/payments?msg=")`. Rename the test to `test_post_with_tick_records_and_returns_to_payments`. Add this test at the end of the non-browser tests (before the `# --- browser` line):
   ```python
   def test_consent_post_never_redirects_off_site(client, owner):
       """0712: CSP form-action 'self' blocks a POST whose redirects leave our origin."""
       response = client.post("/payments/consent", data={"agree": "1"}, follow_redirects=False)
       location = response.headers["location"]
       assert location.startswith("/") and not location.startswith("//")
       assert "connect/start" not in location
   ```
5. Commit after each of steps 2 to 4 (`0712 step N`).

## 5. Do not touch

`App/app/main.py` (CSP), `App/app/static/`, the Stripe routes, templates. Hard rule 8: never push to main.

## 6. Commands

From `App/`:
1. `.venv/bin/python -m pytest tests/test_payments_consent.py tests/test_payments_dashboard.py tests/test_stripe_connect.py -q --tb=short -k "not fits_a_phone" 2>&1 | tail -10` → all pass.
2. `.venv/bin/python -m pytest tests/test_host_i18n.py -q --tb=short -k same_keys 2>&1 | tail -5` → pass.
From the repo root: 3. `python3 scripts/context_lint.py 2>&1 | tail -3` → `context lint: OK`.

## 7. Acceptance

- [ ] POST /payments/consent with the tick redirects to `/payments?msg=…`, never to `/payments/connect/start`.
- [ ] §6 passes.

## 8. Stop and ask

As in the TEMPLATE.

## 9. Report

Write `docs/tasks/0712-report.md` (400 tokens at most), set `Status: review`. Do not push.

## Risk list (for the reviewer)

`App/app/routes/payments.py`.

## Owner steps

After merge and deploy: Platby, tick the box, tap "Souhlasím a pokračuji". You land on Platby with "Uloženo…". Tap "Otevřít Stripe".
