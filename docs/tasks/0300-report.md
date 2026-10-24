# 0300 report

Status: review

## Files changed
- App/app/templates/_components.html (copy_button macro: secondary bordered button, `copy-btn` class, optional label)
- App/app/templates/apartments.html (two hand-written copy buttons replaced by copy_button; import added)
- App/app/static/host2.css (0295 block: grid-column -2 / -1, payer 4+auto row; 0300 copy-btn block appended)
- App/app/templates/base.html (host2 key 20261024-0300)
- App/tests/static_versions.json (regenerated with --write)
- App/tests/test_0300_copy_button.py (new, 2 tests)

## Commands
- `.venv/bin/python -m pytest tests/test_0300_copy_button.py tests/test_host_invoice_items_browser.py tests/test_host_controls_browser.py tests/test_static_versions.py tests/test_design_lint.py tests/test_0285_rows_browser.py -q --tb=short -rs 2>&1 | tail -30`
  - `16 passed, 1 warning in 33.90s` (0 skipped)
- `.venv/bin/python ../scripts/design_lint.py 2>&1 | tail -3`
  - `design lint: OK`
- `python3 scripts/context_lint.py 2>&1 | tail -3`
  - `ERROR docs/tasks/0300-copy-button-and-payer-items.md: missing section '## 8. Stop and ask'` (the brief file itself; not in brief §6, not changed)

## Acceptance (brief §7)
- [x] Every icon copy button renders through copy_button (apartments.html uses it; no `class="btn-icon" data-copy=` left)
- [x] Invoice items browser test passes

## Deviations
- Commits per step (`0300 step k`, plus `0300 base host2 key`, `0300 static versions`) instead of one commit, per executor rule (cutoff safety).
- No PR opened: the task is to commit only, never push.
- Screenshots skipped per the owner's instruction.
- Remaining unchecked: nothing in brief §7.

## Questions
- Step 3 sets Remove to `grid-column: -2 / -1`, as the brief says. For a payer, that lands on track 4 (the VAT column) of a 5-track grid, not on the auto track. The tests pass, but the visual layout was not checked. Owner should look at a payer invoice at 760 px.

## Owner steps left
- Review the payer invoice layout at 760 px and the copy button in Settings or Properties.
- Push and open the PR yourself: `git push -u origin claude/project-thread-1am307`.
