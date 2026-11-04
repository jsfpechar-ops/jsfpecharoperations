# 0949 report: paste reminder removed from the dashboard

Status: in progress. Steps 1-7 done, step 8 (part B: "You are ready" card only with one property) pending or in progress, see the commit list.

## Commits (branch claude/friendly-albattani-ndmdji, not pushed)
- Step 1: 4a6f70a9 (needs_you.py, admin.py, dashboard.html, test_needs_you_0240.py, brief Files line)
- Step 2: df76efb0 (dashboard.html paste branch)
- Step 3: 7e2e72fb (host_i18n.py, host_vi_i18n.py: 24 dead keys)
- Step 4: b5dacb6b (workflow.css, app2.css, base.html ?v=, static_versions.json, catalog.json)
- Step 5: 8dbe81c4 (test_paste_check_0233.py rewritten, test_workflow_0230.py tuple, test_host_quiet_dashboard_browser.py block)
- Step 6: 5a58b88c (screenshots in docs/tasks/screenshots-0949/)
- Step 7: this commit (docs, `.needs-you-how` selector removed: grep showed no other use)

## Tests (0 skipped in all browser runs)
- test_needs_you_0240.py: 7 passed
- Step 5 set (paste_check_0233, workflow_0230, workflow_strip_0232, wizard_try_it_0884, property_health_0244): 20 passed
- test_host_quiet_dashboard_browser.py + test_layout_lint_browser.py + test_static_versions.py: 9 passed, 0 skipped
- test_host_i18n.py: 3 failed, 11 passed. Same 3 fail on a clean tree ("no such table: apartment"). Known, not caused by this change.

## Assertions changed
- test_paste_check_0233.py: two tests replaced by test_dashboard_never_shows_the_paste_reminder (EN and CS).
- test_workflow_0230.py: "workflow.paste.title" removed from the key tuple.
- test_needs_you_0240.py: unused arg removed; the Studio paste-line assertion removed (orchestrator decision). The function name still says "paste"; rename left for later.
- test_host_quiet_dashboard_browser.py: paste_line block replaced by a count-is-zero assertion.

## Per-width notes (screenshots in docs/tasks/screenshots-0949/)
- 390: viewed. Single-property dashboard: "2 things need you today", no paste card, cards full width, no overflow.
- 768 / 760: viewed (orchestrator). Needs-you cards stack full width, no paste card, no horizontal overflow.
- 1280: viewed (orchestrator). List rows aligned, no paste card, Today table intact.

## Design-system checklist (docs/design/design-system.md)
- [x] Page extends host_page (template change only removed a block)
- [x] Header action row: untouched
- [x] No Save bar or heading change: untouched
- [x] No fine print change: untouched
- [x] Spacing: untouched
- [x] 390/768/1280 checked as above, no sideways scroll
- [x] test_layout_lint_browser.py green, 0 skipped; screenshots opened
- [x] CS and EN keys removed together
- [ ] CI watched to the end (no PR yet)

## Deviations
- Step 1 grep expected no other callers; test_needs_you_0240.py had two. Fixed per orchestrator decision.
- Step 3 grep also matches workflow.short.paste (not dead); kept.
- Step 7 ran context_lint: decisions.md is ~2253 tokens, cap 2200. Cause: the new decision line. The 90-day archive rule moves nothing (oldest line 2026-10-06). Needs a split or compaction decision from the orchestrator. Not done here: decisions.md is append-only.
- status.md link to this report resolves once this file exists.

## Open question (owner)
- Should anything replace the reminder (for example one calm line on the property page)? Not built; the property-page health row covers it.

## Owner steps left
- None for steps 1-7. Merge through scripts/merge-pr-on-green.sh only after CI is green.
