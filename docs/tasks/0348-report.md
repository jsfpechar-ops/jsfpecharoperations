# 0348 report

Status: blocked

## Files changed
- App/app/guest_guide_merge.py (new, step 1)
- App/app/scheduler.py (step 2)
- App/app/routes/guest_guide.py (step 3)
- App/app/templates/guest_guide.html (step 4)
- App/app/host_i18n.py (step 5)
- App/tests/test_guest_guide_merge.py, App/tests/eval/guide_import_cases.json, App/scripts/guide_import_eval.py (step 6, copied from docs/plans/0348-files/)
- docs/ENVIRONMENT.md (step 7)
- docs/tasks/0348-report.md (this file)

## Commands (last lines)
- Step 1 check: `2793 12 cs` (matches expected)
- Step 2 check: `Brief 0347: ` (matches)
- Step 5/4 tests (`test_guest_guide_pages.py test_host_i18n.py test_flash_literals.py`): 3 failed, 27 passed. Failures are the three Vietnamese language-endpoint tests in test_host_i18n.py (`test_language_endpoint_sets_cookie_and_rejects_open_redirects`, `test_a_signed_in_dashboard_keeps_vietnamese`, `test_language_endpoint_accepts_vietnamese`), error `sqlite3.OperationalError: no such table: apartment`. The brief says this is known and not from this change; not verified against base.
- Step 6 (`test_guest_guide_merge.py test_guest_guide_import.py test_ai.py`): `68 passed, 1 warning in 6.18s`
- Step 6 eval (`guide_import_eval.py --offline`): four `lang=` lines then `PASS`
- Step 7 lint: `context lint: OK` (warnings only, pre-existing)
- Acceptance: `test_guest_guide_merge.py` 21 passed; `grep -c` for done-state writes in guest_guide_merge.py = 0; `"state": "check"` at line 269; scheduler imports and calls process_pending (line 363); eval file has no URLs or e-mails.

## Section 7 ticked
- [x] no done-state write in merge module; check write present
- [x] 21 merge tests pass
- [x] scheduler wiring
- [x] Guide page screenshot: taken at review by the orchestrator (390 px, one `used` Booking import, one `done` Airbnb import, two `check` cards): result line and "Fetched, drafting cards" badge show, no horizontal scroll (scrollWidth 390).
- [x] guide_import_eval.py --offline PASS; eval file holds no real listing text
- [ ] Ship rule (staging feature flag): owner step
- [x] ENVIRONMENT row present; lint OK

## Deviations
- Review fix: a non-dict listing or an unexpected crash in merge fails that row instead of stalling the queue (2 tests).
Done: steps 1 to 7. Left: step 8 (390 px screenshot of the guide page with a `used` import and the result line). I did not seed a database or run the browser in this session (tool budget). Nothing was pushed. The 3 test_host_i18n failures noted above are the brief's known set.

## Questions
- Should the screenshot be taken in a fresh session (seeded fixture) before review?

## Owner steps left
- Ship rule from brief section 7: run `scripts/guide_import_eval.py` with the real key on staging, paste output in the PR, then set `UBYHOST_AI_FEATURES` and the budget env var.
