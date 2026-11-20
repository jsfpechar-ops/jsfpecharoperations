# 1770 report: Go `mail` job registration

Status: review

## Commits

- Implementation already on `main` (`ff535973a`, matches exact-diff sidecars).
- **Step 1:** `sha256sum -c docs/tasks/1770-files/MANIFEST.sha256` already OK on `main`; no copy, no `1770 step 1` commit.
- **This PR:** `1770 step 5` — brief Status `review` + refreshed report.

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
cd go && go test ./internal/mail/... ./cmd/ubyhost-web/... ./cmd/ubyhost-web/... -count=1
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail	0.251s
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	1.697s
```

```
cd go && go test ./cmd/ubyhost-web/... -run MailJob -count=1 -v (tail)
TestMailJobIsRegistered — PASS
TestMailJobRunsAgainstDatabase — SKIP (UBYHOST_TEST_DATABASE_URL not set)
```

```
python3 scripts/context_lint.py
context lint: OK
```

```
cd App && .venv/bin/python -m pytest tests/test_go_go_mail_job_golden.py -q
ERROR: file or directory not found: tests/test_go_go_mail_job_golden.py
```

## §7 acceptance

- [x] `mail` registered every 5 minutes; factory safe with nil pool.
- [x] `TestMailJobRunsAgainstDatabase` (when `UBYHOST_TEST_DATABASE_URL` set): queued outbox row → console send → `sent`; expired provisional hold; second run does not resend (SKIP LOCKED in `mail.Drain`).
- [ ] Golden / route parity (`test_go_go_mail_job_golden.py` / `test_go_mail_parity.py` per `docs/plans/go-mail-job.md`): **blocked by §3** — needs brief **1770-fix-1** to extend §3 before adding `App/tests/test_go_mail_parity.py` and wiring `App/scripts/mail_*_golden.py`.
- [ ] Host screenshots: no host pages in this brief (N/A).

## Deviations

1. **Step 0 anchor typo in brief/ANCHORS.txt:** `grep -cF 'func _job_mail() -> None:' App/app/scheduler.py` returns 0; live Python is `def _job_mail() -> None:` (`grep -cF` → 1). All other anchors return 1; sidecar count 2.
2. **`TestMailJobRunsAgainstDatabase`** skips locally without `UBYHOST_TEST_DATABASE_URL` (no Postgres in this agent VM). CI is expected to run it with DB (same pattern as briefs 0683, 0760).
3. Brief §6 `pytest tests/test_go_go_mail_job_golden.py` — file does not exist (plan names `test_go_mail_parity.py`); §3 forbids adding it here → **1770-fix-1**.
4. Brief §4 steps 2–4 (golden script, web routes, i18n) **stale for job-only pass** — not executed; §3 lists only the two `register_job_mail*` files plus report/sidecars.
5. Brief §6 “no test skipped”: `TestMailJobRunsAgainstDatabase` skips without `UBYHOST_TEST_DATABASE_URL` (same as brief writer note in §2).

## Questions

None.

## Owner steps

Rollout per brief: add `mail` to `UBYHOST_GO_JOB_KINDS` and `UBYHOST_JOB_QUEUE_KINDS` after M-P8; send one test mail on Go before switch.