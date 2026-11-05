# 0965 report (B07: G02, G03, G04)

Status: blocked
Reason: `test_0965_acknowledgement_is_neutral_then_positive_and_red_only_after_a_failed_submit` fails in all six variants (en/cs x 390/768/1280) on the same colour assertions, on two clean runs. Per the brief's stop rule (fails twice, same cause) the run stopped at step 6. No CSS, JS or threshold was changed for it.

Done: steps 0 to 5 (committed), the birth-date expectation fix (step 6, committed). Left: the acknowledgement failure, the guest baseline run, and the screenshots not inspected (section 4).

## 1. Files changed

`git diff --stat 89772982 HEAD -- App/app App/tests docs/tasks/0965-guest-review.md`: 10 files, 1294 insertions, 19 deletions (section 3 files, the test file, and the brief).

Commits: 1e69e2fc (step 1), c7503f95 (step 2), 3b238d38 (step 3), 94871621 (step 4), 92e2a525 (step 5), step 6 test fix (SHA in the git log), this report (`0965 step 7`).

## 2. Birth-date check (step 1, base vs branch)

`initBirthDate()` in `App/app/static/signature.js` is byte-identical between base 7b0355c and the branch. The review row uses it. Intl with the same options gives `1 January 1980` (en-GB) and `1. ledna 1980` (cs-CZ) (node 22, ICU 78). The test now expects those values per language. Production code is unchanged.

## 3. Commands

- `test_guest_browser_e2e.py -k 0965 -q -rfs` (DB removed before the run): 13 passed, 6 failed, 0 skipped. All six rows-test variants pass. The six failures are the acknowledgement test: the `border` assertion at line 1159 (en) and 1167 (cs) fails. The invalid class and `aria-invalid` checks pass.
- First run used a DB left over from an earlier run and failed with `UNIQUE constraint failed: apartment.permalink_token` (18 failed). Remove the scratch DB before each run.
- Guest baseline and `test_host_geometry.py`: not run (stopped by the rule above).
- `python3 scripts/context_lint.py | tail -30`: `context lint: OK`, exit 0, WARN lines only (open-brief names, "10 commits touched App/ after the last status.md update").
- `git diff --check`: no output, clean.
- `tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py`: 16 passed, 0 skipped.
- Tracked PNGs: none changed; `git status` shows only the test file before the commit.

## 4. Screenshots (step 7, partial)

- `0965-en-390-review-legal-closed.png`: five rows, label above value, `1 January 1980` in the birth-date row, Change links on one right edge, a long name and address wrap inside their rows. Legal line is below the crop.
- `0965-cs-390-review-legal-closed.png`: same layout in Czech; the birth-date row `1. ledna 1980` is visible at 390 px (acceptance item). Změnit links aligned.
- `0965-cs-390-ack-attempted-invalid.png`: the acknowledgement box has a red border and light-pink fill, and the browser's native "Please check this box" bubble sits over the acknowledgement text and hides part of it. This is an overlap; STOP criterion. The bubble may be a capture artifact; needs a decision.
- Not inspected: `0965-en-390-ack-attempted-invalid.png` (not written; the test failed before the shot), all other 0965 PNGs. No screenshot is passed.

Likely cause of the colour failure (not verified): the measured border reads the default grey `[201,201,194]` while the screenshot shows red on the row; the ticked state reads Oklab-like values `[0.703, -0.045, 0.021]`. The colour helper or the measured element in `_B07_ACK_JS` may be wrong.

## 5. Acceptance (section 7)

Ticked (test-measured, run 2): birth-date row present at 390 in English and Czech with the app's format; five fact rows, label above value, aligned Edit edges, no sideways scroll, one surface (rows test 6/6).
Passing in run 2 (13 of 19 0965 tests): rows (6), sticky action (4), Edit returns to the right step (2), and one other 0965 test.
Not verified: acknowledgement colours (6 failing), guest baseline, the saved-strip screenshot, the static cache-key diff re-check, all screenshots except the three in section 4.

## 6. Deviations

- Birth-date expectation: the brief's `01.01.1980` replaced by `1 January 1980` (en) and `1. ledna 1980` (cs), per the orchestrator's decision and the step 1 check. Only that assertion changed.
- Brief Status was already `blocked`; no separate status commit.

## 7. Questions

- Acknowledgement test: fix the colour helper or the measured element (owner: orchestrator). Then rerun the 0965 group and the guest baseline.
- Native validation bubble over the acknowledgement text at cs-390: accept as capture artifact, or change the layout.

## 8. Owner steps left

None. No push, merge or PR was made.
