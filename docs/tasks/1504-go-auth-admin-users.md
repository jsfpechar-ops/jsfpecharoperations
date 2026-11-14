# 1504: Go auth, admin account writes (`POST /admin/users`, `/admin/users/{id}/invite`, `/admin/users/{id}/email`, dormant)

Status: review
Depends on: 1501 | Base commit: 859d114d5 | Branch: go-wave3
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

**One big PR mode.** Work on the branch that is checked out now (go-wave3). Never create a branch, never push, never open a PR, no `mcp__` tools. Commit after each step that changes a file with the message `1504 step k` (k = the step number), and the report as `1504 report`. The orchestrator opens the one PR.

**Depends on, checked against go-wave3 at 859d114d5:** 1501 (built on this branch) gives `mail.QueueLinkMail`, `mail.KindAccountInvite`, `mail.QueueEmailChanged` (`go/internal/mail/auth_queue.go` 206, 249). The rest already exists from 1280/1282: `session.CreateAccount`, `EmailTaken`, `SetAccountEmail`, `AccountByID` (`go/internal/session/accounts.go` 69, 154, 180, 192), `session.IssueLoginLink` and `LinkTTL` (`loginlink.go` 58, 34), `mail.SendNow` (`outbox_drain.go` 114), `mail.MaskEmail` (`outbox_config.go` 166), and in package `auth`: `deps.admin`, `supportReason` (`admin.go` 35, 78), `normaliseEmail` (`account.go` 204), `formStr`, `pathID`, `flashFor`, `deps.audit`, `deps.attach`, `remembers` (`auth.go`). Not 1502 or 1503: no code of theirs is used. 1509 and 1510 add their own `/admin/users/{id}/...` rows and files after this one; nothing here touches them. 1514 only empties `knownGaps` in `routes_test.go`; the helpers this test reuses (`loadSeed`, `sessionToken`, `parseCookie`, `samePayload`, `header`, `str`, `norm`, `testPool`, `goldenCase`) stay.

## 1. Objective

Port the three admin writes of the customer pages to Go: create a host account and mail its invitation, send a fresh invitation, and set or change an account's login e-mail (with the support reason, the change notices, and a fresh session for the admin's own browser). This closes the `/admin/users` method gap (Go has `GET /admin/users` since brief 1282, Python still answers the `POST`), so the whole path can later be switched to Go; tier A because it creates accounts, mails login links and ends sessions.

## 2. Context

Rules (AGENTS.md): 2 privacy (no new personal-data field, no new outbound request: mail goes through the existing outbox and `mail.SendNow`); 3 nothing real in the repo (test secret, `@example.test` addresses); 4 no new dependency (`go/go.mod` unchanged); 5 SQL with Postgres placeholders, no schema change; 11 go-first: `App/scripts/admin_users_golden.py` is port plumbing (go-first exception 1, golden scripts). No file under `App/app/` changes.

**The code is in sidecar files.** `docs/tasks/1504-files/` mirrors the repo paths with `.txt` added. Step 1 copies them and checks their sha256. Never type or edit the code. `docs/tasks/1504-files/edit_routes.py` is run, not copied.

**Python source of truth** (`App/app/routes/admin_accounts.py` at 859d114d5):

| Route | Python | Go (`go/internal/web/auth/admin_users_post.go`) |
|---|---|---|
| `POST /admin/users` | `user_create` 745-771 | `deps.userCreate` |
| `POST /admin/users/{id}/invite` | `user_invite` 774-785 | `deps.userInvite` |
| `POST /admin/users/{id}/email` | `user_email_set` 788-851 | `deps.userEmailSet` |
| (helper) | `_send_invite` 731-742 | `deps.sendInvite` |

Gates in Python's order, as the 1282 routes do: the host CSRF check (`hostweb.CSRF`, `security.protect_host_post`), then the int path parameter (FastAPI's 422, `pathID`), then `_require_admin` 716-723 (`deps.admin`, `admingate.Require`). Every answer is `admin_helpers.back` (`hostweb.Back`) to `/admin/customers` or `/admin/customers/<id>` with `msg=` or `err=` in the request language.

What the handlers do, line for line with Python:

