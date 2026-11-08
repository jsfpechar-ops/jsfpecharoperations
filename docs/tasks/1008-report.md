# 1008 report (executor: Haiku 5.5)

Status: blocked

## Files changed
- App/app/static/app2.css: 1008 block appended at the end (CSS only, scoped under `body.v2 .form.prop-form-single`)
- App/app/templates/base.html: app2.css `v=20261108-1007` to `20261108-1008`
- App/tests/static_versions.json: regenerated with `--write` (51 files)
- docs/design/pages/properties.md: one bullet under "Property detail"
- docs/tasks/1008-ux-property-editor-wolt.md: Status line only (todo to blocked)
- docs/tasks/1008-report.md: this report

## Commands
- `python3 scripts/design_lint.py`: `design lint: OK`
- `python3 scripts/context_lint.py`: `context lint: OK` (WARN lines are pre-existing)
- `pytest tests/test_static_versions.py tests/test_0534_property_page_v2.py tests/test_0952_lock_section.py tests/test_copy_cleanup.py tests/test_remove_legacy_actions.py`: `36 passed in 2.71s`
- Browser group 2 (8 files, `UBYHOST_REQUIRE_BROWSER=1`, `-rs -x`): `1 failed, 25 passed in 40.65s`
  - FAIL: `tests/test_0541_property_page_phone_browser.py::test_0948_strip_shares_form_edges_and_columns` at 768 px: `.prop-strip` x=20, `.form` x=24 (tolerance 1).
  - Cause: the 720 px column is centred, so at 768 px `.form` no longer shares the left and right edges of the full-width `.prop-strip`. The test pins those edges to match.
- Not run: browser group 3, layout lint (step 5 last command), screenshots (step 6), copies to /mnt/project-files/ux-shots/wolt/.

## Deviations
- Stopped at the first failing browser test (brief section 8). Not fixed, and no test edited.
- Commit trailer: Co-Authored-By Claude Haiku 5.5 (system attribution), not the Sonnet line in the brief.
- One local commit, not pushed.

## Decision needed (orchestrator or owner)
Pick one:
1. Also cap `.prop-strip` at 720 px (touches the strip, outside the brief's editor scope).
2. Drop the `max-width:720px` on `.form.prop-form-single` below 768 px, so the column stays full width where the strip is full width.
3. Change test_0948 to allow the centred column (test change, owner approval).

## Owner steps left
None until the decision above. Nothing pushed. No PR opened.
