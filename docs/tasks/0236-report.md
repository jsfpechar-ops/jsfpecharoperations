# 0236 report

Status: blocked

## Commits
- 5187d51 0236 step 1: `App/tests/test_onboarding_wizard_browser.py`, the door_lock block replaced in both places (grep count 2)
- 6bf6fa2 0236 step 2: same file, the two anchors in the lock-step test replaced (grep count 4)
- 80a8ed7 0236 step 3: `App/app/templates/reservations.html`, the link-window line replaced

## Step 4 result (browser run, 600000 ms timeout)

Command: `UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/tmp/claude-0/pw .venv/bin/python -m pytest tests/test_onboarding_wizard_browser.py tests/test_host_list_layouts_browser.py tests/test_guest_link_window_0231.py -q --tb=short -rs`

Last lines:
```
tests/test_host_list_layouts_browser.py:116: in test_stays_pills_and_deadlines_stay_on_one_line
    assert row["height"] <= SHORT_ROW_MAX, (locale, width, row)
E   AssertionError: ('en', 1280, {'pill': True, 'deadline': True, 'height': 122, 'name': 0, ...})
E   assert 122 <= 100
1 failed, 75 passed, 1 warning in 140.19s (0:02:20)
```

No skips reported. The wizard tests and the 0231 link-window tests pass. The one failure is the stay-list row height on en, 1280 px: 122 px against a limit of 100 px. The row still looks two lines tall with the pill and deadline on it.

## Deviations
The brief says to stop after a failure without fixing anything else, so the stay-list row height was not investigated further. Not run: none. Left: the stay-list height failure in `test_stays_pills_and_deadlines_stay_on_one_line` (en, 1280) needs an owner or orchestrator decision.

## Questions
- Should the row-height failure be fixed in a new brief, or does the 100 px limit need to change? I did not guess.

## Owner steps left
- Decide on the row-height failure, then rerun the same command.
- No push, PR or merge was done, as instructed.