- **create:** `normalise_email(form email)`; empty is `users.email.error.invalid`; `email_taken` is `users.email.error.taken`; `create_account(email, display_name, role="host")` (a ValueError key such as `users.email.error.invalid` or `auth.error.username` becomes the flash; a unique violation is `taken`); audit `user_created`, detail `user=<id>`, actor the admin, owner the new account, actor id from the session; then `_send_invite`; flash `users.invite.sent` with `%(email)s` the normalised address.
- **`_send_invite`:** `login_link.issue(target, purpose=INVITE, remember=True)` (retires the account's unused invite links), `mail_notify.link_mail(kind="account_invite", ..., minutes=72*60)` in English (no `lang`), then `mail.send_now(outbox_id)` in the request, as Python does (not a background task). With mail off nothing is queued and nothing sent; the flash still says sent, as in Python.
- **invite:** target `SELECT * ... WHERE id = ? AND active = 1`; missing, inactive or a blank address is `users.invite.no_email`; `_send_invite`, then audit `invite_sent` (no detail, owner the target); flash `users.invite.sent` with the stored address as it is.
- **email:** target `SELECT * ... WHERE id = ?` (inactive accounts too); missing is `users.email.error.not_found`; the new address normalised (empty is `invalid`); the old one stripped and lower-cased; equal is `users.email.unchanged` (a `msg`); changing an address needs `support_reason` (5 to 300 characters, whitespace folded), else `users.email.error.reason`; `email_taken(email, except_user_id=id)`; `set_account_email` (unverified, `session_version` + 1 when an address is replaced, unused links spent); audit `email_set` (`to=<masked>`) or `email_changed` (`from=<masked> to=<masked> reason=<reason>`); on a change `mail_notify.email_changed(..., stamp=db.utcnow())` (by `support`, both addresses, queued only); flash `users.email.saved`. When the admin changed their own address, the browser gets a new `ubyhost_session` for the new `session_version`, with the old login time (`iat`) and "remember me" of the current cookie and no impersonation (`auth.issue_session` without a workspace, lines 836-850).

**Strings.** Nine keys are appended to `go/internal/web/auth/i18n_keys.txt` only if missing (another brief may add one of them too): `users.email.error.invalid`, `users.email.error.taken`, `users.email.error.not_found`, `users.email.error.reason`, `users.email.unchanged`, `users.email.saved`, `users.invite.sent`, `users.invite.no_email`, `auth.error.username` (`App/app/host_i18n.py`, for example 7397-7402 and 7500-7501 en). `i18n.json` is regenerated from the key file, never hand-edited; `App/tests/test_go_auth_routes.py` proves it is fresh.

**Differences from Python, on purpose or inherited** (all unreachable in practice or shared by every Go route):
1. `normaliseEmail` is the package's existing port of `mail.normalise_email` (`account.go` 204) for a bare address or `Name <addr>`; Python's `email.utils.parseaddr` accepts more exotic forms (comments, quoted local parts) that this form never receives.
2. A database or mail-environment error answers a plain 500 (`serverError`), where Python shows its error page.
3. `except_user_id` in the address check cannot change the outcome (the unchanged check runs first); kept for parity.

**Verified by the brief writer** in a throwaway worktree of go-wave3 at 859d114d5 with exactly these steps, PostgreSQL 16 on a disposable port: `gofmt -l` empty, `go build ./...`, `go vet ./internal/web/auth/ ./cmd/ubyhost-web/` clean; `TestAdminUsersPostGoldenDatabase` (42 cases) and the whole `./internal/web/auth/ ./internal/mail/ ./cmd/ubyhost-web/` suite `ok` on the database, 0 skipped; the golden regenerated from Python passes too; `test_go_auth_routes.py` 2 passed. Also verified with brief 1503 applied after it (route count 21 to 22, the whole package green). Mutations caught: change notice `by="self"`, no `SendNow`, audit detail `id=`, invite link not remembered, reason check skipped, `unchanged` flashed as `saved`, own-account cookie without `rm`, own-account cookie skipped, `invite_sent` with a detail.

Anchors (step 0; each `grep -cF '<anchor>' <file>` prints 1):

| File | Anchor |
|---|---|
| `App/app/routes/admin_accounts.py` | `async def user_create(request: Request):` |
| `App/app/routes/admin_accounts.py` | `def user_invite(user_id: int, request: Request):` |
| `App/app/routes/admin_accounts.py` | `async def user_email_set(user_id: int, request: Request):` |
| `go/internal/mail/auth_queue.go` | `func QueueLinkMail(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, kind string,` |
| `go/internal/mail/auth_queue.go` | `func QueueEmailChanged(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, userID int64,` |
| `go/internal/session/accounts.go` | `func SetAccountEmail(ctx context.Context, db *pgxpool.Pool, userID int64, email string, now time.Time) error {` |
| `go/internal/web/auth/auth.go` | `func Routes(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) []Route {` |
| `go/internal/web/auth/auth_test.go` | `func TestRoutesBuildWithoutPool(t *testing.T) {` |
| `go/internal/web/auth/routes_test.go` | `func sessionToken(t *testing.T, secret string, spec map[string]int64, now time.Time) string {` |
| `go/internal/web/auth/routes_test.go` | `func loadSeed(t *testing.T, ctx context.Context, pool *pgxpool.Pool, seed [][2]any, now time.Time) {` |
| `App/scripts/auth_routes_golden.py` | `def run(case, seed):` |

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/auth/admin_users_post.go` | create (copy) | `userCreate`, `userInvite`, `userEmailSet`, `sendInvite` |
| `go/internal/web/auth/admin_users_post_test.go` | create (copy) | golden replay on PostgreSQL, route list check |
| `go/internal/web/auth/testdata/admin_users.json` | create (copy) | golden, from Python |
| `go/cmd/ubyhost-web/register_web_auth_admin_users_test.go` | create (copy) | the mux serves the new patterns |
| `App/scripts/admin_users_golden.py` | create (copy) | writes the golden from the real FastAPI routes |
| `go/internal/web/auth/auth.go` | edit (script) | three rows appended at the end of `Routes` |
| `go/internal/web/auth/auth_test.go` | edit (script) | route count +3 |
| `go/internal/web/auth/i18n_keys.txt` | edit | up to nine keys appended |
| `go/internal/web/auth/i18n.json` | regenerate | from `i18n_keys.txt` |
| `docs/tasks/1504-go-auth-admin-users.md` | edit | the Status line |
| `docs/tasks/1504-report.md` | create | the report |

`docs/tasks/1504-files/` is part of this brief; do not edit it. No other file may change.

## 4. Steps

0. Checks (from the repo root, one call):

```bash
git status --short | tail -5; ls go/internal/web/auth/admin_users_post.go go/internal/web/auth/admin_users_post_test.go go/internal/web/auth/testdata/admin_users.json go/cmd/ubyhost-web/register_web_auth_admin_users_test.go App/scripts/admin_users_golden.py 2>&1 | grep -c 'No such file'; grep -c 'd.userCreate\|d.userInvite\|d.userEmailSet' go/internal/web/auth/auth.go
cd docs/tasks/1504-files && sha256sum -c <<'EOF' 2>&1 | tail -6
e8b1da3572f3fec9753b232cfb08b9cacb322361c07095f77c751c31d2d96eff  App/scripts/admin_users_golden.py.txt
27be50bf3fb518a2d8546b2b2e8a1932b649bea7f3d2b93fbf81f2d6ee21d0aa  edit_routes.py
9aaacaa894836394a8bdabfcf5438f68485179ba972a5cfedf7bde645620d622  go/cmd/ubyhost-web/register_web_auth_admin_users_test.go.txt
ad8b03c3a2fcd53bef9d7b245bfa4cd3fd622702454d69d9791399758fd16caa  go/internal/web/auth/admin_users_post.go.txt
2892c6f86d2ed74e8933b2d0f74423abc49313e8c811c4b6aec8ff49e6b98a02  go/internal/web/auth/admin_users_post_test.go.txt
b0938aa806984daa073f53ab90064976ca0e48dfd487d1512fd7fe8d754b5417  go/internal/web/auth/testdata/admin_users.json.txt
EOF
```

   Expected: `git status` prints nothing (uncommitted files of another brief: STOP and ask), the `grep -c` lines print `5` and `0`, then six `OK` lines. Then check every anchor of section 2 with `grep -cF '<anchor>' <file>` (one call, eleven commands joined with `;`): eleven `1`. Anything else: STOP (section 8). No commit for step 0.

1. Copy the files and build (from the repo root):

```bash
cd docs/tasks/1504-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && git status --short | tail -6
cd go && gofmt -l internal/web/auth cmd/ubyhost-web 2>&1 | tail -3; go build ./... 2>&1 | tail -5
```

   Expected: `git status` shows exactly the five `??` lines of the created files in section 3; no gofmt or build output (`go: downloading` lines are fine). Commit `1504 step 1`.

2. Register the routes and the strings (from the repo root):

```bash
python3 docs/tasks/1504-files/edit_routes.py 2>&1 | tail -3
for k in users.email.error.invalid users.email.error.taken users.email.error.not_found users.email.error.reason users.email.unchanged users.email.saved users.invite.sent users.invite.no_email auth.error.username; do grep -qxF "$k" go/internal/web/auth/i18n_keys.txt || echo "$k" >> go/internal/web/auth/i18n_keys.txt; done
git diff go/internal/web/auth/auth.go | grep '^[-+]' | grep -v '^[-+][-+]'; git diff --stat | tail -4
cd go && gofmt -l internal/web/auth 2>&1 | tail -3; go vet ./internal/web/auth/ ./cmd/ubyhost-web/ 2>&1 | tail -5
```

   Expected: `added 3 rows` and `route count N -> N+3` (N is 18 if no sibling brief added a route, more otherwise); the `auth.go` diff is exactly these three added lines, the last rows of `Routes`:

```
+		{"POST /admin/users", "/admin/users", d.userCreate},
+		{"POST /admin/users/{id}/invite", "/admin/users/{id}/invite", d.userInvite},
+		{"POST /admin/users/{id}/email", "/admin/users/{id}/email", d.userEmailSet},
```

   The stat lists `auth.go` (3 insertions), `auth_test.go` (2 lines changed) and `i18n_keys.txt` (1 to 9 insertions); no gofmt or vet output. The script printing an `AssertionError`: STOP. Commit `1504 step 2`.

3. Regenerate the catalog and check it (from the repo root). If `App/.venv/bin/python` is missing, first `cd App && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -5; cd ..`.

```bash
cd App && .venv/bin/python -c "import sys; sys.path.insert(0, 'scripts'); from pathlib import Path; import go_host_i18n as g; p = Path('../go/internal/web/auth'); (p / 'i18n.json').write_text(g.render(g.read_keys(p / 'i18n_keys.txt')), encoding='utf-8'); print('wrote i18n.json')" 2>&1 | tail -2
cd App && .venv/bin/python -m pytest tests/test_go_auth_routes.py -q --tb=short -rs 2>&1 | tail -5; cd .. && git status --short | tail -5
```

   Expected: `wrote i18n.json`, `2 passed` (nothing skipped), and `git status` shows only ` M go/internal/web/auth/i18n.json`. Commit `1504 step 3`.

4. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip the start. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`). Skip the start if `su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55504/data status' | tail -1` says `server is running`:

