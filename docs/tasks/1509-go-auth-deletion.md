# 1509: Go auth, admin schedules a workspace deletion (`POST /admin/users/{id}/schedule-deletion`, dormant)

Status: review
Depends on: 1501 | Base commit: 859d114d5 | Branch: go-wave3
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

**One big PR mode.** Work on the branch that is checked out now (`go-wave3`). Never create a branch, never push, never open a PR. Commit after each step that changes a file with the message `1509 step k` (k = the step number), and the report as `1509 report`. Acceptance uses `git log --grep`, never a fixed base commit.

**Depends on, checked:** 1501 (built on go-wave3) gives `mail.QueueWorkspaceDeletion` and `mail.DeletionScheduled` (`go/internal/mail/auth_queue.go` 352). Not 1504: its routes (`POST /admin/users`, `/admin/users/{id}/invite`, `/admin/users/{id}/email`) do not conflict with this pattern in `http.ServeMux`, and this brief uses none of its code. The Routes row and the route count are applied by a script that works whether or not 1502 to 1508 ran first. 1514 only empties `knownGaps` in `routes_test.go`; the helpers this test reuses stay.

## 1. Objective

Port `user_schedule_deletion` (`App/app/routes/admin_accounts.py` 1042-1068) to `go/internal/web/auth`: the admin types the account's username, the account gets `deletion_due_at` 30 days ahead, every contact address of the workspace gets the "scheduled" notice, an audit row is written, and the admin is sent back to the customer page. Tier A (account deletion date); dormant until the owner adds the path to `UBYHOST_GO_PATHS`, and proven equal to Python by a golden recorded from the real Python route.

## 2. Context

Rules (AGENTS.md): 2 privacy (no new field, no new outbound request; the mail rows go to the existing outbox); 3 test addresses only (`@example.test`); 4 no new dependency (`go/go.mod` unchanged); 5 SQL with `$n` placeholders, no schema change; 11 go-first: `App/scripts/auth_deletion_golden.py` is port plumbing (go-first.md allowance 1, golden script). No file under `App/app/` changes.

**Python, the source of truth** (`App/app/routes/admin_accounts.py` 1042-1068, verbatim):

```python
@router.post("/admin/users/{user_id}/schedule-deletion")
async def user_schedule_deletion(user_id: int, request: Request):
    """Disable the account and set the deletion date (BE-10, G-D11)."""
    account, guard = _require_admin(request)
    if guard:
        return guard
    target = db.query_one("SELECT * FROM user_account WHERE id = ?", (user_id,))
    if not target:
        return _back(f"/admin/customers/{user_id}", err=_flash(request, "flash.error.no_such_user"))
    form = await request.form()
    if _form_str(form, "confirm") != target["username"]:
        return _back(f"/admin/customers/{user_id}", err=_flash(request, "flash.error.confirm_username"))
    due = (
        datetime.now(timezone.utc) + timedelta(days=WORKSPACE_DELETION_DAYS)
    ).replace(microsecond=0).isoformat()
    db.update("user_account", user_id, {"deletion_due_at": due})
    mail_notify.workspace_deletion(user_id, due, "scheduled")
    db.audit(
        "workspace_deletion_scheduled",
        f"user={user_id} due={due}",
        actor=account["username"],
        owner_user_id=user_id,
    )
    return _back(
        f"/admin/customers/{user_id}",
        msg=_flash(request, "flash.users.deletion_scheduled", date=due),
    )
```

`WORKSPACE_DELETION_DAYS = 30` (line 1010). Gates run in Python's order, as the other handlers in `go/internal/web/auth/admin.go` do: host CSRF (`hostweb.CSRF`), the int path parameter (`pathID`, 422), `_require_admin` (`d.admin`, which is `admingate.Require`). `user_account.username` and `deletion_due_at` are `text` (`App/migrations_pg/00001_baseline.sql` 2164); `user_account` has no encrypted column, so `db.update` is a plain `UPDATE`. The route does not check `active`, and an admin may schedule their own account: Python does both, so Go does too (golden cases `schedule_inactive`, `schedule_own_account`).

