# 1102 report — guest guide link only when live

Status: review

## Files changed
- `App/app/routes/guest.py` — import `guest_guide`; `_guide_is_live()`; `guide_live` in stay context.
- `App/app/templates/guest/stay.html` — link guarded and moved below the people block; order comment updated.
- `App/tests/test_guest_guide_view.py` — `_hub_html` + three new tests.
- `docs/tasks/screenshots-1102/` — stay page UX evidence (390 not-live; 390/768/1280 live).

## Commands (last 5 lines each)
- `grep -n "data-guide-link\|guide_live" App/app/templates/guest/stay.html` → lines 158–159 at file end.
- `cd App && .venv/bin/python -m pytest tests/test_guest_guide_view.py -q --tb=short -x` → `22 passed in 4.99s`.
- `.venv/bin/python -m pytest tests/test_layout_lint_browser.py -q --tb=short` → `4 passed in 222.70s`, 0 skipped.
- `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x` → `4 passed in 222.00s`.
- `python3 scripts/context_lint.py` (repo root) → `context lint: OK`.

## Acceptance (brief §7)
- [x] One `data-guide-link` inside `{% if guide_live %}`, after the people block.
- [x] Three new tests and `test_the_stay_page_links_to_the_guide` pass.
- [x] `test_layout_lint_browser.py` green, 0 skipped; CI browser shards 1–4 green on latest run.
- [x] Screenshots in `docs/tasks/screenshots-1102/`; PR body describes them.
- [x] Code diff limited to section 3 plus report, brief status, screenshots.

## Deviations
- `.github/workflows/ci.yml`: install `age` from the upstream release tarball instead of `apt-get` (mirror DNS was killing the 15-minute `test` job before pytest ran). CI green on run 43060458566.
- Local `test_guest_*.py -x` stops on unrelated `test_1031` screenshot path (`/mnt/project-files`); not caused by 1102.

## Questions
- None.
