# 2054 report: functional parity rerun

Status: blocked

## 1. Files changed

- docs/tasks/2054-report.md (this file). No other tracked file changed.
- Outside the repo: symlinks `/cursor/stores/bc-6e0cc745-51a8-434b-ae3b-2eb8d63269b1/media` and `.../docs` pointing to `/var/tmp/parity-2054/media` and `/var/tmp/parity-2054/docs` (step 2).

## 2. Commands (last lines)

- Step 1: `source scripts/e2e/parity_env.sh > /var/tmp/parity_env.log 2>&1; tail -5 ...; pg_isready -h 127.0.0.1 -p 5433; which go`
  - log: empty; `127.0.0.1:5433 - accepting connections`; `/usr/local/go/bin/go`. OK.
- Step 2: `mkdir -p ... && ln -sfn ...`
  - `id -u` prints 0; both symlinks listed. OK.
- Step 3: `$UBYHOST_E2E_PSQL ... pg_stat_activity where datname like 'parity%'`
  - `parity_run|4`. A parity database has 4 open connections, so another agent may be running. Brief section 8 says STOP.

Steps 4 to 8 were not run.

## 3. Counts

- Audit (steps 5 to 7): not run.
- Jobs (step 4): not run.
- Handlers (step 4): not run.
- Baseline: fail 0 / 843 rows. Now: not measured.

## 4. Failing rows

None measured. No RETIRED rows were classified.

## 5. Acceptance (section 7)

- [ ] Audit finished: no (blocked at step 3).
- [ ] Counts reported: no.
- [ ] Failing rows listed: n/a.
- [ ] Comparison line: baseline fail 0 / 843 rows; now not measured.
- [ ] git status shows only this report: to be checked at commit time.

## 6. Deviations

Done: steps 1 to 3. Left: steps 4 to 8.

## 7. Questions

- Who holds the `parity_run` connections on 127.0.0.1:5433 (4 sessions)? Is it safe to kill them, or should the audit wait?
- Is it OK to keep the `/cursor/stores/...` symlinks in place for the next run?

## 8. Owner steps left

- Confirm the `parity_run` connections are not in use. Then rerun the brief from step 3 (or ask the orchestrator to do it).
