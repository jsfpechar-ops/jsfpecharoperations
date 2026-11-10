# 1076 report

Files: host_i18n.py, host_vi_i18n.py, i18n.py, guest_uk_i18n.py, _property_editor.html, setup_wizard/police.html, guest/claim.html; tests: test_property_readiness, test_property_navigation_browser, test_operator_naming, test_claim_mail, test_claim_copy.

Commands (last line):
- Copy: 1 failed (test_reporting_help_0097 geometry, fails on base too), 69 passed.
- Filing and claim row: 13 failed in test_endtoend, 385 passed, 1 skipped (identical on base; order-dependent, test_endtoend alone 28 passed).
- Guest (UBYHOST_REQUIRE_BROWSER=1): 663 passed, 0 skipped.
- Host + guardrails: 4 failed, 256 passed, 0 skipped. Known: guest-new Cancel 43 px, flash sticky toast, guide cs 390 help-tip (ux_acceptance). The fourth, filter_panels ViewTransition console error, is flaky: passes on the branch alone, fails on base.
- Properties, stay fee, payments: 1488 passed, 0 skipped.
- Layout lint: 4 passed.

Section 7: all ticked, except the diff-grep count is 1, not 0: the intended `tw_email_short` swap in claim.html.
Word budget: en 58, cs 54 (en text shortened by orchestrator decision).

Pages seen (screenshots-1076, 390/768/1280): property-editor (Basic details; police section in idub-*-*.png and editor-police-cs-390.png, from the visual review), setup-police (new IDUB and short-name labels, no overflow), stay-fee-detail (VS metric card; payment card in "details missing" state), stay-fees-list, qr ("Payment reference (VS)"), claim (hint takes 2 lines at 390 px, rest unchanged).

Deviations: steps committed in groups; screenshots by a scratch Playwright test (run from tests/, deleted).

Follow-ups: (1) `claim_email_help` also mentions the receipt; a later brief may trim it. (2) The claim line leaves out the door code on purpose. (3) `stay_fees.payment.vs_hint` still says "this symbol" next to the new label.

Review follow-ups (not blocking): no-break space in "No marketing" and its translations (orphan word at 768/1280); de "So bleibt diese Buchung bei Ihnen. Keine Werbung."; vi "do cảnh sát cấp" wording; en IDUB hint "numbers" → "digits"; remaining "variable symbol" wording on stay-fee pages next to "Payment reference (VS)"; vi editor headings untranslated.
