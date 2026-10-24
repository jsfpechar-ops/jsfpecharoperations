# 0299 report

Status: blocked

## Files changed
- App/tests/test_host_invoice_items_browser.py (lines 180-187 replaced with the brief's step 1 block; 19 insertions, 6 deletions)

## Commands
- `.venv/bin/python -m pytest tests/test_host_invoice_items_browser.py -q --tb=short -rs`
  Result: `1 failed, 4 passed, 1 warning`. Failure at 760 px (en):
  `assert abs(remove_box["y"] - tops[0]) <= 2` gives `84.5 <= 2`
  (Remove y 1107.4 vs controls top 1022.9).

## Steps
- [x] 1. Replace the Remove assertions (applied as written; `tops` is defined at line 160, so `tops[0]` is used)

## Deviations
Done: step 1. Left: none. Blocked by the test result above.
Not run: the brief's step 1 check passes only for the card-width branch; at 760 px the Remove button sits about 85 px below the quantity/unit/price line, so the 0295 "same line" expectation does not match the rendered layout.

## Questions
- Is the 760 px layout (Remove on a second line at card width > 420) the intended 0295 behavior? If yes, the brief's expectation is wrong; if no, the template/CSS is the thing to fix. Not changed here.

## Owner steps left
- Decide the above; then re-run the command.
- No PR opened: the branch is not pushed (brief says commit here, never push).
