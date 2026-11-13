# 1415: Balance CI shards by measured duration

Status: todo
Depends on: 1413 and 1414 (ci.yml order: 1413, 1414, 1415; if 1414 has not landed, do the browser part only) | Base commit: 531e8359 | Branch: task/1415-ci-shard-balance
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Replace the round-robin file split of the browser shards (and of the Postgres shards if 1414 landed) with a greedy split by measured seconds per file, using a stdlib-only script `scripts/ci_shard.py`. Today the four browser shards take 10.5, 13, 23.5 and 13 minutes: the slowest shard sets the wall time.

## 2. Context

Hard rule 4: stdlib only, no new dependency, no new Action. CI already writes junit XML: browser shards `--junitxml=/tmp/ubyhost-tests.xml` (uploaded as an artifact, grep `upload-artifact` in `.github/workflows/ci.yml` lines 360 to 510), Postgres shards `pg-full-<n>.xml` (after 1414) or `pg-full.xml`, the `test` job likewise (grep `junitxml`).

Current browser split (grep `Pick this shard's files`, about line 428): `files="$(printf '%s\n' tests/*_browser.py tests/test_guest_browser_e2e.py tests/test_host_geometry.py tests/test_wp28_geometry.py tests/test_onboarding_wizard_survival.py tests/test_fee_setup_compatibility.py | sort -u | awk -v n=4 -v s=${{ matrix.shard }} '(NR - 1) % n == s - 1' | tr '\n' ' ')"`. The step runs in `App/` and the files are relative like `tests/x.py`. In a junit XML each `<testcase classname="tests.test_x" ...>` carries `time`; the file is the classname up to the first segment that starts with `Test` (a class) mapped as dots to slashes plus `.py`; the executor must check this on a real XML (step 3) and write the mapping down.

Script contract (`scripts/ci_shard.py`, Python 3.12, stdlib only, `argparse`, `json`, `xml.etree.ElementTree`, `statistics`):
- `python3 scripts/ci_shard.py pick --weights W.json --shards N --index I [--files-from FILE | stdin]`: reads file paths one per line, prints that shard's files, one per line, in sorted order. Index is 1-based. Weight per file from the JSON object `{ "tests/x.py": seconds }`; unknown files get the median of known weights (all known weights), or 1.0 if there are none. Greedy: sort files by weight descending (ties by name), put each into the currently lightest shard (ties: lowest index). Deterministic. If the weights file is missing or unreadable or not a JSON object, fall back to plain round-robin on the sorted list `(position - 1) % N == I - 1` and print `ci_shard: no weights, using round-robin` to stderr, exit 0.
- `python3 scripts/ci_shard.py weights --out W.json X1.xml [X2.xml ...]`: sums `time` per file over all testcases (a file seen in several XMLs is summed), writes JSON with sorted keys, seconds rounded to 1 decimal, keys relative like `tests/test_x.py`. Missing XML: skip with a stderr note.
- Never import anything from `App/`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `scripts/ci_shard.py` | create | the script |
| `App/tests/test_ci_shard.py` | create | unit test |
| `docs/context/test-map.md` | edit | one row (file is limited to 1200 tokens: keep the row to one line) |
| `.github/ci-weights/browser.json`, `.github/ci-weights/postgres.json` | create if junit XML could be fetched, else none | initial weights |
| `.github/workflows/ci.yml` | edit | browser shard step (and Postgres shard step if 1414 landed) call the script |
| `docs/tasks/1415-report.md` | create | the report |

No other file may change.

## 4. Steps

