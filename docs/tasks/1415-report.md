# 1415 report

Status: review

## Files changed
- `scripts/ci_shard.py` (new): stdlib script, `pick` and `weights` modes.
- `App/tests/test_ci_shard.py` (new): 9 unit tests.
- `.github/ci-weights/postgres.json` (new): 586 files, 1884 s total, from main run 43589068676 (pg-full-junit-1..4).
- `.github/workflows/ci.yml`: browser and Postgres shard steps call `pick`; both steps now exit 1 on an empty shard.
- `docs/context/test-map.md`: one row for `test_ci_shard.py`.

## Steps
- 1 baseline: done. postgres-full-shard present (1414 landed).
- 2 script: done.
- 3 weights: done for Postgres only. Browser junit is not uploaded as an artifact (only `browser-shots-n`), so `browser.json` was not created.
- 4 unit test: done.
- 5 test-map: done.
- 6 wiring: done, with a deviation (see below).
- 7 proof: done (below).
- 8 checks: done (below).
- 9 report and push: done.

## Checks
- `pytest tests/test_ci_shard.py`: `9 passed in 0.11s`. Run with `--noconftest` because `App/` has no `.venv` and the app deps are not installed; conftest imports fastapi.
- YAML parse of `ci.yml`: OK.
- actionlint and shellcheck: not installed here, not verified.
- Context lint: not run (not verified).
- Postgres set (762 files, 586 weighted): disjoint True, complete True. Greedy loads 563.2 / 563.2 / 563.2 / 563.7 s, spread 0.5 s (max weight 31.6 s). Round-robin on the same data: spread 254.0 s.
- Browser set (161 files): disjoint and complete by construction, and shard 1 to 4 output is identical to the old awk split (41/40/40/40).
- Sample weights (40 files, weights 1 to 120): greedy spread 2.0 s, round-robin spread 30.0 s.

## Weights source
Real Postgres weights from main CI junit. Junit `classname` is `tests.test_x` for module tests and empty for collection-skipped items (those get no weight). Mapping confirmed on real XML.

## Missing weights or missing entry
Missing or non-object weights file: round-robin on the sorted list, stderr `ci_shard: no weights, using round-robin`, exit 0. A file with no weight: the median of all known weights (1.0 if none).

## Deviations
- Added an empty-shard guard (`exit 1`) to both wiring steps. Without it, an empty list makes pytest run the whole suite.
- Browser weights not shipped: only round-robin runs until a browser junit is uploaded.
- Used `python3` (not `python`) in the wiring, as the brief says.
- Browser shards: no real weights, so no balance numbers for browser.
- Did not open a PR (system instruction forbids it); owner or orchestrator opens it.

## Questions
- Should the browser shards upload `/tmp/ubyhost-tests.xml` so `browser.json` can be built?

## Owner steps
1. Open the PR from `claude/optimistic-allen-ybxnjg`, wait for green, merge with `scripts/merge-pr-on-green.sh <PR number>`.
2. After merge, compare the next CI shard times with 10.5 / 13 / 23.5 / 13 minutes (browser) and the Postgres shard times.

## Fix after review
- test-map.md under the 1200-token cap: row shortened to `scripts/ci_shard.py` and two wordings tightened; no test names changed. context lint: OK.
