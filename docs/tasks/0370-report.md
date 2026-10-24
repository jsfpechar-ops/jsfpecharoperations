# 0370 report: tablet menu test screenshot

Status: review

## Files changed

- `App/tests/test_0251_tablet_browser.py`: `_shot` takes `full_page=True`; the menu-open shot passes `full_page=False` (with a one-line comment). No assertion changed.

## Commands (§6)

Before step 1 (base commit 911bfb9), `UBYHOST_SHOTS_DIR=/tmp/0370-shots`:

```
WARNING  ubyhost:main.py:143 Running against the MOCK UbyPort server - nothing is reported to the police. Set UBYHOST_UBYPORT_ENV=test or prod when you have credentials.
.../_connection.py:632: playwright._impl._errors.TimeoutError: Page.wait_for_function: Timeout 5000ms exceeded.
=========================== short test summary info ============================
FAILED tests/test_0251_tablet_browser.py::test_overview_cards_and_tablet_menu_on_touch
1 failed in 9.98s
```

Note: App/.venv was missing in this worktree, so the venv from `/home/claude/wt-0368-browser-test-portability/App/.venv` was used.

After step 1 (same env, plus `-rs`):

```
.                                                                        [100%]
1 passed in 5.74s
```

0 skipped.

## ls /tmp/0370-shots | tail -8

```
0251-menu-open-1024.png
0251-menu-open-1180.png
0251-overview-1024.png
0251-overview-1180.png
0251-overview-820.png
```

## Acceptance (§7)

- [x] §6 fails before step 1 and passes after, with `UBYHOST_SHOTS_DIR` set.
- [x] `0251-menu-open-1180.png` and `0251-menu-open-1024.png` exist in `/tmp/0370-shots`.
- [x] No assertion changed.

## Deviations

- The §6 command ends in `tail -5` as written in the brief; the executor rule asks for `tail -30`. Kept the brief's command, since its output is short.
- The `-rs` flag was added to the after-run to check for skips.

## Questions

None.

## Owner steps left

None. Branch is not pushed and no PR is open.

## Orchestrator review (2026-10-24)
Diff matches the brief; fail-before and pass-after shown with UBYHOST_SHOTS_DIR set, as on CI.