**The shared mail.** `workspace_deletion` (`mail_notify.py` 1206-1229) is also what the retention job sends one week before the date. Go has it once, from brief 1501: `mail.QueueWorkspaceDeletion(ctx, pool, getenv, ownerUserID, dueAt, stage, now)` (`go/internal/mail/auth_queue.go` 352-384, key `workspace_deletion:<owner>:<due>:<stage>:<address>`). This brief calls it with `mail.DeletionScheduled`; it writes nothing new for the mail. The Go retention port (`go/internal/retention/steps.go` 541-566, `stepWorkspaces`) counts due and reminder rows and fails closed with `ErrWorkspacesNotPorted` instead of mailing or deleting; this brief does not touch it, and a date set by this Go route is the same row Python's route writes, so retention behaves the same whichever side scheduled it.

**The code is in sidecar files** (`docs/tasks/1509-files/`, each repo file stored as `<path>.txt`; never type or edit the code):

- `go/internal/web/auth/deletion.go`: `scheduleDeletion` (the handler), `deletionDue` (`session.UTCNow(at + 30 × 24 h)`, the same string as `.replace(microsecond=0).isoformat()`), `deletionFlash` (`admin_helpers.flash` with params, through the package `catalog`). Uses only existing package helpers: `pathID`, `formStr` (last value, stripped, as `_form_str`), `flashFor`, `none`, `itoa`, `ptr`, `gated`, `d.audit`, `d.admin`, `serverError`, `hostweb.Back`.
- `go/internal/web/auth/deletion_test.go`: `TestDeletionDue`, `TestScheduleDeletionRouteListed` (one row, no ServeMux conflict), `TestScheduleDeletionGoldenDatabase` (replays the 20 golden cases on PostgreSQL with the clock fixed at the golden's `fixed`; compares status, Location, Content-Type, Cache-Control, body, cookies, the `audit` rows, `user_account.deletion_due_at`, and the `email_outbox` rows including the payload). It reuses `loadSeed`, `sessionToken`, `parseCookie`, `header`, `str`, `norm`, `testPool` and the `golden` types from `routes_test.go`.
- `go/internal/web/auth/testdata/schedule_deletion.json`: the golden.
- `App/scripts/auth_deletion_golden.py`: writes that golden from the real FastAPI route, reusing `App/scripts/auth_routes_golden.py` (brief 1282: seed, cookies, `run`) with only `admin_accounts.datetime` fixed to 2099-03-04T05:06:07.890123Z; it also rewrites the package `i18n.json` from `i18n_keys.txt`, as `auth_routes_golden.py` does.
- `edit_routes.py` (not copied into the repo): appends the Routes row as the last row of the `Routes` slice in `auth.go`, after any rows sibling briefs added, and raises the count in `auth_test.go` `TestRoutesBuildWithoutPool` by one from whatever it is (both numbers must be equal before; it stops otherwise).

**Strings.** Three keys are appended to `go/internal/web/auth/i18n_keys.txt` only if missing (1504 or 1510 may add `flash.error.no_such_user` too): `flash.error.no_such_user`, `flash.error.confirm_username`, `flash.users.deletion_scheduled` (`App/app/host_i18n.py` 4754-4756 en, 5641-5643 cs). `i18n.json` is regenerated, never hand-edited; `App/tests/test_go_auth_routes.py` proves it is fresh.

**Differences from Python, on purpose:** none in the answer. Go reads `SELECT username` instead of `SELECT *` (only the username is used). A failed outbox read inside `QueueWorkspaceDeletion` is a 500 after the date is written, as a raising `mail.enqueue` is in Python.

Anchors (step 0, each `grep -cF '<anchor>' <file>` prints 1):

| File | Anchor |
|---|---|
| `go/internal/mail/auth_queue.go` | `func QueueWorkspaceDeletion(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string,` |
| `go/internal/web/auth/auth.go` | `func Routes(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) []Route {` |
| `go/internal/web/auth/auth.go` | `func (d deps) audit(ctx context.Context, g *gated, at time.Time, action, detail, actor string, owner *int64) error {` |
| `go/internal/web/auth/admin.go` | `func (d deps) admin(w http.ResponseWriter, r *http.Request) (*session.Host, bool) {` |
| `go/internal/web/auth/routes_test.go` | `func loadSeed(t *testing.T, ctx context.Context, pool *pgxpool.Pool, seed [][2]any, now time.Time) {` |
| `go/internal/web/auth/auth_test.go` | `func TestRoutesBuildWithoutPool(t *testing.T) {` |
| `App/scripts/auth_routes_golden.py` | `def run(case, seed):` |
| `App/app/routes/admin_accounts.py` | `mail_notify.workspace_deletion(user_id, due, "scheduled")` |

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/auth/deletion.go` | create (copy) | the handler |
| `go/internal/web/auth/deletion_test.go` | create (copy) | golden replay and unit tests |
| `go/internal/web/auth/testdata/schedule_deletion.json` | create (copy, regenerated) | golden |
| `App/scripts/auth_deletion_golden.py` | create (copy) | writes the golden (allowance 1) |
| `go/internal/web/auth/auth.go` | edit (script) | one row appended at the end of `Routes` |
| `go/internal/web/auth/auth_test.go` | edit (script) | route count +1 |
| `go/internal/web/auth/i18n_keys.txt` | edit | up to three keys appended |
| `go/internal/web/auth/i18n.json` | regenerate | by the golden script |
| `docs/tasks/1509-report.md` | create | the report |

`docs/tasks/1509-files/` is part of this brief; do not edit it. No other file may change.

## 4. Steps

0. Checks (from the repo root, one call):

```bash
git status --short | tail -5; ls go/internal/web/auth/deletion.go go/internal/web/auth/deletion_test.go go/internal/web/auth/testdata/schedule_deletion.json App/scripts/auth_deletion_golden.py 2>&1 | grep -c 'No such file'
cd docs/tasks/1509-files && sha256sum -c <<'EOF' 2>&1 | tail -6
dafbb02da4f783639a3f8f96c87f1ed83ed2d37a1e75b17f8e6115c397f9534b  App/scripts/auth_deletion_golden.py.txt
910dfa8a037f1249311c4ea183a710ef33f1156452b76b0dc59a8d389fef1d4a  edit_routes.py
bae7cc0cba501df26c81090f76377fe53a03b4186a8b82ab317e1cb8798db4e6  go/internal/web/auth/deletion.go.txt
bca33fc543bd345347c44d6565070438f80b89740dc1e3a60ee7d2f7c7015605  go/internal/web/auth/deletion_test.go.txt
8dadea914a615a0a5a2b34e0d8dfb729a611d8f8eca7f8448ebf1ba0ffeff4c8  go/internal/web/auth/testdata/schedule_deletion.json.txt
EOF
```

   Expected: `git status` prints nothing (uncommitted files of another brief: STOP and ask), the `grep -c` prints `4`, then five `OK` lines. Then check every anchor of section 2 with `grep -cF '<anchor>' <file>` (one call, eight commands joined with `;`): eight `1`. Also `grep -c 'scheduleDeletion\|schedule-deletion' go/internal/web/auth/auth.go` prints `0`. Anything else: STOP. No commit for step 0.

1. Copy the files and build (from the repo root):

```bash
cd docs/tasks/1509-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && git status --short | tail -6
cd go && gofmt -l internal/web/auth 2>&1 | tail -3; go build ./... 2>&1 | tail -5
```

   Expected: `git status` shows exactly `?? App/scripts/auth_deletion_golden.py`, `?? go/internal/web/auth/deletion.go`, `?? go/internal/web/auth/deletion_test.go`, `?? go/internal/web/auth/testdata/schedule_deletion.json`; no gofmt or build output (`go: downloading` lines are fine). Commit `1509 step 1`.

2. Register the route and the strings (from the repo root):

```bash
python3 docs/tasks/1509-files/edit_routes.py 2>&1 | tail -3
for k in flash.error.no_such_user flash.error.confirm_username flash.users.deletion_scheduled; do grep -qxF "$k" go/internal/web/auth/i18n_keys.txt || echo "$k" >> go/internal/web/auth/i18n_keys.txt; done
git diff go/internal/web/auth/auth.go | grep '^[-+]' | grep -v '^[-+][-+]' ; git diff --stat | tail -4
cd go && gofmt -l internal/web/auth 2>&1 | tail -3; go vet ./internal/web/auth/ ./cmd/ubyhost-web/ 2>&1 | tail -5
```

   Expected: `added` and `route count N -> N+1` (N is 18 if no sibling brief added a route, more otherwise); the `auth.go` diff is exactly the one line `+		{"POST /admin/users/{id}/schedule-deletion", "/admin/users/{id}/schedule-deletion", d.scheduleDeletion},` as the last row of `Routes`; the stat lists `auth.go` (1 insertion), `auth_test.go` (2 lines changed) and `i18n_keys.txt` (1 to 3 insertions); no gofmt or vet output. The script printing an `AssertionError`: STOP. Commit `1509 step 2`.

3. Regenerate the golden and the catalog from Python (from the repo root). If `App/.venv/bin/python` is missing, first `cd App && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -5; cd ..`.

```bash
cd App && .venv/bin/python scripts/auth_deletion_golden.py 2>&1 | grep -v ' INFO ' | tail -5; cd .. && sha256sum go/internal/web/auth/testdata/schedule_deletion.json | tail -1; git status --short | tail -8
cd App && .venv/bin/python -m pytest tests/test_go_auth_routes.py -q --tb=short -rs 2>&1 | tail -5
```

   Expected: `wrote go/internal/web/auth/testdata/schedule_deletion.json` and `wrote go/internal/web/auth/i18n.json`; the hash `8dadea914a615a0a5a2b34e0d8dfb729a611d8f8eca7f8448ebf1ba0ffeff4c8`; `git status` shows `M go/internal/web/auth/i18n.json` and nothing else uncommitted; `2 passed`, nothing skipped. A different hash is allowed only when `git log --oneline 859d114d5..HEAD -- App/scripts/auth_routes_golden.py | tail -3` lists a commit (a sibling changed the shared seed); then keep the regenerated file, write both hashes under Deviations, and step 4 decides. A different hash without such a commit is also allowed when the two `2 passed` lines hold (the seed may carry values that change per run, as the 1503 and 1504 writers saw): keep the regenerated file and record both hashes under Deviations; STOP only when a test fails. Commit `1509 step 3`.

4. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip the start. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`). Skip the start if `su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55519/data status' | tail -1` says `server is running`:

