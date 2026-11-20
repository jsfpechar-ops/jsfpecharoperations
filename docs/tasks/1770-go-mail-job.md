# 1770: Go jobs 1: register the `mail` job kind

Status: review — exact-diff sidecars ready (2026-11-20).
Depends on: 1231, 1231b, 1231c (outbox drain, done), 1632 SES keys | Base commit: current tip of the working branch | Branch: task/1770-go-mail-job
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: B (Sonnet writes the exact-diff pass; orchestrator reads the diff of the risk-listed files)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1770 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1770 step'`.

## 1. Objective

Register `mail` in `go/cmd/ubyhost-web/register_job_mail.go` so Go drains the outbox (`go/internal/mail/outbox_drain.go` exists). Python `mail.drain` stays until the switch.

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first (no new personal-data field without a `retention.py` line, no new outbound request without a reason in the PR); 3 no secrets, no real data (fixtures use `@example.test`); 4 no new dependency without a decision line; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, a schema change is a new `App/migrations_pg/` file; 6 light mode, every form works without JavaScript (Go forms carry the `_csrf` input); 11 Go first.

**Python source of truth:** `App/app/mail.py` 737 (`drain`), `go/internal/mail/outbox_drain.go`, `docs/plans/go-mail-job.md`.

**Risk:** Real mail to guests and hosts.

**All implementation code is pre-written on `main`.** Sidecars: `docs/tasks/1770-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Checksums:

| sha256 | file | action |
|---|---|---|
| `f9c3bfa364d87b24316d407d5c1526f68e2958927a6ecbdbe78dc95961f77466` | `go/cmd/ubyhost-web/register_job_mail.go` | create |
| `5ca696fd7164617c4e078cc0c07c8239da0e0e473685c0533538a8a06f0f00f9` | `go/cmd/ubyhost-web/register_job_mail_test.go` | create |

Full manifest: `docs/tasks/1770-files/MANIFEST.sha256`.

**Verified by the brief writer:** sidecars taken from current `main`; `sha256sum -c docs/tasks/1770-files/MANIFEST.sha256` OK against live repo paths; `cd go && gofmt -l cmd/ubyhost-web/register_job_mail.go cmd/ubyhost-web/register_job_mail_test.go` empty; `go vet ./cmd/ubyhost-web/...` silent; `go test ./cmd/ubyhost-web/ -run 'MailJob' -count=1` OK (DB test skips without `UBYHOST_TEST_DATABASE_URL`).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/cmd/ubyhost-web/register_job_mail.go` | create | registerJob for mail |
| `go/cmd/ubyhost-web/register_job_mail_test.go` | create | registered and claims a row in a test database |
| `docs/tasks/1770-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1770-report.md` | create | the report (§9) |

No other file may change. Two open briefs naming the same file in §3 run in the order of the dependency overview in [go-sqlite-final](../plans/go-sqlite-final.md).

## 4. Steps

0. Checks (repo root). Anything other than the stated result: STOP (§8). Each `grep -cF` / `wc` anchor prints `1` (or `2` for the sidecar count); see `docs/tasks/1770-files/ANCHORS.txt`:
   - `grep -cF 'def drain(limit: int = 8) -> Dict[str, int]:' App/app/mail.py | tail -1`
   - `grep -cF 'func Drain(ctx context.Context, pool *pgxpool.Pool, cfg Config, limit int) (Summary, error)' go/internal/mail/outbox_drain.go | tail -1`
   - `grep -cF 'func _job_mail() -> None:' App/app/scheduler.py | tail -1`
   - `grep -cF 'registerJob("mail", 5, mailHandler)' go/cmd/ubyhost-web/register_job_mail.go | tail -1`
   - `grep -cF 'func TestMailJobRunsAgainstDatabase(t *testing.T)' go/cmd/ubyhost-web/register_job_mail_test.go | tail -1`
   - `find docs/tasks/1770-files -name '*.txt' ! -name 'ANCHORS.txt' | wc -l | tail -1` prints `2`.

1. Copy sidecars and verify (one call, repo root). Never retype or edit them:

   ```bash
   S=docs/tasks/1770-files && for f in $(cd "$S" && find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "$(dirname "$f")" && cp "$S/$f.txt" "$f"; done && sha256sum -c "$S/MANIFEST.sha256" 2>&1 | tail -20
   ```

   Expected: 2 lines ending `: OK`. Commit `1770 step 1`. If files already match `main`, log that and skip the commit.
2. Run the commands in §6; write the report (§9).

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file; `handlers.go` and shared `i18n.json` (add new catalog files instead); anything under `App/app/` except what §3 lists; filing code (`go/internal/ubyport`, `App/app/reporting.py`) unless §3 lists it.

## 6. Commands

- `cd go && gofmt -l . | tail -5` prints nothing
- `cd go && go vet ./internal/mail/... ./cmd/ubyhost-web/... ./cmd/... 2>&1 | tail -20` is silent
- `cd go && go test ./internal/mail/... ./cmd/ubyhost-web/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30` passes, no test skipped
- Mail route golden (`test_go_mail_parity.py`, plan go-mail-job) is **out of scope**; needs brief **1770-fix-1**.
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean
## 7. Acceptance

- Test: a queued row is claimed, sent through a fake SES, marked sent once; two workers never send one row twice (`FOR UPDATE SKIP LOCKED`).
- `git log --oneline --grep='^1770 step'` shows one commit per step; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3 would have to change; a new column, retention line or outbound request is needed; the tests need a skip.

## 9. Report

`docs/tasks/1770-report.md`: commits, command outputs (last 30 lines), accepted differences, what was left undone (1770-fix-1 goldens).

## Rollout wave and rollback

- **Rollout:** Add `mail` to `UBYHOST_GO_JOB_KINDS` and `UBYHOST_JOB_QUEUE_KINDS` together, after the SES test (M-P8) passes on Go; watch one day of outbox counts equal Python's.
- **Rollback:** Remove `mail` from both variables; Python drains again.

## Owner steps

Send yourself one mail from the app on Go before the switch (SES test M-P8).
