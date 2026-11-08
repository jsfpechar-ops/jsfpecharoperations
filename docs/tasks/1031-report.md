# 1031 report

Status: blocked (Done: steps 0 to 8. Step 9: test_guest_host_noun.py fails on the cs copy of fee_obec_unknown. Left: step 9 rerun and the report commit after that decision.)

Part 1 (district forms): 6875e53b.

## Reproduction (step 1, red, commit 1c3a793f)
Browser test `test_1031_check_box_follows_every_change`, 390 px, synthetic data.
Steps that passed locally: Prague adult (hidden), Brno adult (150), minor in Brno (hidden), adult again in Brno (150).
Failing `seen`: (row 4, "Praha 3 - Žižkov", hidden False, "150 CZK", data-fee-live `{"from": "2026-11-08", "rate": 50, "to": "2026-11-11"}`, data-obec-rule present with obec "PRAHA").
Hypothesis: H2 (the browser key did not fold a district form to PRAHA). The owner's exact Prague case did not reproduce locally, so the owner's 150 is most likely H1 outside the code (no 0898/1025 on prod, or cached signature.js). Owner steps below.

## Files
- docs/tasks/1031-stay-fee-same-town-and-end-to-end.md (step 0)
- App/tests/test_guest_browser_e2e.py (step 1: 1031 tests appended, first test only)
- App/app/stay_fee.py (step 2: 1031 obec key, property_obec, same_obec_resident)
- App/tests/test_stay_fee_obec_forms_1031.py (step 2: rewritten)
- App/tests/test_stay_fee_obec_0898.py (step 2: "Praha 5 Brno" -> "Brno 5 Praha", as allowed)

## Commands (last lines)
Step 1: `pytest tests/test_guest_browser_e2e.py -k 1031 -rs -q --tb=short -x`: 1 failed, 50 deselected, 0 skipped (the seen tuple above).
Step 2: `pytest tests/test_stay_fee_obec_forms_1031.py tests/test_stay_fee_obec_0898.py tests/test_stay_fee_estimate_0910.py --deselect ...::test_form_script_key_is_the_python_key`: 146 passed, 1 failed, 1 deselected.
The failure: `tests/test_stay_fee_obec_0898.py::test_typo_is_liable_and_has_no_flag`, city "Praga": expected 4 liable nights, got 0.

## Deviations
- Step 2 not green. Conflict between the brief and an existing test: brief step 2 FOLDS and Decided rule 7 map "Praga" to PRAHA (OBEC_ALIASES "PRAGA": "PRAHA"); `0898` expects "Praga" to be liable. Only the "Praha 5 Brno" edit is allowed in 0898, so I did not change it.
- Step 2 test `test_form_script_key_is_the_python_key` was deselected (needs step 3).
- Steps 3 to 9 not run. No screenshots yet (step 8).

## Questions
1. "Praga": keep it as Prague (PRAHA, as brief step 2 says) and change the expected value in 0898 to not liable, or drop the "PRAGA" alias? Brief says not to edit 0898 expected values beyond the named ones. Decision needed.

## Owner steps
1. On the server, check the deployed commit includes this branch (and 0898 `9af79325`, 1025 `02929cad`).
2. Run in production: `SELECT id, internal_name, addr_obec, city_en, stay_fee_rate_czk, stay_fee_collect FROM apartment;` and `SELECT apartment_id, effective_from, rate_czk FROM stay_fee_rate ORDER BY apartment_id, effective_from;` and send the Prague flat row (no guest data).
3. On the phone, open the guest link once after the deploy (new `?v=20261108-1031` key forces the new script; not yet bumped, step 4).

## Session 2 results (steps 2 to 8)
- Step 2: "PRAGA" alias dropped (coordinator decision). obec tests: 146 passed, 1 deselected.
- Step 3: server rule and JS key fold like stay_fee._obec_key. 149 passed (incl. JS parity test).
- Step 4: live nights across a rate change, box re-count listeners, cache keys 20261108-1031. 165 passed.
- Step 5: fee_obec_unknown key in six languages. 80 passed.
- Step 6: tests/test_stay_fee_sametown_1031.py: 25 passed. Fee-number guard: no fee read in the save handler.
- Step 8: browser 1031: 3 passed, 0 skipped.
- Step 9: test_stay_fee*/invoice/static_versions: 557 passed, 2 skipped (skips not from this change, not checked further). context_lint: OK.
  test_guest_*.py: stopped at 262 passed, 1 failed (test_guest_host_noun.py::test_no_guest_ui_or_mail_copy_calls_the_host_ubytovatel: `fee_obec_unknown` in cs contains "Ubytovatel", the forbidden host noun). Brief copy kept unchanged, so this needs an owner/coordinator decision (reword cs copy, or allow the word in that key). Remaining guest files not run.

## Screenshots (390 px)
- /mnt/project-files/ux-shots/stayfee-sametown/check-sametown-390.png: box hidden, amount absent; Submit bar overlaps the Czechia row (sticky button in full-page capture).
- /mnt/project-files/ux-shots/stayfee-sametown/check-othertown-390.png: box shows 150 CZK, 3 nights x 50 CZK, no overlap in the box.
- /mnt/project-files/ux-shots/stayfee-sametown/check-unknown-town-390.png: 150 CZK plus the honest sentence; sticky step bar drawn over content in full-page capture.