```bash
mkdir -p /var/tmp/pg55504 && chown postgres /var/tmp/pg55504 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg55504/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55504/data -o "-p 55504 -k /var/tmp/pg55504" -l /var/tmp/pg55504/log start' 2>&1 | tail -3
```

   Expected: `server started`. No PostgreSQL 16 binaries at that path: write "CI only" in the report, run section 6 without the database, and set the report `blocked`. Then run the tests (from the repo root):

```bash
cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55504/postgres go test ./internal/web/auth/ ./cmd/ubyhost-web/ -count=1 -v -run '^TestAdminUsersPostGoldenDatabase$|^TestAdminUsersPostRoutes$|^TestRoutesBuildWithoutPool$|^TestCatalogHasEveryKey$|^TestAuthAdminUsersRoutesRegistered$' 2>&1 | grep -E '^(--- |ok|FAIL)|SKIP' | tail -12
cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55504/postgres go test ./internal/web/auth/ -count=1 -v -run '^TestAdminUsersPostGoldenDatabase$' 2>&1 | grep -c '^    --- PASS'
cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55504/postgres go test ./internal/web/auth/... ./internal/mail/... ./internal/session/... ./cmd/ubyhost-web/... -count=1 2>&1 | grep -v ' INFO ' | tail -10
```

   Expected: five `--- PASS` lines and two `ok` lines, no `SKIP`; then `42`; then only `ok` lines. No commit (nothing changed).