```bash
mkdir -p /var/tmp/pg55519 && chown postgres /var/tmp/pg55519 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg55519/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55519/data -o "-p 55519 -k /var/tmp/pg55519" -l /var/tmp/pg55519/log start' 2>&1 | tail -3
```

   Expected: `server started`. No PostgreSQL 16 binaries at that path: write "CI only" in the report, run section 6 without the database, and set the report `blocked`. Then run the tests (from the repo root):

```bash
cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55519/postgres go test ./internal/web/auth/ -count=1 -v -run '^TestDeletionDue$|^TestScheduleDeletionRouteListed$|^TestScheduleDeletionGoldenDatabase$|^TestRoutesBuildWithoutPool$|^TestCatalogHasEveryKey$' 2>&1 | grep -E '^(--- |ok|FAIL)|SKIP' | tail -12
cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55519/postgres go test ./internal/web/auth/... ./internal/mail/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -10
cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55519/postgres go test ./internal/web/auth/ -count=1 -v -run '^TestScheduleDeletionGoldenDatabase$' 2>&1 | grep -c '^    --- PASS'
```

   Expected: five `--- PASS` lines and `ok`, no `SKIP`; only `ok` lines; `20`. No commit (nothing changed).

5. Run section 6. Write the report (section 9) and commit it as `1509 report`. Do not push or open a PR.

