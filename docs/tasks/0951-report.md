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
