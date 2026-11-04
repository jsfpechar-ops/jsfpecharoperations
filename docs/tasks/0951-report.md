# 0951 report

Status: blocked
Done: steps 1 to 5, step 6 partly (geometry test written, failing). Left: step 6 fix, step 7.

## Commits
- 9f9a2e91 step 1: Guest links markup (one input+Copy row each, one action row, `guest-copy-row` class; wizard `_components.html` onboarding-finish-* not touched).
- 59422b43 step 2: host.css `.guest-link-*` rules removed, app2.css 0951 block added.
- step 3: no file change, no commit. `test_0531_property_page.py` + `test_calmer_forms.py`: 18 passed.
- 6ef7a3d7 step 4: passport select and OCR checkbox markup and CSS.
- 7de7172f step 5: base.html `app2.css?v=20261104-0951a`, `host.css?v=20261104-0951a`. Manifest `--write` refused ("app2.css changed but still has ?v=20261104-0951a"); manifest NOT regenerated. Orchestrator: run `--write` after merge.
- step 6 (this commit): `test_guest_links_and_message_settings_geometry` added; CSS copy-button min-height and margin overrides.

## Test
`-k guest_links_and_message` at 390: FAILED. `#permalink` input y=1202.2, its `[data-copy=permalink]` button y=1208.2, both 44 px high. Button sits 6 px low; cause not found (margin:0 and align-self:center did not fix it).

## Deviations
- Steps 6 and 7 not complete: no screenshots, no report tests run, no docs lines (property add-on, decisions, status).
- Decision line for orchestrator: none yet.

## Next step
Open the 390 px computed style of `#permalink`'s parent `.guest-copy-row` and button (`getComputedStyle`: position, top, transform, margin-top, vertical-align). Fix in app2.css 0951 block so the button's y equals the input's y (within 4 px). Then rerun the `-k guest_links_and_message` test, do step 7.

## Update (second run)
Status: blocked
Fixed: 6 px Copy offset (cause: `.prop-sec :is(input…)` rule set margin-bottom:12px on the input; reset with `input:not([type=hidden])` in the 0951 block). Actions row was 307 px wide at 1280 (section is a 2-column grid from 1024 px): `.guest-link-top` now spans both columns. Regenerate tip check uses `.help-tip-btn`.
Geometry test `-k guest_links_and_message`: PASSED (390/768/1280).
Gate set (13 passed, 4 failed, 283 s): layout lint `test_every_host_page_passes_the_layout_lint` 80 findings (help-stranded 56, tight-side 24), not yet compared with a clean-tree baseline; `test_a_changed_static_file_has_a_new_key` and `test_the_manifest_is_current`: app2.css changed under key 20261104-0951a, manifest not regenerated (--write refused). Fourth failure not identified in the captured tail.
Screenshots: docs/tasks/screenshots-0951/automatic-messages-{390,768,1280}.png, viewed.
- 390: Link and PIN with Copy on the input row; action pills wrap to 3 rows; ? after each regenerate; settings stacked; checkbox 24 px with ? inline.
- 768: one column for links, two number fields side by side; passport select full width; checkbox row aligned.
- 1280: links full width; actions in 2 rows; numbers side by side.
- Finding: the note "A stay appears…" and the passport label sit with almost no gap at 768/1280 (grid row gap does not separate them). Not fixed.
Next step: decide the static key (bump to a new key or accept the orchestrator's regenerate), run `tests/test_static_versions.py --write`, identify the 4th failure, and check the 80 layout-lint findings against the base branch.

## Update (third run)
Status: blocked
Gate set (`test_host_property_controls_browser`, `test_0833`, `test_0541`, `test_layout_lint_browser`, `test_static_versions`, `test_0531`, `test_calmer_forms`): last full run 34 passed, 1 failed, 0 skipped; after the last CSS change the lint file alone: 3 passed, 1 failed (layout lint); property controls file 7 passed in the same run (geometry test passes).
Fixed: help-tip `?` moved inside the OCR `<label>` (lint `help-stranded` for `tight-side` was caused by 8 px copy gap: now 12 px). `test_property_and_operator_controls` asserted `data-copy="property-guest-url"`, moved to `overview-guest-url` by 0948 (base already broken). Geometry test checks checkbox against first text line. Cache key now 20261104-0951f, manifest current.
Lint still: 56 `help-stranded` (OCR `?` tip, 8 routes x 7 widths). The lint measures the tip against the label text span; with the tip inside the label it reports "on its own line" at 320 px, 41 px off. Not fixed.
Screenshots (docs/tasks/screenshots-0951/): 390 viewed: Copy on input row, actions wrap to 3 rows, ? inline; select text second line clipped by the select height (real finding, not fixed). 768/1280 viewed earlier: note and passport label gap now 24 px.
Next step: in app2.css, make the OCR tip not a lint-stranded element: move `help_tip('ocr_scan-help')` out of the `label` and right after the `<label>` in a `div.passport-scan-row` flex row whose label is `display:contents`-free, or give the span `display:inline` so the lint anchor is the text line; then the select `min-height` to fit two lines (`height:auto`), and rerun lint.
