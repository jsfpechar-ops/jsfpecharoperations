# 1211: Go job kind `retention`, deleting half (apply paths, apply golden)

Status: todo
Depends on: [1210](1210-go-retention-job.md) merged (its files unchanged) | Base commit: the 1210 merge on main | Branch: a new branch from main, e.g. claude/1211-go-retention-apply
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier A (deletion, guest data, photos)

## 1. Objective

Add the deleting half of `App/app/retention.py` to `go/internal/retention`: outside a dry run each step deletes or nulls exactly what it counted, with Python's side effects (audit rows `retention_purge`, `submission_orphan_purge`, `invoice_retention_purge`, `platform_invoice_purge`; the `invoice_purge_unlock` setting; passport photo files). Proven against the real Python job for an owner-1 and a global apply run. Go deletes only when both `UBYHOST_RETENTION_AUTOPURGE` and `UBYHOST_GO_RETENTION_APPLY` are on (unchanged from 1210).

## 2. Context

Rules: hard rules 1-4, 8 as in 1210 §2. All 1210 §2 fixed decisions stand. New here (orchestrator decisions, do not change):

- **Same statements as Python, same order.** `stepGuests` = `housebook.purge_expired`: photos first (`passport_photos.delete_photo`: `<UBYHOST_DATA_DIR>/passport_photos/<id><ext>[.enc]` for `.jpg .pdf .png .webp`, regular files only), a failed file delete fails the step before any row goes; then `DELETE FROM guest`, audit `retention_purge` (actor `host`, as `db.audit` with no signed-in actor); then `purge_orphan_submissions` (also when no guest was due). `UBYHOST_DATA_DIR` unset with guests due: the step fails, nothing deleted (Python would look in `App/data`; Go must not delete rows whose photos it cannot see). Invoices: unlock `'1'`, item+invoice deletes per id, unlock `''` even on error (Python `finally`), audit. Platform invoices: per-id deletes, then unmatched old bank payments; audit only when something went, actor `system`. `stay_fee_records`: the two deletes in one pgx transaction (Python `db.immediate()`). `cleaning` and `push`: the update/delete statements run even when the counts are 0, as in Python. The other steps run their UPDATE/DELETE only when the count is above 0, with the same WHERE as the count.
- **Workspaces fail closed.** Python's apply path queues the week-before reminder (`mail_notify.workspace_deletion`: rendered HTML/text mail from `host_i18n` strings into `email_outbox` for every `legal_entity.contact_email`, if mail is enabled) and runs `_delete_workspace` (40 statements in one transaction, then photo files). Neither is ported: rendering needs the mail shell and catalog that live only in Python (and `go/internal/mail` is read-only for this lane). So outside a dry run the Go step counts workspaces due (`deletion_due_at <= now`) and reminders due (`now < deletion_due_at <= now + 7 days`); if either is above 0 it returns `ErrWorkspacesNotPorted` with both counts (no audit line, no `counts` key, job error at the end, everything else applied); if both are 0 it returns 0 exactly as Python would. The golden script patches the Python step the same way (`go_workspaces_step`, the only patch).
- **Photos in production.** The Go container mounts `/data` read-only (`deploy/lightsail/docker-compose.yml`, `ubyhost-go`). Removing a photo there fails, so the guest step fails closed whenever an expired guest still has a file (normally none: the photo sweep deletes photos after 7-30 days). Not changed here: owner decision in Owner steps.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/retention/retention.go` | edit (patch) | remove the 1210 apply guard and `errApplyNotPorted` |
| `go/internal/retention/steps.go` | replace | counting and deleting halves, `deletePhoto`, `ErrWorkspacesNotPorted` |
| `go/internal/retention/golden_test.go` | replace | four scenarios; data-dir test |
| `go/internal/retention/testdata/golden.json` | regenerate | four scenarios |
| `App/scripts/retention_golden.py` | replace | apply scenarios, workspaces patch |
| `App/tests/test_go_retention_parity.py` | replace | four scenario names |
| `docs/tasks/1211-report.md` | create | the report |
| `docs/tasks/1211-appendix/files.md` | delete (report step) | the file contents, committed with the brief |

No other file may change (`retention_test.go`, `fixture.sql`, `register_job_retention.go` stay as 1210 left them).

## 4. Steps

From the repo root. Do not read `docs/tasks/1211-appendix/files.md`: the extractor copies every file from it.

### Step 0: anchors and the extractor

```bash
sha256sum go/internal/retention/retention.go go/internal/retention/steps.go go/internal/retention/golden_test.go App/scripts/retention_golden.py App/tests/test_go_retention_parity.py go/internal/retention/testdata/golden.json 2>&1 | tail -6
```

Expected exactly:

```text
550b821aca1756171fb4f04f54f90077460e39df523cb9b0309f9f0623b15e63  go/internal/retention/retention.go
c82210a6a1e6aa6cd39ce37280e2ce2bccb9bf0e336ac5fe2a4fa404a1e6bce5  go/internal/retention/steps.go
2dc07e83e11891681130d3a4363de773a0789bcdd98abd5604d462266b192989  go/internal/retention/golden_test.go
25966764bf1848ae6e53415a65dcce2ed1e2e9c9925be4b83cb158f8ec97812c  App/scripts/retention_golden.py
fe3059ed30dcc4faf1fafcf40dd435d268bbadd08bdc9b9b4f537d2fc8239f03  App/tests/test_go_retention_parity.py
6fbf48500afc798657fd7791710288fc470b1fae08a7c953db8a4aa46808785d  go/internal/retention/testdata/golden.json
```

Anything else (1210 not merged or changed): STOP (§8). Then write the extractor:

```bash
cat > /tmp/x1211.py <<'PY'
import hashlib, os, re, sys
brief = open(sys.argv[1], encoding="utf-8").read()
for path in sys.argv[2:]:
    found = re.findall(r"^<!-- file: " + re.escape(path) + r" -->\n````[a-z]*\n(.*?)\n````$", brief, re.S | re.M)
    if len(found) != 1:
        sys.exit(f"STOP: {len(found)} blocks for {path}")
    data = (found[0] + "\n").encode("utf-8")
    if os.path.dirname(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as out:
        out.write(data)
    print(hashlib.sha256(data).hexdigest() + "  " + path)
PY
python3 -c "import ast;ast.parse(open('/tmp/x1211.py').read());print('extractor ok')"
```

### Step 1: remove the apply guard

```bash
python3 /tmp/x1211.py docs/tasks/1211-appendix/files.md /tmp/1211-retention.patch 2>&1 | tail -1; git apply /tmp/1211-retention.patch && sha256sum go/internal/retention/retention.go | tail -1
```

Expected: `320c4a823d83516db0303750d19038a0643d0c7b97a3cc34f0f913da10dbb63a  /tmp/1211-retention.patch`, then `ac304e25c0583a8413444f2ab05a5415f8c18a26cd6b507e56b42a1972b3c9e0  go/internal/retention/retention.go`. Commit `1211 step 1: retention apply guard removed`.

### Step 2: the deleting half

```bash
python3 /tmp/x1211.py docs/tasks/1211-appendix/files.md go/internal/retention/steps.go go/internal/retention/golden_test.go 2>&1 | tail -3; cd go && test -z "$(gofmt -l ./internal/retention)" && go vet ./internal/retention/ 2>&1 | tail -5
```

Expected exactly the two lines below, then no `go vet` output:

```text
171a6fd872d639d135b8018f887ddf894ff064fa4b23b998283752eeaf07e78c  go/internal/retention/steps.go
4b2e6872ece0525323baf0ea237ec0c7e4c06ff2acd06ea46f52ff08c821f8c5  go/internal/retention/golden_test.go
```

Commit `1211 step 2: retention apply paths`.

### Step 3: Python golden script and parity test

```bash
python3 /tmp/x1211.py docs/tasks/1211-appendix/files.md App/scripts/retention_golden.py App/tests/test_go_retention_parity.py 2>&1 | tail -3
```

Expected exactly:

```text
106119556c8587da8aca1057d14aa3c0be57272e6e8af229eda5b11ebad779eb  App/scripts/retention_golden.py
f7c3054f5075d2cb6fbe6c7af414789bc71ee0667a9aab4098c3414e5ed39547  App/tests/test_go_retention_parity.py
```

Commit `1211 step 3: retention golden with apply scenarios`.

### Step 4: regenerate golden.json

Start the server and venv with the 1210 step 6 block (copy it from `docs/tasks/1210-go-retention-job.md`, `### Step 6`, first bash block), then:

```bash
cd App && UBYHOST_TEST_DATABASE_URL='postgresql://postgres@/postgres?host=/var/tmp/pg1210&port=5433' .venv/bin/python scripts/retention_golden.py 2>&1 | tail -3; sha256sum ../go/internal/retention/testdata/golden.json | tail -1
```

Expected: `wrote .../golden.json`, then `65de56d3adfa805d2af4a4b2cc48c3c1ca9c414eeba520182f310cf22b6c3985  ../go/internal/retention/testdata/golden.json`. A different sha256: STOP (§8). Commit `1211 step 4: retention golden.json with apply`.

## 5. Do not touch

1210 §5, plus `go/internal/retention/retention_test.go`, `testdata/fixture.sql`, `go/cmd/ubyhost-web/register_job_retention.go`, `deploy/` (the read-only mount is an owner decision).

## 6. Commands

```bash
cd go && test -z "$(gofmt -l ./internal/retention ./cmd/ubyhost-web)" && go vet ./internal/retention/ ./cmd/ubyhost-web/ && UBYHOST_TEST_DATABASE_URL='postgresql://postgres@/postgres?host=/var/tmp/pg1210&port=5433' go test ./internal/retention/ ./cmd/ubyhost-web/ -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL)|^    --- ' | tail -30
```

Expected: `--- PASS` for `TestRunMatchesPythonGolden` with subtests `global_dry`, `owner1_dry`, `owner1_apply`, `global_apply`; `TestApplyWithoutDataDirDeletesNoGuest`; the three unit tests; two `ok`; no `SKIP`.

```bash
cd App && UBYHOST_TEST_DATABASE_URL='postgresql://postgres@/postgres?host=/var/tmp/pg1210&port=5433' .venv/bin/python -m pytest tests/test_go_retention_parity.py -q --tb=short -rs 2>&1 | tail -5; .venv/bin/ruff check scripts/retention_golden.py tests/test_go_retention_parity.py 2>&1 | tail -2
```

Expected: `2 passed`, `All checks passed!`. Repo root: `python3 scripts/context_lint.py 2>&1 | tail -3` ends `context lint: OK`.

## 7. Acceptance

- [ ] Step 0 sha256 list matched; every later sha256 matched.
- [ ] §6 Go command: all four golden subtests and the data-dir test `--- PASS`, none skipped.
- [ ] Parity pytest `2 passed`; ruff clean; context lint OK.
- [ ] `git diff --stat main..HEAD | tail -10` lists only the §3 paths.
- [ ] Four commits `1211 step 1` to `1211 step 4`; nothing pushed.

## 8. Stop and ask

As 1210 §8, plus: step 0 sha256 differ (1210 changed after its review: the orchestrator re-cuts this brief); `git apply` fails.

## 9. Report

Write `docs/tasks/1211-report.md` (600 tokens at most), same sections as 1210 §9, diff stat against `main`. Then `git rm -r -q docs/tasks/1211-appendix`. Set `Status: review`. Commit `1211 report`.

## Risk list (for the reviewer)

Read in full: `go/internal/retention/steps.go` (every apply block against the Python function in its comment: same WHERE as the count, statement order, `deletePhoto` before the guest delete, the unlock reset on error, the transaction in `stepStayFeeRecords`, `stepWorkspaces` fail-closed), `App/scripts/retention_golden.py` (`go_workspaces_step` is the only behaviour patch).

Known parity gaps (accepted; owner to know):

1. Workspace deletion and its week-before reminder mail are not ported (above): with Go applying, a due workspace or a due reminder makes the nightly job fail (`job_failed:retention`, all other steps applied) until the kind goes back to Python or a later brief ports them.
2. Photos: `/data` is read-only in the Go container, so an expired guest that still has a photo file makes the guest step fail (no row deleted, other steps applied).
3. Retries (1210 gap 1) now re-run deletions; they are idempotent (the second pass finds 0 rows), but audit lines repeat.
4. Python's invoice and platform-invoice purges are separate autocommit statements; Go keeps them separate (not one transaction) for parity.

## Owner steps

Only after 1210's 3 dry-run nights matched Python, and only if you have accepted the retention policy (Python's `UBYHOST_RETENTION_AUTOPURGE=1` is the same decision):

