# 0169 report

Status: review

## Files changed (commits)
- step 1: App/app/static/host2.css (focus-visible rule; --space-1 is 4px so rule kept as written). design_lint OK.
- step 2: App/app/templates/_components.html line 298, App/app/templates/reservation_detail.html line 20 (tabindex -1, aria-hidden true).
- step 3: App/tests/a11y_guard.js (aria-hidden skip rule; nav-no-current replaced as briefed). Copied to /mnt/project-files/design-reset/tools/a11y_guard.js (identical). Note: the replacement dropped the old `.ui-nav-bottom,.sub-tabs,[data-sub-tabs]` exclusion, as the brief specified.
- step 3b: App/app/templates/_ui.html, App/app/templates/_property_create.html (aria-labels on Read more links).
- step 4: App/app/templates/base.html (host2.css key 20261019-0169), App/tests/static_versions.json. test_static_versions: 2 passed.

## Step 5 (browser tests): 3 failed, 22 passed, 0 skipped
- FAILED test_a11y_guard_browser.py::test_keyboard_focus_is_visible_and_not_covered: 8 findings, focus-obscured 4 (operators, operator-add, operator-edit, invoice-settings: input#new_signature_file / edit_signature_file), focus-not-visible 4 (cleaning from/to, guest-new stay_from/stay_to). The date fields are still reported.
- FAILED test_design_guardrails_browser.py::test_every_host_page_passes_the_layout_guard: 21 field-button-misaligned, as expected (brief 0170).
- FAILED test_host_controls_browser.py::test_host_interactions_geometry_copy_and_archive_controls: at reservations, the first Tab lands on a.skip-link with outline 4px; the test expects 2px. Caused by the step 1 rule (outline width from --space-1).
- Other rules (nav-no-current, no-accessible-name) do not appear in the a11y output.

Last 5 lines of the rerun (run2): "FAILED ... x3", "3 failed, 22 passed, 1 warning in 312.29s".

## Cleanup
Ran `git checkout -- docs/tasks/0102-evidence; git clean -fdq docs/tasks/0102-evidence`.

## Deviations
Done: steps 1 to 4 and 3b. Step 5 not passed. Left: step 5 pass (focus findings and 2px-vs-4px conflict), step 6 final commit (done as report commit only).
Step 1 rule width (4px) conflicts with test_host_controls_browser expecting 2px.

## Questions
1. Should the focus outline be 2px (test) or 4px (brief)?
2. Why do the date fields (cleaning, guest-new) and signature file inputs still report focus-not-visible/obscured after step 1? They may sit outside .host-workspace or be covered by another element; the brief does not name those.

## Owner steps left
None until the questions are answered. Do not push or merge.
