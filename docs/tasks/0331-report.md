# 0331 report: Havel gap list on /admin/operations

Status: review. Branch task/0331-havel-gap-list.

Commits: 57e9119 (step 1 engine), 1e945c8 (step 2 route), b59f8d7 (step 3 template), e5fa9e2 (step 4 i18n en/cs/vi), 643f585 (steps 5-6 tests, guardrail route).

Files: App/app/havel.py, App/app/routes/admin_accounts.py, App/app/templates/admin_operations.html, App/app/host_i18n.py, App/app/host_vi_i18n.py, App/tests/test_havel_gap_list.py (new), App/tests/test_havel_gap_list_browser.py (new), App/tests/test_design_guardrails_browser.py, docs/tasks/screenshots-0331/admin-havel-390.png (new).

Tests:
- test_havel_gap_list.py, test_havel_gap.py, test_admin_operations.py: 12 passed.
- test_havel_gap_list_browser.py: 1 passed, 0 skipped. Guardrail `-k admin`: 2 passed, 0 skipped.
- Required suite (tests/test_havel*.py, test_admin*.py, test_design_guardrails_browser.py, test_a11y_guard_browser.py): 125 passed, 0 skipped.
- test_host_i18n.py run alone: 3 failed ("no such table: apartment", the known unrelated issue). Passes in other combinations.
- context_lint: OK.
- design_lint: FAIL on App/app/templates/_havel_thread.html "havel-not-helped" (from 0320, not touched here). Not in this change's files.

Screenshot (390 px): the box shows three numbered steps; the spend line and the gap table stack with labels. The top row reads lowercase "kde je dopis od policie" because the newest wording wins. The fixed mobile tab bar sits over the second row in the element capture; this is the fixed nav, not the section.

Deviations:
- Brief anchors were from f4c76d7; origin/main is d4673ec. Anchors checked with grep and matched (havel_gap is migration 0020).
- Added `from collections import Counter` to havel.py.
- Dropped `class="ops-havel-how"` (not in the design catalog, design_lint T3) and the `ui-mono` class on the page cell (stacked wrap of "stays").
- Commit trailer: the brief says Opus 5.5; the session attribution says Haiku 5.5. I used Haiku 5.5, which is the model that ran this brief.
- Browser chromium path is 1243 (per the orchestrator rule), not 1194 from the brief.

Open questions: none blocking. Next gap-list row text may show a lowercase newest wording (cosmetic).
