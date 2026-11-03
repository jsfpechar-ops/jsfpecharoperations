# 0806 report: setup wizard v2 browser-test parity

Status: blocked (tool-call checkpoint reached; not committed, per owner instruction)

## Files changed
- App/app/static/app2.css: 5 rules appended inside the 0801 block (before the 0800 comment). Ported from host.css: calendar other-platform hide/show, choice-card radio accent-color, copy-button width/min-height.
- App/tests/test_onboarding_wizard_browser.py: `".ui-ph h1"` replaced by `".wiz-page h1.big"` (3 places, old-shell header).

## Test run (App/, wizard browser file)
Before: 46 failed. After: `33 failed, 52 passed in 113.24s`.
Fixed: calendar other-label group (test line ~1250) and the copy-button sizing group (line ~1421, partly).

## Remaining failures (not fixed)
1. test_deferred_police_journey_without_javascript (6): line 1169 needs the exit button below the h1 (header bottom <= exit y + 1). v2 head puts them side by side. Needs a layout decision: stack the head or reorder, which is a wizard-layout change.
2. test_phone_guest_sharing_and_clear_setup_actions (12): line 1421 copy-button widths differ (216 px). The 200px rule did not take effect; check the guest_link markup scope or an inline width.
3. test_choice_card_selects_from_anywhere (15): line 1451 lede colour rgb(85,85,79) must equal h1 colour rgb(28,28,26). Either give the h1 or lede the same colour in v2, or change this assertion (needs owner check).
4. test_choice_card_selects_from_anywhere (line 1563): outline style on the focused card is `none`, test expects `solid`. Needs a focus-visible rule for .ui-choice-card.

## Not run
docs/design lint, the 0800 setup subset, and the second test group in brief section 6.

## Deviations
Done: steps a, b (calendar part), c (selector only). Left: the rest of c, d, and all section 6 acceptance commands.
Owner steps left: none.
