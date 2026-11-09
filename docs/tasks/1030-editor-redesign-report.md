# 1030 report: property editor redesign

Status: review

## Result (owner decisions 2026-11-08: "6 pills as switcher", Wolt-simple)
- Phone (<768) unchanged.
- >=768: title, the six status pills (3 per row), one slim fix line, one section card. A pill (click, Enter, Space) shows its section, writes the hash, sets aria-current. Guest link opens Automatic messages; Copy link keeps its action. The section list (.prop-nav) and the Continue setup box never show.
- Fix line: after a failed save it names every invalid or blank required field by its clean label (no help, no star), then server missing items not already covered; each name links to its field.
- >=1024: pills and editor start under the title, max width min(1000px, 100% - 64px) so Save clears the help bubble.
- Merged origin/main (#817 "Applies from" kept). main owns docs/tasks/1030-report.md (walg), so this report has its own name.

## 1032: Stay fee at wide widths
- Reproduced at 1280 to 1800: long council values and a wide saved signature pushed fields past the card; More details sat 16 px in. Not fixed by main.
- Fixed at >=1024: shrinkable grid tracks, min-width:0, plain More details and Signature on the field left edge.
- Saved signature shown whole at every width (max 160 px high, aspect kept); the Edit pad draws it scaled to fit (host.js). Stored format unchanged.
- Test: tests/test_stay_fee_section_wide_1032_browser.py (overflow and alignment at 1280/1440/1600/1800; corner-drawn signature saved, reloaded, edited, redrawn at 1440/1800).

## Test pins (owner decision 2026-11-08)
- test_property_navigation_browser.py, test_property_preview_sticky_browser.py, test_design_guardrails_browser.py: pills are the switcher.
- test_stay_fee_rate_field_1029.py: Stay fee chosen by its pill at >=768.
- test_0710 mockup match: wide card header accepted (WIDE_OVERRIDES, WIDE_MISSING_OK in tests/v2_mockup.py).
- New: tests/test_property_fixline_browser.py.

## Keys
app2.css 1032c, app.js 1030i, host.js 1032a; tests/static_versions.json rewritten.

## Screenshots (/mnt/project-files/ux-shots/editor-redesign/)
- editor-390-v3.png; editor-{768,1280,1280-fixline,1280-stayfee}-v4.png
- stay-fee-{1440,1800}-v5.png; stay-fee-signature-{1440,1800}-v5.png

## Owner steps left
Review and merge PR #820 with scripts/merge-pr-on-green.sh.
