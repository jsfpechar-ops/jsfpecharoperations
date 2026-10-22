# 0240 report: "What needs you", foundation

Status: blocked

## Files changed

- `App/app/needs_you.py` (new, step 1)
- `App/app/templating.py` (step 2)
- `App/app/host_i18n.py`, `App/app/host_vi_i18n.py` (steps 3-4)
- `App/app/static/workflow.css` (step 5)
- `App/app/templates/base.html` (step 6)

Not started: step 7 (`docs/design/catalog.json`), step 8 (`App/tests/test_needs_you_0240.py`).

## Commands (last lines)

- Step 1: `python -c "import app.needs_you"`: no output, no traceback.
- Steps 3-4: `pytest tests/test_alert_stack.py tests/test_host_i18n.py`: `27 passed, 2 warnings`.
- Step 6: `pytest tests/test_alert_stack.py tests/test_static_versions.py`: `1 failed, 15 passed`.
  Failing test: `test_the_manifest_is_current`. Its message: `run: .venv/bin/python tests/test_static_versions.py --write`. The manifest records the sha256 of `workflow.css`, which step 5 changed.

## Deviations

- Done: steps 1 to 6. Left: the static manifest (see Questions), steps 7 and 8, the §6 commands and the report's acceptance.
- Mistake: step 6 was committed (`0240 step 6`) while `test_static_versions.py` was failing, because my shell chain did not stop on the failure. The commit is local only and not pushed. Fix it in the next session by running the manifest write and amending or adding a commit.

## Questions

- Step 6 needs `App/tests/test_static_versions.py --write` to refresh the manifest, which changes a file outside §3. I stopped instead of running it (brief §8). Confirm that the manifest refresh is allowed, then run:
  `cd App && .venv/bin/python tests/test_static_versions.py --write` and then `.venv/bin/python -m pytest tests/test_static_versions.py -q --tb=short 2>&1 | tail -5`.

## Owner steps left

None.