5. Check the golden against Python once more (from the repo root): regenerate it, replay it, then put the committed one back. The regenerated file differs in bytes (cookie times rounded to the second, a fresh encrypted seed value), so its hash is not checked; the replay is the check.

```bash
cd App && .venv/bin/python scripts/admin_users_golden.py 2>&1 | grep -v ' INFO ' | tail -3; cd ..
cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55504/postgres go test ./internal/web/auth/ -count=1 -run '^TestAdminUsersPostGoldenDatabase$' 2>&1 | grep -v ' INFO ' | tail -5; cd ..
git checkout -- go/internal/web/auth/testdata/admin_users.json && git status --short | tail -3
```

   Expected: `wrote go/internal/web/auth/testdata/admin_users.json`, then `ok`, then `git status` prints nothing. A failure here, when step 4 passed, means Python changed since the brief was written: STOP and report the failing case names. No commit.

6. Run section 6. Write the report (section 9), set `Status: review` in this file and commit both as `1504 report`. Do not push or open a PR.

## 5. Do not touch

`go/internal/hostweb/`, `go/internal/session/`, `go/internal/mail/`, `go/internal/jobs/`, `go/internal/clientip/`, every existing file in `go/internal/web/auth/` except the two lines of `auth_test.go`, the appended `Routes` rows of `auth.go`, `i18n_keys.txt` and the regenerated `i18n.json` (in particular `routes_test.go`, `testdata/routes.json`, `finish.go`, `admin.go`, `account.go`), `go/cmd/ubyhost-web/` except the new test file, `go/go.mod`, `go/go.sum`, `App/app/`, `App/tests/`, `App/scripts/auth_routes_golden.py`, `deploy/` (no `UBYHOST_GO_PATHS` change), `docs/context/`, `docs/tasks/1504-files/`. Never print a secret, token, link or e-mail address from a real system. Rules 2, 3, 4, 5 and 11 as in section 2.