1. Decide the photo mount: either leave `/data` read-only in `ubyhost-go` (the guest step then fails closed when an expired guest still has a photo; tell the orchestrator if `job_failed:retention` appears), or ask the orchestrator for a brief that mounts it read-write.
2. Check no workspace is due for deletion within a week (else keep `retention` on Python until a workspace brief exists):

```bash
cd /opt/ubyhost/deploy/lightsail && docker compose exec -T postgres psql -U ubyhost -d ubyhost -P pager=off -c "SELECT COUNT(*) FROM user_account WHERE deletion_due_at IS NOT NULL AND deletion_due_at <= to_char((now() AT TIME ZONE 'UTC') + interval '7 days', 'YYYY-MM-DD\"T\"HH24:MI:SS+00:00')"
```

Expected: `0`.
3. In `/opt/ubyhost/deploy/lightsail/.env` set `UBYHOST_RETENTION_AUTOPURGE=1` and add `UBYHOST_GO_RETENTION_APPLY=1`, then deploy:

```bash
cd /opt/ubyhost/deploy/lightsail && ./scripts/deploy.sh
```

4. Next morning: the newest `retention_run` audit row (1210 owner step 3 query) says `"dry_run": false`, and no `job_failed:retention` alert is open.
5. Roll back: delete the `UBYHOST_GO_RETENTION_APPLY` line and run step 3's deploy again (Go goes back to counting).

