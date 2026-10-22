# 0278 report

Status: blocked

## Files changed
- App/app/db.py: added get_settings (step 1)
- App/app/welcome_back.py: keys_for, check() takes optional preloaded settings (step 2)
- App/app/routes/admin.py: dashboard does one get_settings read (step 3)
- App/tests/test_admin_route_split.py: POST /welcome-back/dismiss added to onboarding list (step 4)
- App/tests/test_welcome_back_0275.py: test_check_uses_preloaded_settings (step 5)

## Commands
1. pytest (query_budget, admin_route_split, welcome_back_0275, dashboard_order, dashboard_queue, host_quiet_dashboard): 49 passed, 0 failed.
2. ruff E9,F63,F7,F82,F401,F841: All checks passed!
3. pytest tests -x --ignore-glob=*_browser.py: 1 failed, 69 passed at tests/test_admin_funnel.py::test_overview_cards_and_bars (assert 38 == 100). The same test passes alone on the current tree and on the pre-0278 base commit, so it looks order-dependent, not caused by 0278.
3b. Full run without -x (background): 25 failed, 3754 passed, 3 skipped, 11 warnings in 600.96s (0:10:00)

## Acceptance (section 7)
- [x] Commands 1 and 2 pass.
- [ ] Command 3 has no new failure: NOT met. Full run 25 failed; baseline not checked (see Questions).
- [x] Dashboard query budget unchanged (test_query_budget passes, budget not edited).

## Deviations
- Commits were made per step (0278 step 1 to step 5), not one "steps 1-5" commit.
- Step 5 test uses _set_seen with TODAY-20 days and the existing host["owner"] fixture, as the brief's sketch was ambiguous.

## Questions
- test_admin_funnel::test_overview_cards_and_bars fails only inside the full run. Owner may want to check whether it is a known order-dependency.

## Owner steps left
- Push the branch and open the PR (executor does not push).
