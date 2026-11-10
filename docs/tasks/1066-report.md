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

## Continuation 2
- Cause: the 1066 desktop `::before` (44 px box on a 24 px help dot) widened the scroll area of `#settings-group-phone` descendants (`assert 6 == 0`). Rule deleted; phones keep 44 px.
- `test_static_versions.py`: 3 passed. `test_input_attributes_1066.py`: 7 passed, 0 skipped. `test_push_settings_browser.py` + `test_layout_lint_browser.py`: first run 14 passed, 1 failed (`double-primary` on `cleaning@1280`, a page this change does not touch); rerun of the lint file: 4 passed, 0 skipped. Push-settings tests (incl. 4 alerts-row params) passed.
- settings (alerts-on, `settings-alerts-<w>.png`): 390: help dots drawn about 44 px (the 1023 rule), label "Urgent alerts on this device" wraps over 3 lines, no overflow; 768: dots about 44 px, one line, buttons right; 1280: dots 24 px, one line, no overflow.
- property-new (`property-new-<w>.png`, many inline tips): 390: small round "?" beside every label, single column, no overflow; 768: same, "Copy from another property" top right; 1280: two-column form, tips inline, "After you create it" side card, no overflow.
- Deviations: reviewer corrections applied (alerts-on settings shots, 768 from a scratch test deleted afterwards, property-new instead of stay-fees). Reviewer said the dot is 24 px at every width; the shots show about 44 px at 390 and 768 (the `max-width:1023px` rule), 24 px at 1280. Cleaning lint failure was flaky.
- Owner: CI must rerun on #860.
