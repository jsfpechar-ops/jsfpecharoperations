# QA fix: new-guest form input (2026-11-09)

Source: QA findings guest-form-a-01/02, guest-form-b-04, guest-form-c-02/04/06, guest-checkin-01..04.

## Done

1. Enter no longer presses a language button. A hidden default submit sits before the language buttons (works without JavaScript); with JavaScript, Enter presses the visible step's Continue, or Save on the last step.
2. A refused save keeps what the guest typed in name, city and street fields even when the text is in another alphabet, and the summary names the field and the reason in every guest language (`latin_only_error`). An alphabet-only city is no longer reported as "City is required". Validation is unchanged: the same input is refused.
3. Offline: the submit is held back with a friendly sentence (`save_network_error`); the form stays as is.
4. No JavaScript: a visible sentence (`nojs_needed`) says JavaScript is needed for signature and photo.

## Deferred

- A connection that drops while a request is in flight still shows the browser's own page (needs a fetch-based submit; that changes click-to-navigation timing the existing e2e tests rely on).
- Pre-typing Latin hint, per-field client check, draft in sessionStorage, no-JS typed-name signature (would change what UbyPort receives).

## Tests

`tests/test_guest_form_input_browser.py` (new), `test_guest_browser_e2e.py`, `test_layout_lint_browser.py`, `test_host_geometry.py`, `test_guest_*.py`, `test_validation*.py` with `UBYHOST_REQUIRE_BROWSER=1`, 0 skipped.
