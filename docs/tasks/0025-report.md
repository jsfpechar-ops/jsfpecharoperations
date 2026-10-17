# 0025 report: one guest e-mail; the registration confirmation carries the door code

Status: review
Branch: `task/0025-confirmation-with-door-code`, cut from `main` at `8e89924` (0024 merged).

## Steps

1. Done. Route order in `App/app/routes/guest.py`: `submit_stay_if_complete`, then `on_registration_complete`, then `maybe_notify_completion`. Each call as written.
2. Done. `HOLD_CONFIRMATION_MINUTES`, `completion_door_code`, `_release_confirmation`, `_release_held_confirmations` added after `send_code_mail` in `App/app/door_codes.py`.
3. Done. `_send_code_mail` releases a held confirmation first; if that sent the code, it stops.
4. Done. Both `door_code_notice(..., "failed")` branches in `issue` now call `_release_confirmation` (2 places).
5. Done. `_phase("held_confirmations", _release_held_confirmations)` added after `budget_alerts`.
6. Done. `maybe_notify_completion(reservation, apartment, *, force: bool = False)`.
7. Done. Hold, or the code in the confirmation (`door_code=code_fields`, `payload[mail.DOOR_CODE_KEY]`).
8. Done. `notified_at` on the door code is set only when the code travels in the confirmation.
9. Done. `_guest_mail_content` takes `door_code` and passes it to `build_completion`.
10. Done. `build_completion` takes `door_code` and adds the code block after the status text.
11. Done. `App/tests/test_confirmation_with_door_code.py` created, 8 tests, copied from the brief.
12. Done. §6 run (below).

## Commands

Targeted, `.venv/bin/python -m pytest tests/test_confirmation_with_door_code.py tests/test_door_code_handover.py tests/test_door_codes_safeguards.py tests/test_guest_mail.py -q`, last 5 lines:

```
  from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
80 passed, 1 warning in 1.11s
```

Full, `.venv/bin/python -m pytest tests -q` (last lines of the summary):

```
FAILED tests/test_feed_dns_pinning.py::test_two_concurrent_fetches_do_not_cross_pinned_addresses
FAILED tests/test_feed_url_ssrf.py::test_redirects_are_revalidated_not_followed_blindly
FAILED tests/test_feed_url_ssrf.py::test_a_redirect_that_drops_https_is_refused
FAILED tests/test_feed_url_ssrf.py::test_allows_public_https_calendar - app.f...
4 failed, 2967 passed, 7 warnings in 334.29s (0:05:34)
```

The four are the DNS tests from brief 0023 §2. The browser tests ran in this full run (Chromium symlink in place).

`python3 scripts/context_lint.py`: `context lint: OK`

## Section 7

- [x] §6 passes as stated.
- [x] In `guest.py`, `submit_stay_if_complete` (line 1847) comes before `on_registration_complete` (1848), which comes before `maybe_notify_completion` (1850).
- [x] `grep -c 'DOOR_CODE_PROBLEM' App/app/door_codes.py` prints `4`.
- [x] `git diff --stat origin/main` lists only §3 files: `claim.py`, `door_codes.py`, `mail_notify.py`, `routes/guest.py`, plus the new test file and this report.

## Deviations

None to the steps. The brief's "Do not touch" list (i18n files, templates) is untouched.

## Questions

None.

## Owner steps left

1. Brief step on staging (from the brief): with TTLock keys added back and `UBYHOST_STAGING_NO_LOGIN` removed, register a test stay on a property with a lock. Expect one e-mail with the confirmation and the code.
2. Logs: search `DOOR_CODE_PROBLEM` and confirm nothing appears for that stay.
