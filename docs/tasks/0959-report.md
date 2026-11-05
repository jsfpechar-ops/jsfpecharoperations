# 0959 report (executor)

Status: blocked. The regression test failed a second time after the name-case fix. It now fails at the switch back to English (line 810), not at the name check.

## Changed files
Code and tests: App/app/routes/guest.py, App/app/templates/guest/base.html, App/app/templates/guest/form.html, App/app/templates/_signature_script.html, App/app/static/guest.css, App/app/static/signature.js, App/app/i18n.py, App/app/guest_uk_i18n.py, App/tests/test_guest_browser_e2e.py, App/tests/static_versions.json (regenerated with --write). Commit c9103eef.

Fix applied (guest.py, relang route only): surname, first_name, doc_number, visa_number, res_street, res_city are drawn from the raw posted values. Normalised values still drive step logic. normalise_name, validation.py and the save path are unchanged.

## Commands
- test_guest_browser_e2e.py -k 0959: FAIL (1 failed, 0 passed, 0 skipped). Timeout 30000 ms at line 810 (expect_navigation on switch to EN). Lines before it pass, including the Czech name and surname checks.
- test_static_versions.py + test_wp07_cache_heartbeats.py: PASS 16, FAIL 0, SKIP 0.
- Guest test-map rows, context_lint, git diff --check: NOT RUN (stop rule).

## Acceptance
- New test passes: not met.
- Czech and German step counts: not verified.
- Guest test-map rows: not verified.
- Static and cache tests: met.
- Screenshots: 0959-review-cs-390/768/1280.png exist. Only 390 was inspected: name kept as typed, step 3 of 3, Czech labels, no overflow. Open language menu at 390 not captured.
- Diff only in section 3 files: met (plus i18n and test files listed above).

## Likely cause (not fixed, outside the decision)
signature.js confirm guard: `(drawn || ticked || picked) && !window.confirm(...)`. The test's dialog handler calls pytest.fail on any dialog, so a confirm on the CS to EN switch hangs. Owner or orchestrator to decide: fix the guard state after a redraw, or change the test expectation.

## Deviations
- Commit trailer is Claude Co-Authored-By per the harness instruction, not Codex.
- Step 1 committed although the test fails, per the brief order. Status is blocked.

## Done / Left
Done: relang fix, static regen and checks, 390 CS review inspected.
Left: confirm-guard decision, 768/1280 inspection, EN/CS/DE step checks, menu screenshot, test-map rows, lint.
