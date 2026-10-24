# 0362 report

Status: review

## Files changed

- `scripts/ci_junit.py` (new, exact copy of brief step 1)
- `.github/workflows/ci.yml` (steps 2 to 5, plus one fix commit)
- `.github/dependabot.yml` (step 6)
- `.github/workflows/deploy-production.yml` (step 7, one comment on `workflow_run:`)

## Commands

(a) `Demo: 1 passed, 0 failed, 1 skipped` / `exit 0` / `Demo: 1 passed, 0 failed, 1 skipped` / `exit 1`. As expected.
(b) `ok` (run with App/.venv Python, PyYAML present).
(c) `grep -c` prints 0 for all five workflow files. `context lint: OK`.
(d) zizmor: `No findings to report. Good job! (5 ignored, 8 suppressed)`.
actionlint on ci.yml: no output, exit 0.

## Acceptance (section 7)

- [x] §6 (a) to (d) as expected.
- [ ] `ci.yml` at least 150 lines shorter: it is 402 to 303 lines, 99 shorter. See Deviations.
- [x] No job name changed.

## Deviations

- Done: steps 1 to 7. Left: none.
- Step 2 left one orphan `run: 'true'` line (off by one in my edit). actionlint caught it; fixed in commit 6ce5ac8 "0362 step 2 fix".
- Line-count target not met: the brief's exact diffs remove 99 lines, not 150. I followed the steps as written and did not add extra cuts. Reviewer to decide.
- `upload-artifact` is pinned to the v4 SHA, because ci.yml used v4 (not v7).
- `ci_junit.py` uses stdlib `xml.etree`, as the brief specifies. A security hook suggested `defusedxml`; not applied, since it would be a new dependency. Input is pytest's own JUnit file.
- The first 8 commits (steps 1 to 7 and the fix) have the message `0362 step k` with no Co-Authored-By trailer. The attribution reminder asked for trailers; I added them to this report commit only and did not rewrite the unpushed history. Say if you want it rewritten.
- The test suite was not run (not in the brief).

## Owner steps left

1. Merge when CI is green (after review).
