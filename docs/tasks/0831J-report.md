# 0831J report (executor)

Status: blocked. Tasks 1 and 3 done. Task 2 not finished: 1024 px fails (see Deviations). Not committed, not pushed.

## Files changed
- `App/tests/test_design_shell.py`: old-shell page `/payments?lang=en` changed to `/stay-fees?lang=en` (3 places). `/stay-fees` renders `_shell_sidebar.html` (`id="app-sidebar"`), has no `set v2`, and sets `nav == 'stay_fees'` so the active-link check holds.
- `App/tests/test_design_shell_browser.py`: `_open` default path to `/stay-fees?lang=en`; comment updated. Other `/invoices` calls unchanged.
- `App/app/static/app2.css` (0831H block only): added `@media (min-width:481px)` rules for the shared price width (`stay_price` and `item_unit_price` at 7rem), the item card (thead hidden, 5-column grid, description full width, Remove on the controls' line), and Remove height (44 px up to 1023 px, 39 px from 1024 px, matching the inputs).

## Commands and results
- `.venv/bin/python -m pytest tests/test_design_shell.py tests/test_design_shell_browser.py -q --tb=short -rs`: 18 passed, 0 skipped.
- `.venv/bin/python -m pytest tests/test_host_geometry.py -q --tb=short -rs`: 2 passed, 0 skipped.
- `.venv/bin/python -m pytest tests/test_host_invoice_items_browser.py tests/test_host_geometry.py -q --tb=short -rs`: 6 passed, 1 failed (`test_invoice_item_geometry_and_localized_screenshots`, 1024 px en).
  - Last failure: `stay and extra price widths differ at 1024px (en)` at the previous CSS. With `max-width:none` on the price rule, the failure moved to `Remove left differs from the description field at 1024px (en)`: 718 vs 630 px. At 1024 px the item row measures 420 px or less, so the test takes its narrow-row branch.

## Deviations
- The brief asked for the price rule at >= 481 px only. To pass the rest of the file I also needed: a 5-column card from 481 px, a Remove height rule per breakpoint, and the thead hidden in that range. These are in the same 0831H block.
- Done: tasks 1 and 3 (test_host_geometry passes alone). Left: task 2 at 1024 px. The 1024 px row width and the price width must be checked in a browser (a debug copy of the test is the quickest). Likely cause: at 1024 px the sidebar narrows the card, so the 5-column grid with fixed 7rem inputs no longer fits.
- `App/tests/test_0830_airbnb_pages_browser.py` shows as modified in git. It is the other executor's file; not touched here.
- `docs/tasks/screenshots-0624/consent-390.png` was already modified before this run; not touched.

## Owner / orchestrator steps left
- Fix the 1024 px case of `test_invoice_item_geometry_and_localized_screenshots`, then run `App/.venv/bin/python -m pytest tests/test_host_invoice_items_browser.py tests/test_host_geometry.py -q --tb=short -rs 2>&1 | tail -30`.
- Check the 390 px screenshot of the invoice form after the fix (not taken).
