# 1075-cont-1 report

Status: review

## Cause and fix

Inside `details` on `.entities-page` the hint is plain text (0543). The ancestor that did not shrink was `span.tip-tail` (added by app.js to keep the last word glued to the `?`): `inline-block` + `white-space:nowrap`. At 390 it measured scrollWidth 332 > clientWidth 272, and the label and field overflowed too. A fix of `white-space:normal` alone made it wrap, but by eye "(optional)" then dropped to its own line, and the hint sat 6 px in from the label because `.field-label-row .help-tip{display:inline-flex}` (line 1690) beats 0543's `details .help-tip{display:block}`. Final rule, scoped to this fold (line 369 unchanged):

```
body.v2 details.invoice-more .field-label-row .tip-tail{display:inline;white-space:normal}
body.v2 details.invoice-more .field-label-row .help-tip{display:block;margin-left:0}
```

## Files

`App/app/static/app2.css`, `App/app/templates/base.html` (`?v=20261110-1075b`), `App/tests/static_versions.json`, `App/tests/test_1075_fold_tip_browser.py` (new), `docs/tasks/screenshots-1075/` (22 PNG), this report, the brief (step 0 review), `docs/tasks/1075-report.md` (status).

## Commands (last line)

- `test_1075_fold_tip_browser.py` (REQUIRE_BROWSER): `3 passed`. Without the rule: `3 failed` (all three widths). Restored: `3 passed`.
- `test_static_versions.py`: `3 passed`.
- `test_layout_lint_browser.py`: `4 passed`, 0 skipped.
- `test_layout_lint_browser.py test_host_*.py test_design_guardrails_browser.py test_1075_fold_tip_browser.py`: `3 failed, 264 passed`, 0 skipped. Failures:
  1. guardrails `guest-new 390 Cancel 43 px`: the known, allowed finding.
  2. `test_host_ux_acceptance.py::test_every_page_family_fits_every_width_language_and_rail_state`: `guide` cs 390, `help-tip-btn` right 393 > 390.
  3. `test_host_flash_outcomes.py::test_browser_renders_saved_warning_as_sticky_amber`: the sticky warning toast never shows (30 s timeout).
  Items 2 and 3 also fail with the pre-cont-1 CSS and base.html (commit 1be39d49) restored, and the 1075 diff touches neither the guide page nor toasts. They are pre-existing, not caused by this branch. Not silenced and not fixed (out of scope).
- Shots script: 0 px sideways scroll on all 21 page/width pairs; fold summary 52 px; `clipped: False`, tip left 296 = fold content left. Cleanup FOREIGN KEY error (known).
- `context_lint.py`: `context lint: OK`.

## Per-page verdict (looked at by eye)

- payments-new-stay: 390: chips wrap cleanly, fields full width; 768: OK; 1280: OK.
- operator-add: 390: OK; 768: OK; 1280: OK, table and form aligned.
- operator-edit-fold-closed: 390: single chevron, rounded fold; 768: OK; 1280: OK.
- operator-edit-fold-open: 390: "Continue numbering from (optional)" on one line, hint wraps on 3 lines flush under it, inside the fold with the 16 px inset, input below it uncovered, border and corners intact; 768: OK; 1280: hint on 2 lines under its label, inside the fold.
- setup-property: 390: OK; 768: OK; 1280: OK.
- lock-tab: 390: OK; 768: OK; 1280: OK.
- smart-locks: 390: OK; 768: OK; 1280: OK.

(In full-page shots, the fixed mobile bottom nav shows mid-page: a capture artifact.)

## Deviations

- Step 1 rule differs from a pure `white-space:normal`; the reason is above (visual check).
- A second cache bust (`1075a` -> `1075b`) after the rule was revised.
- Items 2 and 3 above: for the orchestrator to log in known-issues or brief separately.

## Questions

None.
