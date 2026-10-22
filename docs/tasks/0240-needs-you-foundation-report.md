# 0240 report: "What needs you", foundation

Status: review

## Files changed

- `App/app/needs_you.py` (new, step 1)
- `App/app/templating.py` (step 2)
- `App/app/host_i18n.py`, `App/app/host_vi_i18n.py` (steps 3-4)
- `App/app/static/workflow.css` (step 5)
- `App/app/templates/base.html` (step 6)
- `App/tests/static_versions.json` (step 6b, manifest refresh written by `test_static_versions.py --write`)
- `docs/design/catalog.json` (step 7)
- `App/tests/test_needs_you_0240.py` (new, step 8)

## Commands (last lines)

- Step 1: `python -c "import app.needs_you"`: no output, no traceback.
- Steps 3-4: `pytest tests/test_alert_stack.py tests/test_host_i18n.py`: `27 passed`.
- Step 6: `pytest tests/test_alert_stack.py tests/test_static_versions.py`: `1 failed, 15 passed`. Step 6 was committed while red, because my shell chain did not stop on the failure. Fixed by step 6b.
- Step 6b: `pytest tests/test_alert_stack.py tests/test_static_versions.py`: `16 passed`.
- §6.1: `pytest tests/test_alert_stack.py tests/test_needs_you_0240.py tests/test_host_i18n.py tests/test_static_versions.py tests/test_design_lint.py`: `39 passed, 2 warnings`.
- §6.2: `python3 scripts/context_lint.py`: `context lint: OK` (warnings only: catalog.json and test_wp28_ui_sweep.py are named by other open briefs; 14 commits touched App/ since last status update).

## Deviations

- Step 6 red commit (`0240 step 6`), fixed by `0240 step 6b: refresh static manifest`, approved by the orchestrator. The brief's §3 did not list the manifest; added on the orchestrator's instruction.
- Step 6b and step 8 ran tests with `tests/test_alert_stack.py` first, per session notes.

## Questions

None.

## Owner steps left

None.
