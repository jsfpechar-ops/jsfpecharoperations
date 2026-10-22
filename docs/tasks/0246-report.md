# 0246 report: "What needs you" review fixes

Status: review

## Commits (branch claude/project-thread-0io75h, not pushed)

- `eedfc39 0246 step 1`: needs_you.py skips the setup line for the sample property; test fixture fix (see Deviations).
- `78169c3 0246 step 2`: dashboard.html, how-to moved inside the paste line; card-level block removed.
- `1f0f6f3 0246 step 3`: workflow.css rule, base.html key `20261022-0244` to `20261022-0246`, static_versions.json refreshed.
- `9a61a68 0246 step 4`: new sample-property test, browser test lines replaced.

## Files changed

App/app/needs_you.py, App/app/templates/dashboard.html, App/app/static/workflow.css, App/app/templates/base.html, App/tests/static_versions.json, App/tests/test_needs_you_0240.py, App/tests/test_host_quiet_dashboard_browser.py, docs/tasks/0246-report.md.

## Commands (last lines)

- Step 1: `24 passed, 1 warning in 2.64s`
- Step 3 (after manifest write): `18 passed, 1 warning in 2.88s`
- Step 4: `22 passed, 1 warning in 43.86s` (no skips)
- Brief 6.1: `35 passed, 1 warning in 3.69s` (no skips)
- Brief 6.2 (screenshots refreshed): `16 passed, 1 warning in 56.91s` (no skips)

## Checklist (section 7)

- [x] Section 6 commands 1 and 2 pass with 0 skipped.

## Screenshot

390 px, open state: /mnt/project-files/foolproof-round2/dashboard/dashboard-vi-390-open.png. The "Cách dán" how-to sits inside the paste line, under its sentence. The fixed bottom tab bar overlaps the cards in this capture (it is the page's sticky nav at scroll position, not part of this change).

## Deviations

- Step 1: `test_setup_and_paste_lines_name_the_property` (existing test) failed with `KeyError: 'legal_entity_id'`. Under the mock environment, `demo.is_demo_apartment` reads `legal_entity_id` for non-demo names, and that test's apartment dict lacked the field. Fixed by adding `"legal_entity_id": None` to that fixture's apartment dict. `demo.py` was not changed.
- Step 3: the cache key was `20261022-0244` as the brief expected, so no other key was changed.
- Step 4a: no import had to be added; `needs_you` and `date` were already imported.

## Questions

None.

## Owner steps left

None. Nothing pushed; no PR opened.
