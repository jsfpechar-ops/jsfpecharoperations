# 0960 report
Status: review

Files: App/app/i18n.py, App/app/guest_uk_i18n.py, App/app/templates/guest/_fee_pay.html, App/tests/test_stay_fee_guest_pay_0897.py, docs/tasks/screenshots-0960/fee-card-390.png, docs/tasks/0960-guest-fee-card-why-and-please-pay.md (Status only).
Steps 1 to 4 done: fee_intro added in en, cs, de, es, fr, uk under the h2; fee_legal_pointer removed (5 keys in i18n.py, 1 in guest_uk_i18n.py; no other use); new test test_0960_fee_card_says_why_and_asks_to_pay_in_plain_text.
Tests: pytest test_stay_fee_guest_pay_0897.py test_static_versions.py: 48 passed. test_guest_browser_e2e.py -k fee: 8 passed, 0 skipped.
Deviations: en intro says "under Czech law" instead of "required by Czech law", to match legal_notice_fee_body ("may charge under its by-law") and the pending legal sign-off. Commit attribution uses Haiku 5.5, not the brief's Sonnet 5.5.
Questions: owner to confirm the legal wording and the cs/de/es/fr/uk translations.
Owner steps left: review copy, then merge via scripts/merge-pr-on-green.sh.
