# 0996 report

Status: blocked (signature dialog 390 px screenshot not captured; see Deviations)

## Files changed
- App/app/static/app2.css (grid span, v2 dialog/tabs/pad/checkline rules, mobile dialog rule)
- App/app/templates/_property_editor.html (top duplicate button removed, title sr-only)
- App/app/templates/_smart_locks_panel.html (setup heading sr-only)
- App/app/templates/base.html (app2.css key 20261107-0996b)
- App/tests/static_versions.json (regenerated)
- App/tests/test_host_property_controls_browser.py (0984 lock-off expectation: no button in state box)

## Commands (last lines)
- test_host_*, door_code, ttlock, smart_locks, geometry (chromium only, webkit not installed): 500 passed, 1 failed (0984, fixed in step 6), 0 skipped; 0984 rerun: 1 passed.
- test_static_versions.py + test_0282_signature_dialog_browser.py: 4 passed.
- test_layout_lint_browser.py + test_design_guardrails_browser.py: 15 passed, 0 skipped.

## Section 7
- [ ] Signature dialog: not verified visually (no screenshot taken).
- [x] Smart lock: state box has no button; "How it works" full width; checkbox above the single "Connect my lock" button (390 px screenshot /tmp/shots/0984-lock-off-390.png read).
- [x] Layout lint zero findings, 0 skipped.

## Observations
- 390: Smart lock section: state box without button, single "Connect my lock" under checkbox, "How it works" full width, no empty column.
- 768 and 1280: /tmp/shots/0984-lock-off-768.png and -1280.png not opened.

## Deviations
- Webkit engine not installed in this sandbox; ran with `-k "not webkit"`.
- Step 2 appended rule overrode the existing max-width:599px dialog rule (0282 canvas 318 < 340); added the mobile rule again; key bumped twice (0996b).
- Step 6 edited 0984 test expectation (brief allowed the update).
- Dialog 390/768/1280 screenshots not taken: no harness opens the dialog; Playwright script not written (call budget).

## Owner steps left
- None before review; the dialog screenshots remain to be taken.
