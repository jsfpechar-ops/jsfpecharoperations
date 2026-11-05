# 0958 executor report

Status: blocked (checkpoint reached; not ready for review)
Branch: codex/0958-calendar-type-state (local only, not pushed) | Base: 7b0355c. Designated branch claude/new-session-2vk4py left untouched.

## Done
- Worktree /tmp/ubyhost-0958-worktree; approved patch applied (`git apply --check` and apply clean, `git diff --check` clean).
- Commits: `0958 step 1` (CSS, template key 0958a, test, brief, patch), `0958 step 2` (manifest: dashboard-calendar.css entry only).
- venv: Python 3.12.3, requirements.lock (hashes) and requirements-dev.txt installed, playwright 1.63.0 (CI pin). No pins changed.

## Command results
1. Calendar group, `-x`: FAIL at test_feed_dns_pinning (`OSError: Address family not supported`; sandbox has no IPv6). Without `-x`: 202 passed, 13 failed (1 IPv6 feed test, 12 new 0958 tests).
2. 0958 regression: 12 failed, 0 skipped. Every case fails at the final `assert dialog.is_hidden()` after Escape; the dialog stays open. Keyboard/pointer type switching, aria-pressed, field visibility and colour checks ran before that point. Cause not investigated.
3. `test_cleaning*.py`: 80 passed, 0 skipped.
4. Host group, `-x`: FAIL at `test_host_fee_navigation.py::test_frozen_report_order_and_forms` ("Your records" missing). Not investigated; not known to be caused by this change. Remaining host, layout-lint and 0710 tests not run.
5. `test_static_versions.py` + `test_wp07_cache_heartbeats.py`: 16 passed, 0 skipped.
6. `context_lint.py`: OK (pre-existing WARNs only). `git diff --check`: clean. Changed files: the 4 allowlisted App files plus the two docs/tasks files.

## Acceptance
- Not met: Escape cancellation (regression fails); selected/inactive colour acceptance unverified in the final assertion.
- Not met: layout-lint zero findings (not run); browser groups have failures.
- Met: manifest matches the new CSS key; context lint OK; only named files changed.

## Screenshots
10 files at /tmp/ubyhost-0958 (`calendar-0958-*`, outside the repo). Not inspected: the call budget was spent. No visual claim is made.

## Deviations
- Stay/Cleaning type-state change is in the patch as supplied; no CSS was edited by hand.
- Local branch name follows the brief, not the session's designated branch.

## Left (queued)
- Diagnose why Escape does not close the create dialog (new test or app behaviour).
- Investigate the host fee navigation failure against base.
- Run the remaining host/layout-lint tests and inspect screenshots at 390/768/1280.
- G01 (guest draft), C04/C05/C06 and the rest of B02 remain queued.

## Owner actions
- Decide whether the regression failure is a test or an app issue.
- Provide an IPv6-capable environment for test_feed_dns_pinning, or accept the CI result.
- Publishing (none done): `git push -u origin codex/0958-calendar-type-state` after review.
