# 1073 report

Files changed: App/tests/v2_mockup.py (BOX_OVERRIDES accepts a list; housebook@320 lists both wraps); brief corrections (six lines, step 7 command, step 6 whole file).

- Step 2 (before): 11-09 14 passed; 11-10 1 failed, 13 passed.
- Step 5: 11-09, 11-10, 11-20, 12-01 each `14 passed`, 0 skipped.
- Step 6: whole file `183 passed in 234.70s`, 0 skipped.
- Step 7: wrong height "20px" gave `1 failed` naming `.stay .in small height at 320 px`; reverted ("38px" restored).
- Failure message now prints the accepted list instead of the mockup value.

Acceptance: all ticked. No UI change, no screenshot.
Deviations: none beyond reviewer corrections. Questions: none. Owner steps: none.
