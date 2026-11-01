# 0720 report (partial, executor stopped at the tool-call cap)

Status: blocked (partial). Not pushed.

## Commits
- f8f117d 0720 step 0: overview desktop card, header links row, help marker
  (App/app/static/app2.css, App/app/templates/base.html key 20261101-0720, App/tests/static_versions.json)

## Step 0 (desktop regressions) - done
- Desktop needs-you card: >=1024 rule sets card to block, .h to flex with 14 px gap, actions indented 62 px. Not checked against the 0711 screenshot.
- Header quiet links: body.v2 .ov-head .ov-links flex row with gap 4px 14px.
- Help summary: list-style none and webkit marker hidden on .ov-how summary.
- Tests: test_static_versions.py + test_0710_v2_mockup_match_browser.py: 25 passed. test_design_dashboard.py: 3 passed.
- Screenshots not taken, no 390 px screenshot.

## Per test
- Group A Havel (test_havel_browser, test_0386, test_0391, test_0395, test_havel_launcher_skeleton): NOT FIXED. Run result: 19 failed (of the five files, 532 s). Failures include test_0395 test_stale_start_screen_not_restored, test_0395 test_phone_panel_above_tabbar, test_havel_launcher_skeleton test_havel_launcher_does_not_arm_the_navigation_skeleton. Full list: the run output file in the session task directory (bfsdbupep).
- Havel CSS facts for the next executor: .havel-fab and #havel-sheet styles are not in host.css (no matches). The Havel styles live in App/app/static/host2.css (about 112 rules under `.host-workspace`, using host2 tokens). app2.css has no havel rules yet. The brief's pointer to host.css is wrong. Decide whether to copy from host2.css, or stop and ask (brief section 8).
- Dialog motion (test_motion_browser): not started.
- Copy feedback / filters / controls (test_host_feedback, test_host_filter_panels, test_host_controls): not started.
- Group B and C (test_0705, test_dashboard_phone, test_host_quiet_dashboard, test_host_wide_geometry, test_onboarding_followup, test_navigation_prefetch, test_design_shell, test_door_code_window, test_0201): not started.

## Left to do
1. Read the Havel run output, then decide on the host2.css approach (see above).
2. Groups A (rest), B, C, file by file, with -x -q --tb=line.
3. Final run of all listed files, ruff, design_lint, context_lint.

## Session 2 (executor, 25-call cap reached; partial, not pushed)

Commits: 3c9c5df step 1 (Havel block copied from host2.css, see below), step 1b (chip inline-flex, onboarding logo width), step 1c (composer `[hidden]`), then the key bump commit.

Group A Havel: block `/* v2 shared: Havel ... */` at the end of app2.css, extracted by a script (117 rule blocks; only `--accent-on` undefined, as the brief says).
- test_havel_launcher_skeleton_browser.py: 1 passed.
- test_0395_havel_panel_layer_browser.py: 3 passed.
- test_0386_havel_phone_look_browser.py: 5 passed (fixes: `.havel-chip` display inline-flex, since `min-height` does nothing on inline; onboarding-logo width rules added in a separate app2.css block, because app.css is not loaded on v2 and the 512 px logo overflowed the phone).
- test_0391_havel_topics_first_browser.py: 2 passed (fix: `.havel-composer[hidden]{display:none}`; the composer's display:flex beat the hidden attribute).
- test_havel_browser.py: NOT DONE. Failed at test_phone_launcher_and_sheet. Group B edit: `.ui-tabbar` -> `.tabs` (v2 nav). Remaining failure: `sheet["width"] == 390` gets 356 on the phone. Likely the v2 sheet/dialog width or inset differs from the old shell; not investigated. Other tests in this file not run.

Left to do:
1. test_havel_browser.py: sheet width on 390 (356 vs 390), then the other tests in the file.
2. Group A motion (test_motion_browser.py), feedback, filters, controls.
3. Groups B and C, all other files in the brief list. Not started.
4. test_0201 is WebKit-only locally (brief §2, leave alone).
5. Final run, ruff, design_lint, context_lint. Not run yet.
