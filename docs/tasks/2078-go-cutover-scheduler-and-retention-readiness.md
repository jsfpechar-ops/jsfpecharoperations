# 2078: Verify cutover job settings and week-one retention

Status: todo
Depends on: none | Base commit: f6be14e46b68677884e26533eef674b15cb89f6a | Branch: task/2078-go-cutover-scheduler-and-retention-readiness
Executor: Luna | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Document Go-only startup requirements and the week-one retention setting. Verify them with mock configuration and hand production confirmation to the owner.

## 2. Context

Go first. UbyPort filing correctness and privacy take priority. Use synthetic data and an isolated local PostgreSQL schema for tests. Review the named anchors against the approved base or its prerequisite tip.

- `docs/context/status.md:5`

  ```text
  ## Go cutover (11-24)
  ```
- `deploy/lightsail/scripts/deploy.sh:22`

  ```text
  echo "ERROR: UBYHOST_SCHEDULER must be go before deploy (got '${UBYHOST_SCHEDULER:-unset}')." >&2
  ```
- `go/cmd/ubyhost-web/job_config.go:52`

  ```text
  return fmt.Errorf("UBYHOST_GO_JOB_KINDS must also be in UBYHOST_JOB_QUEUE_KINDS: %s", strings.Join(goOutside, ", "))
  ```
- `go/internal/retention/retention.go:77`

  ```text
  live := autopurge && (goApply || production)
  ```
- `docs/ENVIRONMENT.md:63`

  ```text
  | `UBYHOST_GO_RETENTION_APPLY` | `0` | Go `retention` job only. It deletes only when this and `UBYHOST_RETENTION_AUTOPURGE` are both `1` (`true` and `yes` also count; lowercase only). Anything else is a dry run: it counts the exact row set and deletes nothing. |
  ```

## 3. Files

| Path | Action | Purpose |
|---|---|---|
| `docs/ENVIRONMENT.md` | edit | Align scheduler and retention descriptions with Go-only startup. |
| `docs/LIGHTSAIL.md` | edit | Add the owner checklist to the Scheduler section. |

The executor report and brief status follow section 9.

## 4. Steps

1. In `docs/ENVIRONMENT.md` document `UBYHOST_SCHEDULER=go`, the enabled scheduler, and matching job lists containing the active scheduler plan, and positive iCal and submission sweep intervals. List the 14 active kinds derived from `scheduler.Plan` with payments retired and explain why Stripe is outside that plan. Mark mixed-stack behavior historical where relevant.
2. Replace the stale `UBYHOST_GO_RETENTION_APPLY` text with: `Go also requires this flag for live purge outside production. In production, UBYHOST_RETENTION_AUTOPURGE=1 enables live purge even when this flag is unset. Set UBYHOST_RETENTION_AUTOPURGE=0 for the first cutover week.` Maintain the accepted lowercase truthy values.
3. In `docs/LIGHTSAIL.md`, give owner checks for the scheduler, matching active job lists, retired payments, first-week dry run and heartbeat destination presence. Record only confirmation and redacted counts. Use the existing mock config tests in section 6. Leave actual settings for the owner to verify privately.

## 5. Do not touch

Keep the retention runtime policy, deploy scripts and all live configuration unchanged. This is a documentation and local verification brief.

## 6. Commands

Run from the indicated directory with pipeline failure reporting on. Expect the listed cases to run and pass. Required database and browser cases must show zero skips.

```sh
cd go && go test ./internal/scheduler/ ./internal/retention/ -run 'Plan|Setup|ConfigFromEnv' -count=1 -v 2>&1 | tail -30
cd go && go test ./cmd/ubyhost-web/ -run 'Scheduler|JobConfig' -count=1 -v 2>&1 | tail -30
bash -n deploy/lightsail/scripts/deploy.sh 2>&1 | tail -30
python3 scripts/context_lint.py 2>&1 | tail -30
```

Use fixture credentials and record only pass/fail, counts, and redacted diagnostics.

## 7. Acceptance

- [ ] The runbook matches startup behavior and the retired-payments plan.
- [ ] The first-week instructions disable autopurge explicitly and explain the production truth table.
- [ ] No live setting or secret value appears in the report.

## 8. Stop and ask

Stop and report if an anchor diverges after listed prerequisites, a required test fails twice, a dependency or file outside section 3 is needed, or the executor limit is reached. Escalate any need for live credentials, a real provider, a deployed server, or a product decision.

## 9. Report

Write `docs/tasks/2078-report.md` with the changed paths, command results, counts, acceptance evidence and owner steps. Set the brief to `Status: review` after completing the checks. Use `Status: blocked` in the report if stopped.

## Risk list (for the reviewer)

The verification evidence and any wording about cutover switches.

## Owner steps

1. Open the two updated runbook sections before approval.
2. Verify both job lists and the retention switch in your private configuration.
3. Review first-week dry-run counts before restoring the intended retention policy.
