# 1072 report: shared queries once per request, alerts top N, Server-Timing

## 1. Files changed (`git diff --stat 1c56e543`)

`App/app/access.py` (+27), `alerts.py` (+15), `auth.py` (+5), `main.py` (+22), `onboarding.py` (+16), `templates/_host_alerts.html` (6), `templating.py` (+5), `App/tests/test_shared_queries_1072.py` (new, 235), `docs/tasks/screenshots-1072/` (6 PNG), this report. No other `App/app` file; `base.html` untouched.

## 2. Commands

- Steps 1 to 10: every step command gave the expected output (`True`, `8`, `3`; 31, 17 and 44 passed).
- Step 11 `tests/test_shared_queries_1072.py`: `16 passed in 2.23s`.
- Step 12 (app files of 1c56e543 checked out, then restored): `9 failed, 7 passed`. The 7 are the cache-edge and isolation tests.
- Section 6.1: `119 passed in 13.44s`.
- Section 6.2 with Chromium: `2 failed, 593 passed, 1 skipped`. Both failures also fail on the base commit 1c56e543 with the same message (rerun there: `2 failed`): `test_host_flash_outcomes.py::test_browser_renders_saved_warning_as_sticky_amber` and `test_host_ux_acceptance.py::test_every_page_family_fits_every_width_language_and_rail_state` (`guide` cs 390, `help-tip-btn` past right edge). The 1 skip is `test_host_copy_corrections.py:369` (wants `UBYHOST_REQUIRE_BROWSER=1`, which 6.2 does not set).
- Section 10.1: `1 failed, 18 passed`, 0 skipped. The failure is the known sandbox finding `guest-new 390 Cancel 43 px` (`tap-target-small`), which also fails on main. Left as is.
- Section 10.2 `test_layout_lint_browser.py`: `4 passed in 232.18s`, 0 skipped.

Measured query counts (SQLite, `RequestStats`): dashboard `/` 21 before, 19 after. Admin preview of `/apartments` 24 before, 15 after.

## 3. Acceptance (section 7)

- [x] 16 passed; step 12 shows 9 fail without the change.
- [x] Section 6 command 1 clean. Command 2: only the 2 failures that the base has too.
- [x] `_signed_in_page` false for static, metrics, healthz, signed-out, `/l/...`, `/cleaning/shared/...`; regex matches on `/apartments`.
- [x] No `App/app` file outside section 3; `base.html` untouched.
- [x] Two hosts in turn never see each other's property names.
- [x] `/settings` is 200 with the summary line when no non-critical row survives.
- [ ] Fresh Fable review of `auth.py` and `access.py` (orchestrator).
- [x] UX gate.

## 4. UX gate

Screenshots in `docs/tasks/screenshots-1072/`.

- Settings (`settings-alerts-*.png`), 390: three critical cards, each on its own line, the title of the third wraps to two lines, the summary card "1 more alerts / Open the dashboard" is whole, no sideways scroll. 768: same four cards, full width, nothing clipped. 1280: cards fill the content column beside the rail, close buttons aligned right.
- Dashboard (`dashboard-*.png`), 390: no alert stack; the alerts are the "2 things need you today" cards with full-width buttons, no overflow. 768: same, one column. 1280: "What needs you 2" rows with the button at the right, calendar and Today table below.
- Finding, not from this brief and not changed: the summary reads "1 more alerts" (plural after 1).

Design-system checklist: [x] no own shell, style or raw colour added; [x] no new action, form, fine print or copy key; [x] 390, 768, 1280 without sideways scroll; [x] layout lint green, 0 skipped, screenshots opened; [ ] CI watched (after the PR).

## 5. Deviations

1. `test_server_timing_is_never_sent_on_guest_or_shared_cleaning_pages` is stronger than the brief: besides the HTTP check it calls `main._signed_in_page` with the host's account set on the request for both paths (must be False) and for `/apartments` (must be True), and asserts the header on a host page again after the loop. The test file therefore imports `main`.
2. Steps 5 and 6 are one commit (`1072 step 6`).
3. Step 12 used `git checkout 1c56e543 -- App/app` and `git checkout HEAD -- App/app` in place of `git stash`: the stash is shared between worktrees.
4. Pushes were made by the executor, as the orchestrator asked.

## 6. Questions

None.

## 7. Owner steps left

As in the brief: open the PR, and after the deploy check that Cloudflare and Caddy pass `Server-Timing` through.
