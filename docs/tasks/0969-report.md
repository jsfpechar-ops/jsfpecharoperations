# 0969 report (B11, alert stacks)

Status: blocked
Reason: 4 tests in `App/tests/test_host_ux_acceptance.py` fail on base `7b0355c` too (pre-existing). The owner named only the fee-navigation test for deselection, so they are not deselected here. Brief stop rule applies.

## Changed files (`git diff 7b0355c --stat`)
- `App/app/templates/_host_alerts.html` (35 lines), `App/app/host_i18n.py` (+2), `App/app/host_vi_i18n.py` (+1)
- `App/tests/test_host_alert_stack_browser.py` (new, 331 lines)
- `docs/tasks/0969-alert-stacks.md` (brief, committed earlier as 4e524344; status line changed in `0969 status`)
- `docs/tasks/0969-report.md` (this file). No tracked PNG changed; `git status` clean.

## Fee-navigation base proof
Detached base `7b0355c`: `test_frozen_report_order_and_forms` FAILED (`assert "Your records" in page`), 1 failed. Deselected in step 3d only; log says "1 deselected". Base worktree removed.

## Chunks (UBYHOST_REQUIRE_BROWSER=1, 0 skipped in every log)
- 3a new file, 6 passed (`chunk-1.log`)
- 3b alert set, 100 passed (`chunk-1.log`)
- 3c group A, 9 files, `-x`: 27 passed, EXIT 0 (`chunk-2.log`)
- 3c group B, 8 files, `-x`: 28 passed, EXIT 0 (`chunk-3.log`)
- 3c group C, 5 files, `-x`: 44 passed, EXIT 0 (`chunk-4b.log`, rerun)
- 3d non-browser, no `-x`, fee test deselected: 181 passed, 5 failed, EXIT 1 (`chunk-5.log`)

Last lines, 3d: `....`, `5 failed, 181 passed, 1 deselected, 1 warning in 1812.18s`, `EXIT_CODE=1`. Other chunks end with their dot line, the summary line and `EXIT_CODE=0`.

## Failures
- Four tests in `test_host_ux_acceptance.py` fail identically on base and on the branch rerun (8 passed, 4 failed each): `test_each_property_setting_has_exactly_one_editable_control_in_the_whole_host`, `test_every_page_family_fits_every_width_language_and_rail_state`, `test_keyboard_reaches_rail_tabs_and_editor_with_visible_focus`, `test_page_families_through_rail_cards_search_and_back`.
- `test_without_javascript_tabs_reload_and_the_shared_editors_save` failed only in the first 3d run (30 s locator timeout under load). It passed on the branch rerun and on base.
- `test_static_versions.py` passed inside 3d. No static file changed, so no regeneration. `context_lint.py` OK.

## Screenshots (all 13 opened)
- zero-stays-390: no stack; title first. OK.
- one-stays-390: large card, title, deadline text, red "Open the stay", dismiss. OK.
- one-settings-390: same title and deadline text, no action line, dismiss kept. OK.
- many-stays 390/768/1280: four large cards (3 deadlines plus guest link), each with its action line. No clipping.
- many-settings 390/768/1280: 3 compact deadline lines plus "1 more alerts / Open the dashboard"; guest-link alert folded. OK.
- filtered-karlin 390/768/1280: Vinohrady row compact, labelled "Workspace alert, another property", deadline kept; 2 large Karlin rows; summary line. Label clear.
- filtered-vinohrady 1280: Vinohrady large; 2 Karlin rows compact and labelled; guest-link card large. Label clear, nothing clipped.
- Compact rows link the whole line by markup (`a.notification-link` wraps the content; dismiss sits outside). Click not exercised here.
- Copy note: "1 more alerts" is plural for n=1. Existing key, not changed.

## Deviations
- Ran 3a and 3b too, since brief step 3 lists four commands.
- First group C run (`chunk-4.log`) was killed with SIGTERM after 28 dots. Rerun as `chunk-4b.log`.
- A run started elsewhere (pid 30318, `/tmp/ubyhost-b11/run3c.sh`, 22:16) shared this worktree and screenshot dir. Not killed; same code.
- Other executors' pytest runs shared the machine (CPU contention).
- `git diff --check` flags trailing whitespace at `docs/tasks/0969-alert-stacks.md:437` (inside the brief's embedded patch). Not changed.
- Step 1 baseline not re-run here.
- A cleanup `rm` was blocked by the safety check; no DB files removed; not retried.

## Acceptance (section 7)
- [ ] Step 1 baseline: not re-run here.
- [ ] Step 3: not green (ux file above).
- [x] Chromium decisions: 6 browser tests passed, including dismissal and return navigation; screenshots as above.
- [x] Before/after keys: `test_same_filing_issues_and_deadlines_on_every_page` passed.
- [ ] `git diff --stat` lists only section 3 files: the brief is also in the diff.
- [x] Screenshots only under `/tmp/ubyhost-b11`.

## Done / Left
Done: steps 1 to 3 run, static and lint checks, screenshots inspected, tree clean.
Left: reviewer or owner decision on the four pre-existing ux failures (deselect or separate brief). Then rerun 3d. Push and PR not done.
