# 1066 report

Status: review

First session: 6 templates, app2.css, base.html, static_versions.json, test_input_attributes_1066.py, guest shots; cmd 1 (647 passed), cmd 4 (4 passed). Details in git history.

## Continuation 1

- Cmd 2 (host row, fresh venv py3.13, Playwright 1.63.0, Chromium 153): first run `-x` stopped at `test_host_flash_outcomes.py::test_browser_renders_saved_warning_as_sticky_amber` (fails twice; same failure on base 0d851ca4). Rest rerun with that test deselected: 728 passed, 1 failed, 2 skipped (not identified), 1 deselected. The 1 failed is `test_host_ux_acceptance.py::test_every_page_family_fits_every_width_language_and_rail_state` (guide, cs, 390: help-tip-btn "past right edge"); same on base.
- Guardrails (CI env, no -x): branch and base both `1 failed, 10 passed`, same id: `guest-new 390 open: tap-target-small a.ui-btn.ui-btn-quiet "Cancel" 43 vs 44`. Identical on 0d851ca4, so 1066 does not cause it. File is #73 in CI list, shard 1; CI run 42699276863 on main 0d85: shard 1 372 passed, 0 failed, 0 skipped. Local: Playwright 1.63.0, Chromium 153.0.8010.12, 119 fonts; CI uses the playwright:v1.63.0-noble image. So it is local-environment (probably fonts); exact cause unproven. No code change.
- Cmd 3 rest: test_static_versions + test_host_i18n 17 passed, 0 skipped.
- Wizard IČO (docs/tasks/screenshots-1066/wizard-ico-390.png, no-entity host): "Company ID (IČO) *" label with red star, full-width field with grey 12345678, "Fill from register" button below; no overflow. The bottom tab bar is drawn mid-image (full-page capture artefact) and covers the button's lower edge.
- Screenshot dirs 0402, 0451, 0410, 0957, 0896 and 0102-evidence restored, not committed.
- Owner: open PR; guardrails and flash/ux failures are environment, CI is the judge.
