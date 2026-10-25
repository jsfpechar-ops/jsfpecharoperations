# 0399 report (session 2)

Status: blocked (one question, see Questions)

## Files changed (this session)

- `App/tests/test_0399_open_buttons_click_browser.py`: browser test now requires `/reservations?range=all`, `/apartments`, `/housebook` and the first property overview at 390 and 1280; clicks with `click(force=True)`; "at least 6" rule removed. New non-browser test: no `row_open()` without an argument, no `<span class="row-open">`, macro renders `<a class="row-open" href=`.
- `docs/design/MASTER.md`: the `open` variant row now says Open is a real link to the row's own target. (No `row_open` name exists in MASTER, so the `open` row in section 7.1 was used.)

## Test output

- `UBYHOST_REQUIRE_BROWSER=1 ... pytest <brief §3 list> -q --tb=short -x -rs | tail -30`: `27 passed in 73.00s`, 0 skipped.
- `python3 scripts/context_lint.py`: FAIL. The only ERRORs are that `docs/tasks/0399-open-buttons-click.md` lacks sections `## 2. Context` to `## 9. Report`; the brief uses its own numbering. Other lines are WARN only.

## Deviations

- `settle_motion(page)` (brief §2 step 6) does not exist in the repo. The test uses `page.wait_for_load_state("load")`, as `test_0385_phone_card_open_browser.py` does.
- Brief §5 step 1 stay-detail check dropped. `reservation_detail.html` has no guests-table Open. Its only `row_open` (line 408) sits in the submissions table, which renders only when the stay has submissions. Demo data has no submissions, so the check could not pass. Test passes without it.

## Questions

1. Should the stay-detail Open check be dropped for good, or should demo data get a submission so the reports-table Open can be tested?

## Owner steps left

- None. Not pushed. Branch `claude/project-thread-by10nz`.
