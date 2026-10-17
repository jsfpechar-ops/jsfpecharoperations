# 0040 feedback, copy, and command-palette report

The previous fixed feedback rail could cover host actions. The CSS owner moved
the rail into the host content lane and kept persistent warnings, failures, and
Undo controls visible. I measured the remaining inline-copy interaction: the
success card shifted its source action down 54 CSS pixels in both EN and CS.
Normal copy now keeps its visible Copied/checkmark receipt on the button and
uses the existing polite live region once; it no longer adds a redundant
success card. Command-palette copy keeps its shared success toast and now binds
that toast to the actual command launcher for focus restoration.

Manual-copy recovery remains inside the in-flow error card or recovery panel
when the three-card rail is full. Dismissal restores the original source node,
visibility, parent, and form association. Command-palette denial stays inside
the native dialog with its readable alert and selectable source.

Changed paths:

- `App/app/static/app.js`: in-place copy success announcement; preserved
  command-launcher focus origin; existing manual-source restoration behavior.
- `App/app/templates/base.html`: in-main feedback region, manual recovery
  markup, and `20261010-host-wide-0040` cache tokens for app.js/host.css.
- `App/tests/test_host_feedback_browser.py`: geometry, rail queue, recovery,
  command failure/success, and focus regressions.
- `generated_images/host-wide-audit/feedback/`: 15 real Chromium captures from
  synthetic host data, including EN/CS mobile and desktop, full-rail failures,
  and command-dialog denial at 360/1280px.

Verification:

- `node --check app/static/app.js` passed.
- `UBYHOST_BROWSER_EXECUTABLE=/usr/bin/chromium UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_feedback_browser.py -q` passed: 1 passed, 0 skipped. It asserts the real copy button retains the same document position at the top and at a scrolled action both immediately and after seven seconds; it also checks full-rail pointer dismissal, source restoration, native-dialog geometry/keyboard selection, command toast timing, and launcher focus restoration.

The broader application suite and cross-page geometry suite belong to the
validation owner. No production or staging deployment was performed.