## 5. Do not touch

`go/internal/hostweb/`, `go/internal/session/`, `go/internal/mail/` (every file), `go/internal/retention/`, `go/internal/jobs/`, `go/internal/web/auth/routes_test.go`, `go/internal/web/auth/testdata/routes.json`, every other existing file in `go/internal/web/auth/` except the three edited in section 3, `go/cmd/ubyhost-web/` (the package's routes are registered already by `register_web_auth.go`), `go/go.mod`, `go/go.sum`, `App/app/`, `App/tests/`, `App/scripts/auth_routes_golden.py`, `deploy/`, `docs/context/`, `docs/tasks/1509-files/`. `UBYHOST_GO_PATHS` defaults stay as they are. Never print a secret, token or e-mail address. Rules 2, 3, 4, 5 and 11 as in section 2.

## 6. Commands

From the repo root:

- `cd go && gofmt -l internal/web/auth 2>&1 | tail -5` prints nothing.
- `cd go && go build ./... 2>&1 | tail -30` prints nothing.
- `cd go && go vet ./internal/web/auth/ ./internal/mail/ ./cmd/ubyhost-web/ 2>&1 | tail -30` prints nothing.
- `cd go && go mod tidy -diff 2>&1 | grep -v downloading | tail -5` prints nothing.
- The three test commands of step 4, with the outputs stated there (0 skipped).
- `cd App && .venv/bin/python -m pytest tests/test_go_auth_routes.py -q --tb=short -rs 2>&1 | tail -5`: `2 passed`.
- `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` shows no error naming 1509.

Test-map: no row covers Go packages; the commands above are this brief's tests. `test_go_auth_routes.py` is the row for the package catalog.

## 7. Acceptance

- [ ] `git log --oneline --grep='^1509 step'` lists steps 1, 2 and 3, and `git log --oneline --grep='^1509 report'` the report.
- [ ] `for c in $(git log --format=%h --grep='^1509 '); do git show --name-only --format= $c; done | sort -u` lists exactly the 9 files of section 3 plus `docs/tasks/1509-go-auth-deletion.md` (the Status line).
- [ ] `cd docs/tasks/1509-files && for f in App/scripts/auth_deletion_golden.py go/internal/web/auth/deletion.go go/internal/web/auth/deletion_test.go; do cmp $f.txt ../../../$f; done` prints nothing.
- [ ] `grep -c 'd.scheduleDeletion' go/internal/web/auth/auth.go` prints `1`.
- [ ] Step 4 and section 6 outputs exactly as stated, `TestScheduleDeletionGoldenDatabase` run (not skipped) with 20 passing cases.
- [ ] `for c in $(git log --format=%h --grep='^1509 '); do git show --name-only --format= $c; done | grep -E 'go\.mod|go\.sum|App/app/|App/tests/|hostweb/|internal/mail/|cmd/ubyhost-web/|deploy/|routes_test\.go'` prints nothing.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor is not found, a file to create exists, a sha256 differs, or the regenerated golden differs without a sibling commit (step 3);
- a test fails twice (never change the code: it is fixed by hash);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1509-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (the section 7 file list).
2. Each command, with the last 5 lines of its output, and the SKIP count (must be 0).
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the full diff of:

- `go/internal/web/auth/deletion.go`: gate order (CSRF, path id, admin), the `NULL` username never matching, the 30-day date string, the order write, mail, audit (as Python: no transaction), the audit detail `user=<id> due=<due>` with owner the target and actor the admin, the flash keys and the back path `/admin/customers/<id>`.
- `go/internal/web/auth/auth.go`: one appended row only.
- `go/internal/web/auth/auth_test.go`: only the count moved by one.
- `App/scripts/auth_deletion_golden.py`: calls the real route through `auth_routes_golden.run`; fakes only `admin_accounts.datetime`.

Verified by the brief writer in a throwaway worktree of `go-wave3` at 859d114d5 with exactly these steps, PostgreSQL 16 on a disposable port, Go 1.25 toolchain: `gofmt -l` empty, `go build ./...`, `go vet ./internal/web/auth/ ./cmd/...` clean, `go mod tidy -diff` empty; `go test ./internal/web/auth/` `ok` with `TestScheduleDeletionGoldenDatabase` running all 20 cases (none skipped) and `./cmd/ubyhost-web/` `ok`; `test_go_auth_routes.py` 2 passed; the golden script run twice gave the same hash. Mutations caught by the golden test: 29 days, audit detail `due:`, stage `week_before`, owner nil in the audit row, back path `/admin/users/<id>`, wrong error flash key. The golden covers: success in en, cs (padded confirm), vi; no contact address; inactive account; date already set (overwritten); own account; impersonating admin (impersonator id in the audit row); repeated `confirm` (last wins, both ways); mail off; wrong case; missing confirm; unknown user; bad id signed in and out (422 before the login gate); host (403 text); signed out (login redirect); no CSRF token same-site and cross-site.

## Owner steps

1. Nothing for this brief alone: it is merged with the one big PR and changes nothing in production (the route is registered but Caddy sends the path to Python until it is listed in `UBYHOST_GO_PATHS`).
2. To switch it, after the deploy: on the server, add `/admin/users/*/schedule-deletion` inside the double quotes of `UBYHOST_GO_PATHS` in `.env` (space-separated, see `docs/ENVIRONMENT.md`), from `deploy/lightsail` run `./scripts/caddy-validate.sh`, then `docker compose up -d caddy`; rollback is removing it again and the same two commands. Switch it together with the other `/admin/users` POST routes (brief 1504's `/admin/users`, `/admin/users/*/invite`, `/admin/users/*/email`, and 1510's `/admin/users/*/export` once it is unblocked), so the whole `/admin/users` prefix moves at once. Then, on a test account only: open the customer page, type the username in the deletion form, press the button, and check the page says "Workspace deletion scheduled for ..." with a date 30 days ahead.