## 6. Commands

From the repo root:

- `cd go && gofmt -l internal/web/auth cmd/ubyhost-web 2>&1 | tail -5` prints nothing.
- `cd go && go build ./... 2>&1 | tail -30` prints nothing.
- `cd go && go vet ./internal/web/auth/... ./cmd/ubyhost-web/... 2>&1 | tail -30` prints nothing.
- The three test commands of step 4, with the outputs stated there (0 skipped; report the `SKIP` count, which must be 0).
- `cd App && .venv/bin/python -m pytest tests/test_go_auth_routes.py -q --tb=short -rs 2>&1 | tail -5` prints `2 passed`.
- `cd go && go mod tidy -diff 2>&1 | grep -v downloading | tail -5` prints nothing.
- `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` shows no error naming 1504.

Test-map: no row covers these Go packages; the commands above are this brief's tests.

## 7. Acceptance

- [ ] `git log --oneline --grep='^1504 '` lists steps 1, 2, 3 and the report.
- [ ] `for c in $(git log --format=%h --grep='^1504 '); do git show --name-only --format= $c; done | sort -u` lists exactly the files of section 3.
- [ ] The copied files equal the sidecar: `cd docs/tasks/1504-files && for f in $(find . -name '*.txt' | sed 's|\.txt$||'); do cmp $f.txt ../../../$f; done` prints nothing.
- [ ] Step 4 printed five `--- PASS`, `42`, only `ok` lines and no `SKIP`; step 5 printed `ok`.
- [ ] `for c in $(git log --format=%h --grep='^1504 '); do git show --name-only --format= $c; done | grep -E 'go\.mod|go\.sum|App/app/|App/tests/|hostweb/|session/|mail/|deploy/|routes_test\.go|routes\.json'` prints nothing.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor is not found, a file to create exists, a sha256 differs, or `edit_routes.py` raises;
- a test fails twice (never change the code: it is fixed by hash);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1504-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (the section 7 file list).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the full diff of:

- `go/internal/web/auth/admin_users_post.go`: the gate order (CSRF, path id, admin); `userEmailSet` reads the target without `active = 1` (as Python) and re-attaches a session only for the admin's own account after a change (new `session_version`, old `iat`, `rm` kept, no workspace); the invite link is `remember` and English; `SendNow` runs in the request; no address, token or link is logged.
- `go/internal/web/auth/admin_users_post_test.go` and `App/scripts/admin_users_golden.py`: the same normalisation on both sides (`<now>`, `<ts>`, `<hash>`, `-<hex>`), the watched SQL comes from the golden itself; the script calls the real routes through `auth_routes_golden.run`.
- `go/internal/web/auth/auth.go`: only the three appended rows. `auth_test.go`: only the count.
- Verified by the brief writer (see section 2): build, vet, 42 golden cases on PostgreSQL 16 with 0 skipped, regenerated golden green, catalog freshness test green, nine mutations caught; 1503 applied after it stays green.

## Owner steps

1. Nothing for this brief alone: it is merged with the one big PR and changes nothing in production (no route is switched, no environment change).
2. To switch it, after the deploy: on the server, add `/admin/users /admin/users/*/invite /admin/users/*/email` inside the double quotes of `UBYHOST_GO_PATHS` in `.env` (space-separated, see `docs/ENVIRONMENT.md`), from `deploy/lightsail` run `./scripts/caddy-validate.sh`, then `docker compose up -d caddy`. Rollback: remove them again and run the same two commands. `/admin/users` alone closes the method gap (its `GET` and `POST` are both Go then). Switch them together with brief 1509's `/admin/users/*/schedule-deletion` (and 1510's export once it is unblocked) so the whole `/admin/users` area moves at once.
3. Then, on a test account only: on a customer page set a new login e-mail with a reason and check the page says "Login e-mail saved."; press the invitation button for a host and check the page says "Invitation link sent to ..." and the mail arrives.
