# 0362: Tidy CI: one annotation script, no dead steps, pinned actions, grouped Dependabot

Status: review
Depends on: 0361 (both edit ci.yml) | Base commit: 73fc1e7 (task/0361 head) | Branch: task/0362-ci-tidy
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

`ci.yml` repeats the same JUnit-annotation Python and 8 "failure detail" steps in every test job, runs a mypy step that can never fail, waits for `test` before `smoke` and `docker` for no reason, and has no job timeouts. Make it shorter, faster and safer without changing what is tested.

## 2. Context

- The repeated block is the step `Annotate failed tests` (an inline `python - <<'PY'` script that reads `/tmp/ubyhost-tests.xml`, prints `::error title=...::` lines and writes `failure_1..8` to `$GITHUB_OUTPUT`) followed by 8 steps named `${{ steps.test_failures.outputs.failure_N || 'Test failure detail N' }}`. It appears in `test` and `browser-shard`. `browser-shard` also has `Summarize required browser checks` (zero-skip guard).
- mypy step: `name: Type check (informational baseline)` with `continue-on-error: true`.
- `smoke` and `docker` have `needs: test`.
- Commit SHAs for the actions in use (resolved 2026-10-24 with `git ls-remote`):
  `actions/checkout` v7 = `3d3c42e5aac5ba805825da76410c181273ba90b1`,
  `actions/setup-python` v7 = `6d4fd22b20465ccc0f7354476588e8df7c9ca0e0`,
  `actions/setup-node` v6 = `249970729cb0ef3589644e2896645e5dc5ba9c38`,
  `actions/upload-artifact` v4 = `ea165f8d65b6e75b540449e92b4886f43607fa02`, v7 = `cf430e030ddbb5b0abf93d22962f4752f3646cd9`.
  If `ci.yml` already says `upload-artifact@v7` (Dependabot #409 merged), use the v7 SHA everywhere. Pin form: `uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7`.
- Current `.github/dependabot.yml`: pip `/App` weekly (limit 5), github-actions `/` weekly, docker `/` weekly.

## 3. Files

| Path | Action | What |
|---|---|---|
| `scripts/ci_junit.py` | create | One script: annotations, failure outputs, zero-skip guard |
| `.github/workflows/ci.yml` | edit | Use the script, drop mypy, drop `needs: test` on smoke/docker, add timeouts, pin actions |
| `.github/dependabot.yml` | edit | Groups and the Python ignore |
| `.github/workflows/deploy-production.yml` | edit | One zizmor ignore comment, step 7 |
| `docs/tasks/0362-report.md` | create | Report |

No other file may change.

## 4. Steps

1. Create `scripts/ci_junit.py` with exactly:
   ```python
   #!/usr/bin/env python3
   """Turn a pytest JUnit report into GitHub annotations and step outputs.

   Usage: ci_junit.py REPORT LABEL [--no-skips]
   Prints "LABEL: N passed, N failed, N skipped", one ::error annotation per
   failure, writes summary= and failure_1..3= to $GITHUB_OUTPUT, and exits 1
   when the report is missing or empty, a test failed, or (--no-skips) any
   test was skipped. Skipped browser tests mean a broken browser, not a pass.
   """
   from __future__ import annotations

   import os
   import sys
   import xml.etree.ElementTree as ET
   from pathlib import Path


   def main() -> int:
       report, label = Path(sys.argv[1]), sys.argv[2]
       no_skips = "--no-skips" in sys.argv[3:]
       if not report.exists():
           print(f"::error title={label}::test report {report} is missing")
           return 1
       cases = list(ET.parse(report).iter("testcase"))
       failures = []
       skipped = 0
       for case in cases:
           if case.find("skipped") is not None:
               skipped += 1
           problem = case.find("failure")
           if problem is None:
               problem = case.find("error")
           if problem is None:
               continue
           title = (case.get("classname", "") + "." + case.get("name", ""))[:200]
           text = problem.text or problem.get("message", "")
           detail = text[-6000:].replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
           print(f"::error title={title}::{detail}")
           failures.append(title + ": " + " ".join(text.split())[-3500:])
       passed = len(cases) - len(failures) - skipped
       summary = f"{label}: {passed} passed, {len(failures)} failed, {skipped} skipped"
       print(summary)
       out = os.environ.get("GITHUB_OUTPUT")
       if out:
           with open(out, "a", encoding="utf-8") as fh:
               fh.write(f"summary={summary}\n")
               for index, detail in enumerate(failures[:3], 1):
                   fh.write(f"failure_{index}={detail}\n")
       if not cases or failures or (no_skips and skipped):
           return 1
       return 0


   if __name__ == "__main__":
       raise SystemExit(main())
   ```
   Run §6 (a). Commit `0362 step 1`.
2. In `ci.yml` job `test`: delete the mypy step. Replace `Annotate failed tests` and its 8 detail steps with:
   ```yaml
         - name: Test report
           id: report
           if: always()
           run: python3 ${{ github.workspace }}/scripts/ci_junit.py /tmp/ubyhost-tests.xml Tests

         - name: ${{ steps.report.outputs.failure_1 || 'Failure detail 1' }}
           if: failure() && steps.report.outputs.failure_1 != ''
           run: 'true'

         - name: ${{ steps.report.outputs.failure_2 || 'Failure detail 2' }}
           if: failure() && steps.report.outputs.failure_2 != ''
           run: 'true'

         - name: ${{ steps.report.outputs.failure_3 || 'Failure detail 3' }}
           if: failure() && steps.report.outputs.failure_3 != ''
           run: 'true'
   ```
   Commit `0362 step 2`.
3. In job `browser-shard`: replace `Summarize required browser checks`, its summary-name step, `Annotate failed tests` and the 8 detail steps with the same block as step 2, but the first step's run is `python3 ${{ github.workspace }}/scripts/ci_junit.py /tmp/ubyhost-tests.xml "Browser shard ${{ matrix.shard }}" --no-skips`, plus after it a step `name: ${{ steps.report.outputs.summary || 'Browser summary' }}`, `if: always()`, `run: 'true'`. Commit `0362 step 3`.
4. Remove `needs: test` from `smoke` and `docker`. Add `timeout-minutes:` right under `runs-on:` in every job of `ci.yml`: `test` 15, `browser-shard` 25, `smoke` 10, `docker` 15, every other job 5. Commit `0362 step 4`.
5. Pin every `uses: actions/...@vN` in `ci.yml` (the deploy workflows use none) to the SHA from §2 with `# vN` after it. Do not touch `uses: ./.github/...`. Give every `actions/checkout` `persist-credentials: false` (merge it into an existing `with:`). Commit `0362 step 5`.
6. Replace `.github/dependabot.yml` with:
   ```yaml
   version: 2
   updates:
     - package-ecosystem: pip
       directory: /App
       schedule: { interval: weekly }
       open-pull-requests-limit: 5
       groups:
         pip-minor-and-patch:
           update-types: [minor, patch]
     - package-ecosystem: github-actions
       directory: /
       schedule: { interval: weekly }
       groups:
         actions:
           patterns: ["*"]
     - package-ecosystem: docker
       directory: /
       schedule: { interval: weekly }
       ignore:
         # A Python runtime upgrade is its own task, not a weekly bump.
         - dependency-name: python
           update-types: [version-update:semver-major, version-update:semver-minor]
   ```
   Commit `0362 step 6`.
7. In `.github/workflows/deploy-production.yml`, on the line `  workflow_run:` append ` # zizmor: ignore[dangerous-triggers] runs only for CI on main pushes; the job checks event != pull_request and head_branch == main, and checks out nothing from the triggering run`. Commit `0362 step 7`. Run §6 (b) and (c), then (d): `/tmp/zz/bin/zizmor --offline --min-severity=high .github/workflows 2>&1 | tail -5` reports no high findings (if `/tmp/zz` is missing: `python3 -m venv /tmp/zz && /tmp/zz/bin/pip install -q zizmor`). Write the report.

## 5. Do not touch

`App/`, `scripts/merge-pr-on-green.sh`, the `run:` commands of test steps (what pytest runs), job names (`test`, `smoke`, `browser`, `browser-shard`, `shellcheck`, `docker`, `secrets`, `context`), the deploy logic. Never push or merge.

## 6. Commands

(a) From the repo root: `printf '<testsuite><testcase classname="a" name="ok"/><testcase classname="a" name="s"><skipped/></testcase></testsuite>' > /tmp/j.xml && python3 scripts/ci_junit.py /tmp/j.xml Demo; echo "exit $?"; python3 scripts/ci_junit.py /tmp/j.xml Demo --no-skips; echo "exit $?" 2>&1 | tail -10` prints `Demo: 1 passed, 0 failed, 1 skipped`, `exit 0`, then the same line and `exit 1`.

(b) `App/.venv/bin/python -c "import yaml,sys; [yaml.safe_load(open(f)) for f in sys.argv[1:]]; print('ok')" .github/workflows/ci.yml .github/dependabot.yml 2>&1 | tail -5` prints `ok` (no PyYAML: say so, do not install).

(c) `grep -c "continue-on-error\|Test failure detail\|uses: actions/[a-z-]*@v" .github/workflows/*.yml 2>&1 | tail -10` prints 0 for every file. `python3 scripts/context_lint.py 2>&1 | tail -3` ends with `context lint: OK`.

## 7. Acceptance

- [ ] §6 (a) to (d) as expected.
- [ ] `ci.yml` is at least 150 lines shorter (`git diff --stat`).
- [ ] No job name changed.

## 8. Stop and ask

Stop, and write the report, if: an anchor is not found; `ci.yml` does not have the `browser-shard` job (0361 not merged); you reach 25 tool calls or about 50k tokens; a step is unclear; you would need push, merge or secrets.

## 9. Report

Write `docs/tasks/0362-report.md` (600 tokens at most) and set `Status: review`.

## Risk list (for the reviewer)

`.github/workflows/ci.yml`, `scripts/ci_junit.py`

## Owner steps

1. Merge when CI is green.
