# 1007 report

Status: blocked

## Stopped at step 7 (brief §8)

Step 7 says: "If a helper is absent, STOP rather than inventing fixtures." The helpers it names are not in `App/tests/test_billing_self_service.py`. They exist in `App/tests/test_billing_order.py` (`host` fixture line 24, `_set` line 43) and `login_as` in `App/tests/conftest.py` line 155. `test_billing_order.py` is not in brief §3, so I did not edit it.

Question for the owner: put the new test in `test_billing_self_service.py` with copied `host`/`_set` fixtures, or allow the test in `test_billing_order.py`? Then the executor can run steps 7 to 11.

## Files changed (local commits, nothing pushed)

- `App/app/routes/billing.py` (step 1): `upgrade` context added.
- `App/app/host_i18n.py` (step 2): 8 keys, EN and CS.
- `App/app/templates/billing_plan.html` (step 3): Change block replaced; `billing-change-row` count 0.
- `App/app/static/app2.css` (step 4): 1007 block appended.
- `App/app/templates/base.html`, `App/tests/static_versions.json` (step 5): `app2.css` bumped to `20261108-1007`, sha256 recomputed.
- `docs/design/catalog.json`, `docs/design/design-system.md` (step 6): six class names; paragraph before "Checklist for new pages:".

## Commands run

- `python3 -c "import app.routes.billing"` (from `App/`): no output.
- `.venv/bin/python -m pytest tests/test_host_i18n.py -q --tb=short -x 2>&1 | tail -30`: `14 passed, 1 warning in 1.46s`.
- `python3 scripts/design_lint.py 2>&1 | tail -30`: `design lint: OK` (run twice).
- `python3 -c "import json;json.load(...)"` on catalog.json and static_versions.json: no error.

Not run: steps 8 (billing and layout-lint tests), 9 (screenshots), 10 (copy to `/mnt/project-files/ux-shots/wolt/`), 11 (context_lint). The rendered `/predplatne` page has not been checked.

## Deviations

- Steps 1 to 3 edits were applied with a small Python script using the brief's exact text, not the Edit tool. Temporary scripts were in `$HOME` and deleted.
- Each step is a separate commit (`1007 step k`); steps 5 and 6 share one commit.
- Brief §10 asks for `git add` of 1006 files. Nothing from 1006 was uncommitted (`git status` showed only the untracked `docs/tasks/1008-...` file), so there was nothing to add.
- Executor guide says to open one PR. Brief §10 says no PR, so none was opened.

## Owner steps left

- Decide the test location (see question above).
- Then rerun the executor for steps 7 to 11, or run them yourself with the commands in brief §6.
- Push and PR are not done: `git push` is for the owner after review.
