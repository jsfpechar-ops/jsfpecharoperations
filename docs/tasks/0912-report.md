# 0912 report

Status: review (changes in the working tree, not committed, no PR, per the parent's instruction)

## Files changed
- `App/app/templates/_components.html`: `onboarding_finish` macro (title row with help_tip, tips list removed, ui-btn classes, data-layout="v2"). Strip markup untouched.
- `App/app/templates/dashboard.html`: line 96, `ph-hide` removed.
- `App/app/static/app2.css`: block `/* 0912: finish card (v2) */` appended, plus a small `.onboarding-finish-intro` grid rule.
- `App/app/templates/base.html`: `app2.css?v=0912`.
- `App/app/reporting.py`: `month_summary` is one query over overlapping stays; reported = their guests with SENT.
- `App/tests/test_0520_overview_today.py`: new `test_month_summary_counts_reports_on_the_same_stays`.
- `App/tests/test_onboarding.py`: line 252 "edit host message" replaced by a check of the primary communication link href (coordinator answer).
- `App/tests/layout_lint.js`: section 11 (button-overlap, button-wraps, tight-row).
- `App/tests/test_layout_lint_browser.py`: BAD_PAGE row and expected rules; `test_the_finish_card_passes_the_lint`.
- `App/tests/static_versions.json`: regenerated (coordinator answer).
- `docs/design/pages/dashboard.md`: 3-line note.
- Created ignored `App/.venv` (requirements, requirements-dev, playwright==1.63.0 as CI pins).

## Commands (last lines)
- Step 3 rows (onboarding, dashboard order, wp28, static): `34 passed` after the fixes.
- `pytest tests/test_0520_overview_today.py tests/test_dashboard_order.py tests/test_onboarding.py`: `27 passed`.
- `pytest tests/test_layout_lint_browser.py` (browser env set): `3 passed`, 0 skipped.
- Host pages row `tests/test_host_*.py tests/test_host_geometry.py`: `206 passed`, 3 failing on re-run (see Deviations).
- Onboarding row: `316 passed`, 0 skipped.
- Design guardrails: `11 passed`. Mockup match: `183 passed`, 0 skipped.
- Static row: `16 passed`. wp28 + 0520: `17 passed`.
- `python3 scripts/context_lint.py`: `context lint: OK` (warnings only, pre-existing).

## Section 7
- [x] 1280: link and PIN as bordered rows, Copy at right, three actions on one line, no bullets, tips behind "?".
- [~] 390 and 768: card shows, actions stacked full width at 390; at 768 the bottom nav hides the actions in the screenshot (fixed nav, not a card bug).
- [x] Strip styled as one row with its link.
- [x] month_summary one query; reported is a subset of guests; new test green.
- [x] Lint flags the fixture; finish-card test green; layout lint 0 skipped.
- [x] Six PNGs in `/mnt/project-files/dashboard-finish/`, each opened once.
- [~] Step 8 rows: all green except the pre-existing failures below.

## Screenshots
- finish-390: link and PIN rows, Copy full width under each code (wrap), Open/Preview/Skip stacked; actions sit under the fixed bottom nav in the capture. Code wraps mid-word (overflow-wrap:anywhere).
- finish-768: rows and Copy at right, actions in one line area behind the bottom nav.
- finish-1280: clean; two rows, Copy right, three actions on one line, quiet Skip link.
- strip-390/768/1280: one bordered row with "Setup is done... Show link"; no overlap. Month line 0 guests, 2 nights, 0 reported (correct for the fixture).

## Deviations
- The step 2 fixtures needed `width:110px;white-space:normal` on the lint row's second link (nowrap from app.css otherwise prevents button-wraps).
- Pre-existing failures, verified on unmodified HEAD in a temporary worktree (removed): `tests/test_host_fee_navigation.py::test_frozen_report_order_and_forms` and `tests/test_host_ux_acceptance.py` (2 tests) fail on HEAD too. Not fixed; out of scope.
- `tests/test_host_feedback_browser.py::test_host_copy_feedback_truth_and_geometry` failed once in the row run and passed on its own re-run; treated as flaky.
- Browser tests rewrite committed evidence PNGs under `docs/tasks/0102-evidence/` and `docs/tasks/screenshots-0410/`. Reverted with git checkout; keep them out of the commit.

## Questions
- Fix the pre-existing stay-fees and ux_acceptance failures in a separate brief?
- The 390 Copy buttons wrap under each code; accept, or make them sit beside the PIN?

## Owner steps
- Commit and open the PR (not done here).
- After deploy: open the dashboard on phone and laptop, check the card and the month line.
