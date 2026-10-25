# 0312 report: Havel page /havel

Status: blocked

Done: steps 1 to 2 (step 3 is a no-op: Vietnamese moved to 0325). Left: steps 4 to 9.

## Files changed
- App/app/host_i18n.py: havel.* copy inserted in en and cs (83 keys each), after the `settings.archive_hint` line of each block.
- docs/tasks/0312-report.md (this file).

## Commands (last lines)
- Step 1 check: `7 messages left this week | Make a new PIN?` (as expected).
- `tests/test_host_i18n.py tests/test_no_em_dashes.py`: `3 failed, 15 passed`. The 3 failures are `test_language_endpoint_sets_cookie_and_rejects_open_redirects`, `test_a_signed_in_dashboard_keeps_vietnamese` and `test_language_endpoint_accepts_vietnamese`, all with `no such table: apartment` in the CSRF primer request. Checked at base 328f5f1 (i18n file swapped back, then restored): the same 3 fail there, so they predate 0312.
- `tests/test_havel_engine.py`: `21 passed`.

## Deviations
- Steps 1 and 2 were applied in one script and committed as one commit, `0312 step 1`, not two commits.
- Step 4 STOPPED on a missing anchor: `App/app/main.py` line 32 is now `from .routes import admin, cleaning as cleaning_routes, dev_ui, guest, guest_guide as guest_guide_routes, guest_guide_view, guest_leon, guest_questions, invoices, legal, mail_unsubscribe, onboarding_wizard, stay_fees`. The brief's old line (without the guest_* entries) is not there. No change made for step 4.
- Step 6 anchor also drifted: `App/app/templates/base.html` line 26 is `/static/host2.css?v=20261024-0354`, not `v=20261022-0289`. Not changed.
- Pre-existing failures in tests/test_host_i18n.py (above) are not caused by 0312 and were not fixed.

## Questions
1. Update the brief's step 4 import line and step 6 cache key to the current text, or should the brief be rewritten?
2. Confirm the 3 pre-existing test_host_i18n failures are a known issue (DB not initialised in that test) and whether they block the PR.

## Owner steps left
None until steps 4 to 9 are done.
