# 0718 report (executor)

Status: blocked. Session stopped at the 25-call checkpoint after steps 1-3 and part of step 5. Steps 4 and the screenshots are left.

## Commits (branch task/0718-v2-phone-shell, not pushed)
- 97fbd69, ee410ad: steps 1 and 2 (tab bar, Menu route and template, test_0718_menu_page.py)
- 2667fd9: step 3 (phone classes below 1024 px)
- 7b5ac9d: merge of the Overview work (0717)
- 86a6a9b: step 3 fix. Removed the phone-block variable redefinitions. The undefined variables --acc2, --soft and --accent now use the app2 :root values (--acc-text, #f6f6f4, --acc). Phone `.btn` colour is pinned to #fff. `.btn.ghost` gets its own #efefeb background (the phone accent background leaked onto it, which caused the 3.72 contrast finding). The dashboard work card has margin 0 and overflow-x:auto below 1024 px.
- Step 5 part (this commit): app2.css key bumped to 20261101-0718 in base.html, static_versions.json regenerated, menu.html added to V2_TEMPLATES in scripts/design_lint.py.

## Test results
- test_a11y_guard_browser.py: 4 passed, 0 skipped. The 3.72 contrast finding is gone.
- Brief section 6 set, run once before the key bump: 8 failed, 46 passed, 0 skipped. Only the tail was visible. Failures seen:
  - test_0710_v2_mockup_match_browser.py, overview at 390 and 768: `text 11px: <a class="tab on"> "Today"` (also Calendar, Stays, Properties, Menu) and `.side is not visible` (the old check that step 4 replaces).
  - test_static_versions.py: `app2.css changed but still has ?v=20261101-0717c`. Fixed by the key bump; test_static_versions.py now passes (3 passed).
- The full section 6 set was not re-run after the key bump.
- design_lint.py: OK. context_lint.py: OK.

## Left for the next session
- Step 4 (test helper): PHONE_MOCKUP, PHONE_WIDTHS, phone_view/phone_selectors, SELECTOR_ALIASES, the box-metric comparison, the menu PAGES entry, the overview phone entry, and the new below-1024 geometry checks in App/tests/v2_mockup.py and App/tests/test_0710_v2_mockup_match_browser.py. Not started.
- Tab labels are 11 px and fail the 12 px text rule. Decide: 12 px tab labels, or a missing_ok entry with a reason. Owner or orchestrator decision.
- Step 5 screenshots (menu-390, overview-390, overview-768) in docs/tasks/screenshots-0718/, then Read them. Not started.
- Dashboard table at 390 px: the card scrolls inside itself now. Brief 0719 replaces the table.

## Deviations (listed by the previous session, not verified by this session)
- nav_badge is never set.
- The nav.today key is used.
- Kalendar is never marked on.
- The Help row goes to /guide.
