# 1007 report

Status: blocked

## Done

- Steps 1 to 6 committed locally: route `upgrade` context, 8 EN and CS keys, Change block replaced, app2.css 1007 block, cache bump to `20261108-1007` (base.html and static_versions.json), catalog and design-system 5b.
- Step 1 bug fixed in a second commit: my first insert dropped the `quote = billing_order.quote(...)` line, which caused a NameError on /predplatne. Restored.
- Step 7: test `test_the_change_card_shows_the_real_upgrade_and_keeps_the_forms` appended to `App/tests/test_billing_order.py` (per coordinator decision; uses its `host` and `_set`).

## Commands

- `.venv/bin/python -m pytest tests/test_billing_self_service.py tests/test_billing_order.py tests/test_0416_plan_page_browser.py tests/test_host_i18n.py -q --tb=short -x -rs`: `47 passed, 1 warning`, no skips listed.
- `python3 scripts/design_lint.py`: `design lint: OK`.
- `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x -rs` (step 8): started in background, output still empty after about 15 minutes. NO RESULT YET. Output file: /tmp/claude-0/-home-user-jsfpecharoperations/19736c2f-d76f-5062-a390-a7e0df73a878/tasks/bze6mvc2r.output
- `python3 scripts/context_lint.py`: not run (it was chained after the layout test).

## Not done

- Step 9: no screenshots taken (390/768/1280). Nothing was looked at.
- Step 10: nothing copied to `/mnt/project-files/ux-shots/wolt/`.
- Step 11 completed only in part (this report). Brief status not changed.
- Tool-call cap reached (30), so the executor stopped here.

## Deviations

- Steps 1 to 3 edited with a Python script using the brief's exact text, not the Edit tool.
- Each step is its own commit (`1007 step k`); steps 5 and 6 share one.
- No PR, no push (brief §10).

## Owner steps left

- Read the layout-lint result, then run `python3 scripts/context_lint.py` from the repo root.
- Take the 390/768/1280 screenshots of /predplatne and review them (UX gate, rule 10) before any merge.
- Run `git push` yourself after review. No push was done here.
