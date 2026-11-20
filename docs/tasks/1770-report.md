# 1770 report: Go `mail` job registration

Status: review

## Commits

- Implementation already on `main` (`ff535973a`, matches exact-diff sidecars).
- `1770 step 1`: sidecars verified (`sha256sum -c docs/tasks/1770-files/MANIFEST.sha256` OK).
- `1770 step 5`: this report.

## Files (§3)

| Path | Note |
|---|---|
| `go/cmd/ubyhost-web/register_job_mail.go` | `registerJob("mail", 5, mailHandler)`; seven Python steps |
| `go/cmd/ubyhost-web/register_job_mail_test.go` | `TestMailJobIsRegistered`, `TestMailJobRunsAgainstDatabase` |
| `docs/tasks/1770-report.md` | this file |

No `UBYHOST_GO_PATHS` or server wiring changes.

## Commands (last lines)

```
sha256sum -c docs/tasks/1770-files/MANIFEST.sha256
go/cmd/ubyhost-web/register_job_mail.go: OK
go/cmd/ubyhost-web/register_job_mail_test.go: OK
```

```
cd go && gofmt -l .
(empty)
```

```
cd go && go vet ./internal/mail/... ./cmd/ubyhost-web/... ./cmd/...
(silent)
```

```
cd go && go test ./internal/mail/... ./cmd/ubyhost-web/... -count=1
ok  	.../go/internal/mail	0.057s
ok  	.../go/cmd/ubyhost-web	1.710s
```

```
python3 scripts/context_lint.py
context lint: OK
```

## §7 acceptance

- [x] `mail` registered every 5 minutes; factory safe with nil pool.
- [x] `TestMailJobRunsAgainstDatabase` (when `UBYHOST_TEST_DATABASE_URL` set): queued outbox row → console send → `sent`; expired provisional hold; second run does not resend (SKIP LOCKED in `mail.Drain`).
- [ ] Golden / route parity (`test_go_go_mail_job_golden.py`): **not in §3**; script and test not added (deferred to a follow-up brief).
- [ ] Host screenshots: no host pages in this brief (N/A).

## Deviations

1. **Step 0 anchor** `grep -cF 'func _job_mail() -> None:' App/app/scheduler.py` returns 0; Python uses `def _job_mail() -> None:` (line 239). Sidecar content is otherwise anchored.
2. **`TestMailJobRunsAgainstDatabase`** skips locally without `UBYHOST_TEST_DATABASE_URL` (no Postgres in this agent VM). CI is expected to run it with DB (same pattern as briefs 0683, 0760).
3. Brief §6 `pytest tests/test_go_go_mail_job_golden.py` — file does not exist; out of §3 scope for this PR.
4. Brief §4 steps 2–4 (golden script, web routes, i18n) not executed — §3 lists only the two `register_job_mail*` files.

## Questions

None.

## Owner steps

Rollout per brief: add `mail` to `UBYHOST_GO_JOB_KINDS` and `UBYHOST_JOB_QUEUE_KINDS` after M-P8; send one test mail on Go before switch.