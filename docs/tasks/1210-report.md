# 1210 report

Status: review

## 1. Diff stat (a83df54..HEAD, tail)

    App/scripts/retention_golden.py              | 232 ++++
    App/tests/test_go_retention_parity.py        |  47 +
    docs/tasks/1210-appendix/files.md            | 1575 (deleted in report commit)
    docs/tasks/1210-go-retention-job.md          | 223 ++++
    docs/tasks/1211-appendix/files.md            | 1147 +++
    docs/tasks/1211-go-retention-apply.md        | 188 +++
    go/cmd/ubyhost-web/register_job_retention.go |  50 +
    go/internal/retention/golden_test.go         | 233 ++++
    go/internal/retention/retention.go           | 449 ++++++++
    go/internal/retention/retention_test.go      |  85 ++
    go/internal/retention/steps.go               | 253 +++++
    go/internal/retention/testdata/fixture.sql   | 191 ++++
    go/internal/retention/testdata/golden.json   | 647 +++++++++

## 2. Commands (last lines)

- Step 2 `go test ./internal/retention/`: `ok  github.com/jsfpechar-ops/jsfpecharoperations/go/internal/retention`
- Step 3 `go test ./cmd/ubyhost-web/`: `ok  .../go/cmd/ubyhost-web`
- Step 6 golden: `wrote .../golden.json`, sha256 `6fbf4850...808785d` (matches brief)
- §6 Go: `--- PASS` TestRunMatchesPythonGolden (global_dry, owner1_dry), TestApplyIsRefusedUntil1211, TestConfigFromEnvSwitches, TestStepsOrderMatchesPython, TestFormats; `ok` for internal/retention and cmd/ubyhost-web; no SKIP
- §6 parity pytest: `2 passed in 2.29s`; ruff: `All checks passed!`
- context_lint: `next free: task 1212 | migration 0046`, `context lint: OK` (warning only: App/ commits after status.md update, for the orchestrator)

## 3. Acceptance (§7)

- [x] All extractor sha256 and golden.json sha256 matched
- [x] Go §6 command: named tests PASS, none skipped, two ok
- [x] Parity pytest 2 passed; ruff clean; context lint OK
- [x] Diff stat lists only §3 paths plus briefs 1210/1211 and 1211 appendix
- [x] slog lines: only `retention run` counts line and `job_failed alert not raised`
- [x] Six commits `1210 step 1` to `1210 step 6`; nothing pushed

## 4. Deviations

- The extractor was written to the session scratchpad instead of `/tmp/x1210.py` (environment rule). Content is identical.
- No push and no PR: the executor brief forbids pushing and this session has no push permission. The branch `claude/1210-go-retention` is local, ready for the orchestrator to push and open the draft PR.
- PostgreSQL 16 started on `/var/tmp/pg1210` port 5433 (throwaway, trust auth).

## 5. Questions

None.

## 6. Owner steps left

1. Orchestrator or owner: push `claude/1210-go-retention` and open a draft PR.
2. Review and merge the PR with `scripts/merge-pr-on-green.sh` after CI is green.
3. After the auto-deploy, on the server, add `retention` to `UBYHOST_JOB_QUEUE_KINDS` and `UBYHOST_GO_JOB_KINDS` in `/opt/ubyhost/deploy/lightsail/.env`. Do not add `UBYHOST_GO_RETENTION_APPLY`.
4. Run `cd /opt/ubyhost/deploy/lightsail && ./scripts/deploy.sh`.
5. For 3 mornings, run the audit query in the brief's Owner steps and compare Go's dry-run counts with Python's.
