# 0848 report

Status: review

## Files changed (uncommitted, per owner instruction)
- App/app/templates/stay_fees.html: bulk box after anchor A (confirm-ready form when 2+ ready, PDF zip link when 2+ saved); copy-setup cards above the unset-property block (per unset period with copy_from).
- App/app/static/app2.css: 0848 block only, after the 0794 end marker (appears once).
- App/tests/test_stay_fees_speed_page_0848.py: new, 5 tests.
- docs/tasks/screenshots-0848/stay-fees-390.png: copied from screenshots-0710/stay_fees-390.png.
- docs/tasks/0848-report.md: this file.
- Not changed: base.html, static_versions.json (cache-key bump and --write skipped, orchestrator does it).

## Commands (tails)
1. `.venv/bin/python -m pytest tests/test_stay_fees_speed_page_0848.py -q --tb=short -x` -> `5 passed in 4.48s`
2. `.venv/bin/python -m pytest tests/test_invoice_*.py tests/test_stay_fee*.py tests/test_fee_*.py tests/test_static_versions.py -q --tb=short -x` -> stopped at `test_a_changed_static_file_has_a_new_key`. Rerun without -x: `2 failed, 289 passed, 2 skipped`. Both failures are the expected cache-key checks (app2.css ?v= still 20261102-0867, host2.css changed with stale key 20261102-0864 from a prior commit, manifest not current). Skips are two screenshot-only tests (UBYHOST_SHOTS_DIR unset).
3. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k stay_fees -q --tb=short -rs` -> `12 passed, 142 deselected`, 0 skipped.
4. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py -q --tb=line -rfs` -> `2 failed, 219 passed, 1 warning in 636.44s`. Failures are both known pre-existing: test_host_fee_navigation.py::test_frozen_report_order_and_forms and test_host_ux_acceptance.py::test_page_families_through_rail_cards_search_and_back (line 642). Without UBYHOST_REQUIRE_BROWSER=1 the brief's command skips test_host_copy_corrections.py:369 (browser evidence test); with it set, that test ran.
5. Geometry findings: none named .fee-bulk or .fee-copy. No CSS fix needed.
6. `UBYHOST_SHOTS_V2=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k screenshots -q` -> `1 passed in 85.10s`.

## Section 7 acceptance
- [x] Bulk box only with 2+ ready or 2+ saved; one confirm question (data-confirm); lists exactly the ready ids (test_two_ready_show_one_confirm_all, test_bulk_box_posts_end_to_end).
- [x] Copy card only for unset properties with a same-place source (test_unset_sibling_shows_the_copy_card).
- [x] Commands 1-4 run; command 3 0 skipped; command 4 0 skipped with the browser flag set (2 known failures, see above).
- [x] docs/tasks/screenshots-0848/stay-fees-390.png exists.

## Deviations
- Commits: none (owner said do not commit). Brief step commits not made.
- Screenshot: the rich fixture shows no bulk box and no copy card (both properties "Not set up", no ready or saved rows). Said so as the brief allows; seeded screenshot is 0890's job.
- Command 4 run with UBYHOST_REQUIRE_BROWSER=1 so the browser-evidence test does not skip.
- Untracked files under docs/tasks/screenshots-0710/ (stays-*.png, submissions-*.png) were written by the screenshot run and are not committed.

## Questions
None.

## Owner steps left
1. Orchestrator: bump app2.css ?v= in base.html to 20261103-0848 (and host2.css key), then `App/.venv/bin/python tests/test_static_versions.py --write`, then rerun tests/test_static_versions.py.
2. Look at docs/tasks/screenshots-0848/stay-fees-390.png, commit the listed files, push, open PR, merge with scripts/merge-pr-on-green.sh when CI is green.
