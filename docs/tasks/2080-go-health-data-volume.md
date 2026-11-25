# 2080: Report an unwritable data volume in Go health

Status: todo
Depends on: none | Base commit: f6be14e46b68677884e26533eef674b15cb89f6a | Branch: task/2080-go-health-data-volume
Executor: Luna | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Report actual app volume writability in Go health. Keep the database check and report 503 when either check fails.

## 2. Context

Go first. UbyPort filing correctness and privacy take priority. Use synthetic data and an isolated local PostgreSQL schema for tests. Review the named anchors against the approved base or its prerequisite tip.

- `App/app/main.py:603`

  ```text
  data_writable = os.access(config.DATA_DIR, os.W_OK)
  ```
- `App/app/main.py:609`

  ```text
  healthy = data_writable and database_ok
  ```
- `go/cmd/ubyhost-web/main.go:116`

  ```text
  h := health{Status: "ok", Version: version, DataDirWritable: true, DatabaseOK: dbOK}
  ```
- `deploy/lightsail/docker-compose.yml:149`

  ```text
  UBYHOST_DATA_DIR: /data
  ```

## 3. Files

| Path | Action | Purpose |
|---|---|---|
| `go/cmd/ubyhost-web/main.go` | edit | Add the data-directory check to health. |
| `go/cmd/ubyhost-web/main_test.go` | edit | Test writable and failure combinations. |

The executor report and brief status follow section 9.

## 4. Steps

1. In `main.go`, resolve the same effective data directory as the service and probe effective writability for the service user. A filesystem probe creates a uniquely named empty file, closes it and removes it in the same check. A missing directory or failed probe is false. Keep responses and logs free of local paths or data.
2. Replace `DataDirWritable: true` with `DataDirWritable: dataWritable`, and replace `if !dbOK {` with `if !dataWritable || !dbOK {` in `healthz`. Keep the database timeout, response schema and 503 branch.
3. Add `TestHealthzDataDirectory` with writable temp dir and a stable denied/non-directory fixture, plus database success and failure combinations. Assert status, both flags and probe cleanup. Run section 6.

## 5. Do not touch

Keep Caddy, metrics, startup and backup scripts unchanged. Test fixtures must live outside the app's production volume.

## 6. Commands

Run from the indicated directory with pipeline failure reporting on. Expect the listed cases to run and pass. Required database and browser cases must show zero skips.

```sh
cd go && go test ./cmd/ubyhost-web/ -run 'HealthzDataDirectory|Health|Wrap' -count=1 -v 2>&1 | tail -30
```

Use fixture credentials and record only pass/fail, counts, and redacted diagnostics.

## 7. Acceptance

- [ ] A healthy directory and database return 200. Either failure returns 503 and the corresponding flag is false.
- [ ] The probe leaves no test file behind.

## 8. Stop and ask

Stop and report if an anchor diverges after listed prerequisites, a required test fails twice, a dependency or file outside section 3 is needed, or the executor limit is reached. Escalate any need for live credentials, a real provider, a deployed server, or a product decision.

## 9. Report

Write `docs/tasks/2080-report.md` with the changed paths, command results, counts, acceptance evidence and owner steps. Set the brief to `Status: review` after completing the checks. Use `Status: blocked` in the report if stopped.

## Risk list (for the reviewer)

`go/cmd/ubyhost-web/main.go`

## Owner steps

1. Review the writable and failure evidence before approving.
