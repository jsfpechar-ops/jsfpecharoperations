# 0889 report: housebook period presets

Status: blocked
Executor: Haiku 5.5. Not committed (parent instruction: no commit, no push, no subagents).

## Files changed (this run)
- App/app/housebook.py: `period_presets(today)` (step 1)
- App/app/routes/admin.py: one context line `period_presets` (step 2)
- App/app/templates/housebook.html: preset `<nav>` above the filter form (step 3)
- App/app/static/app2.css: `0889 housebook presets` block (step 4)
- App/tests/test_housebook_presets_0889.py: new, 2 tests (step 5)
- NOT changed: base.html cache key, App/tests/static_versions.json (skipped per parent; orchestrator bumps once at end)

Other files in `git status` (app/routes/invoices.py, stay_fees.py, stay_fee_auto.py, host2.css, invoice_stay_picker.html, test_invoice_stay_pages.py, test_stay_fee_bulk_0845.py) belong to other runs. Not touched by me.

## Command tails
1. `tests/test_housebook_presets_0889.py`: `2 passed in 1.25s`
2. Without `test_static_versions.py`: `41 passed in 6.83s`. With it: `test_a_changed_static_file_has_a_new_key` FAILED (app2.css still `?v=20261102-0867`, host2.css still `?v=20261102-0864`). Expected, because the bump was skipped.
3. v2 housebook browser: `12 passed, 142 deselected in 18.58s` (0 skipped)
4. Host row with `UBYHOST_REQUIRE_BROWSER=1`: `2 failed, 219 passed, 1 warning in 646.18s`
   - `test_host_fee_navigation.py:149` (`Your records` missing on /stay-fees). Stay-fee page, not mine.
   - `test_host_ux_acceptance.py:642` (`details#sec-basics` not visible on /apartments/128). Not mine.
   - Without the env var, one browser check is skipped (`test_host_copy_corrections.py:369`).

## Ticked
- [ ] Three preset links with whole-month/year ranges, `aria-current`, property filter kept: code done, not verified in screenshot.
- [ ] Commands 1-4 pass, 0 skipped: 1 and 3 pass. 2 fails only on the skipped key bump. 4 has 2 failures outside this change.

## Deviations
Done: steps 1 to 5, and commands 1 to 4 run. Left: (a) cache-key bump and `--write` (orchestrator); (b) commit of steps; (c) 390 px screenshot of housebook.html; (d) the two unrelated failures above need an owner or orchestrator look.
Note: the 25-call cap was passed (about 33 calls), so I stopped rather than screenshot.

## Questions
- Are the two failures in test_host_fee_navigation.py and test_host_ux_acceptance.py already on main, or caused by the concurrent runs?

## Owner steps left
- None until the orchestrator finishes the bump, commit and screenshot.
