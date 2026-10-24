# 0295 report: review polish

Status: review

## Files changed
- App/app/static/host2.css: steps 1-3 (invoice item rows at <=850px and <=420px containers; lookup button height; Open border to --coral-500)
- App/app/templates/base.html: host2 key 20261024-0294 -> 20261024-0295
- App/tests/static_versions.json: regenerated with `--write` (35 files)

## Commands
- `.venv/bin/python tests/test_static_versions.py --write` -> wrote App/tests/static_versions.json (35 files)
- `.venv/bin/python -m pytest tests/test_invoice_*.py tests/test_0293_invoice_form.py tests/test_0291_open_buttons.py tests/test_static_versions.py tests/test_design_guardrails_browser.py -q --tb=short -rs` -> `114 passed, 1 skipped, 1 warning in 44.25s`
  - The 1 skip: tests/test_invoice_autofill.py:300, "set UBYHOST_SHOTS_DIR to capture acceptance screenshots" (screenshot-only test, skipped by design; screenshots were skipped per brief).

## Acceptance
- [x] Steps 1-4 done; tests pass (114 passed, 1 skipped by design).

## Deviations
- None. Screenshots not taken (per executor instructions).

## Owner steps left
- None.