1. Baseline: `grep -n "Pick this shard's files\|Run this shard on PostgreSQL\|^  postgres-full-shard:\|^  browser-shard:" .github/workflows/ci.yml | head; ls scripts | head -40`. Note whether `postgres-full-shard` exists (1414 landed).
2. Create `scripts/ci_shard.py` per section 2 (about 90 lines). Include a function `shards(files, weights, n)` returning a list of n lists so the test can call it directly, and `main()`.
3. Initial weights, best effort, max 5 tool calls: `gh run list --workflow CI --branch main --status success --limit 1 --json databaseId 2>&1 | tail -3`, then `mkdir -p /tmp/junit && gh run download <id> -D /tmp/junit 2>&1 | tail -5` (artifacts of the browser shards and the Postgres job). If `gh` is read-only, unauthenticated or the artifacts are expired, SKIP: ship the round-robin fallback, create no weights files, and say so in the report. Otherwise run `python3 scripts/ci_shard.py weights --out .github/ci-weights/browser.json /tmp/junit/<browser xml files>` and likewise for Postgres. Open one XML with `head -c 1500` first to confirm the classname mapping of section 2 and write it in the report; fix the script if the mapping differs. Weights files must contain only test file paths and seconds (public repo).
4. Create `App/tests/test_ci_shard.py` (no browser, no DB; load the script with `importlib.util.spec_from_file_location` from `Path(__file__).resolve().parents[2] / "scripts" / "ci_shard.py"`). Cases: (a) 12 files with the weights `{f1: 100, f2: 90, f3: 80, f4: 10, ...}` into 4 shards: disjoint, union equals input, `max(load) - min(load) <= max(weights)`; (b) unknown files get the median; (c) deterministic: two calls give equal output; (d) missing weights file: round-robin result equals `(i % n)` dealing; (e) `weights` mode on a tiny junit XML written to `tmp_path` sums two testcases of one file. Mark nothing `sqlite_only`.
5. Test-map: read `docs/context/test-map.md` with `grep -n "^|" docs/context/test-map.md | head -6` and `grep -n "ci\|workflow" docs/context/test-map.md | head`. Add one row `| CI shard script | test_ci_shard.py |` in the table's existing format, if no existing row fits.
6. Wire the browser shards. In the step `Pick this shard's files` replace the `awk ...` part so that the list goes through the script, keeping the same file list and the `echo` lines:
   ```bash
   files="$(printf '%s\n' tests/*_browser.py tests/test_guest_browser_e2e.py tests/test_host_geometry.py \
     tests/test_wp28_geometry.py tests/test_onboarding_wizard_survival.py tests/test_fee_setup_compatibility.py | sort -u \
     | python3 ../scripts/ci_shard.py pick --weights ../.github/ci-weights/browser.json --shards 4 --index ${{ matrix.shard }} | tr '\n' ' ')"
   ```
   The browser job runs in a Playwright container whose `python3` exists (the job already calls `python`); the checkout contains `scripts/`. If 1414 landed do the same in the Postgres shard step with `ci-weights/postgres.json` and `ls tests/test_*.py tests/*_test.py ... | grep -v ...` as input. A missing weights file must not fail the job (the script falls back).
7. Prove the balance, in the report: with the real weights (or, without them, a sample JSON you create in `/tmp` with 40 files of weights 1 to 120), run for I in 1 to 4 `python3 scripts/ci_shard.py pick --weights W --shards 4 --index $I --files-from LIST`, then show: shards disjoint (`sort | uniq -d | wc -l` is 0), union equals input (`diff`), and the sums per shard. State the bound met: heaviest minus lightest is at most the single heaviest file weight. Also compute the old round-robin sums on the same data for comparison.
8. Run the test: `cd App && .venv/bin/python -m pytest tests/test_ci_shard.py -q --tb=short -x 2>&1 | tail -30`. Then `cd .. && python3 scripts/context_lint.py 2>&1 | tail -30` and YAML parse as in 1413 step 7.
9. Report, commit per step as `1415 step k`, push the task branch (never `main`).

## 5. Do not touch

Other tests, `App/app`, other workflow jobs, the deploy gate. Hard rules 3 and 4.

## 6. Commands

Steps 1, 3, 7, 8. Tests: the test-map row added in step 5 only.

## 7. Acceptance

- [ ] `test_ci_shard.py` passes.
- [ ] Step 7 shows disjoint, complete, and heaviest minus lightest at most the heaviest single weight.
- [ ] YAML parses; a missing weights file does not fail the step.
- [ ] Report says whether real weights were checked in, or only the fallback shipped.
- [ ] Context lint has no new error.

## 8. Stop and ask

Stop and write the report if: an anchor is not found verbatim; the junit classname mapping cannot be made to work; a new dependency seems needed; you reach 25 tool calls or about 50k tokens.

## 9. Report

`docs/tasks/1415-report.md` (600 tokens at most), `Status: review`: files changed, step 7 numbers, whether weights were included, deviations, questions, owner steps.

## Risk list (for the reviewer)

The wiring in `ci.yml` (a quoting slip would run zero files and pass; check that the step prints a non-empty file list) and the weights files (stale weights only cost balance, never correctness).

## Owner steps

1. Open the PR, wait for green, merge with `scripts/merge-pr-on-green.sh <PR number>`.
2. After the merge, compare the shard times of the next CI run with 10.5 / 13 / 23.5 / 13 minutes.
