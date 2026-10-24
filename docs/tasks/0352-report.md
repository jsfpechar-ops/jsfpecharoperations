# 0352 report: Leon (AI) guest chat on the guide pages

Status: review

## Files changed

     App/app/guest_uk_i18n.py             |  13 ++
     App/app/i18n.py                      |  65 ++++++++
     App/app/routes/guest_guide_view.py   |  11 +-
     App/app/static/guest-leon.js         | 281 +++++++++++++++++++++++++++++++++++
     App/app/static/guest.css             |  25 ++++
     App/app/templates/guest/_host.html   |   6 +
     App/app/templates/guest/_leon.html   |  32 ++++
     App/app/templates/guest/base.html    |   3 +-
     App/app/templates/guest/guide.html   |   2 +
     App/tests/static_versions.json       |   8 +-
     App/tests/test_guest_csrf.py         |   1 +
     App/tests/test_guest_leon_browser.py | 189 +++++++++++++++++++++++
     App/tests/test_guest_leon_chat.py    | 125 ++++++++++++++++
     docs/context/test-map.md             |   2 +-
     docs/plans/guest-guide.md            |   2 +-
     15 files changed, 757 insertions(+), 8 deletions(-)

Created: guest/_leon.html, static/guest-leon.js, tests/test_guest_leon_chat.py, tests/test_guest_leon_browser.py. Edited: guest.css (appended), guest/base.html, guide.html, _host.html, routes/guest_guide_view.py, i18n.py, guest_uk_i18n.py (by the script), test_guest_csrf.py, static_versions.json, test-map.md, plans/guest-guide.md.

## Commands (last lines)

- Preflight, copy, step 3 script: `added 13 guest keys x 6 languages`; `leon_intro` counts 5 and 1.
- Non-browser set (chat, csrf, guide view, leon, languages, static versions, cache heartbeats, privacy): `145 passed, 1 warning in 19.83s`.
- Browser set with UBYHOST_BROWSER_EXECUTABLE and UBYHOST_REQUIRE_BROWSER=1 (leon, guide, e2e): `23 passed, 1 warning in 225.55s`. 0 skipped (no `s` in the summary).
- `ruff check ... --select E9,F63,F7,F82,F401,F841`: `All checks passed!`
- `design_lint.py`: `design lint: OK`. `context_lint.py`: `context lint: OK` (one WARN: status.md not updated, orchestrator task).
- `grep -c innerHTML guest-leon.js`: 0. Em dash count in guest-leon.js and _leon.html: 0 and 0.

## Acceptance (section 7)

- [x] test_guest_leon_chat.py (6) passed within the 145.
- [x] test_guest_leon_browser.py (5) passed within the 23, 0 skipped.
- [x] innerHTML 0; em dash 0 in both files.

## Deviations

- Step 1 (preflight) had no change and was committed with step 2. Other steps have their own commits (0352 step 2 to step 10).
- No PR opened and no push, per the owner instruction for this run.
- Screenshots skipped (reviewer or orchestrator takes them).

## Questions

None.

## Owner steps left

1. Merge with `scripts/merge-pr-on-green.sh` once CI is green.
2. Leon shows for guests only when `UBYHOST_AI_FEATURES` lists `leon` (0350, owner step 2).
