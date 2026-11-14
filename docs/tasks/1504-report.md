# 1504 report

## 1. Files changed

- `go/internal/web/auth/admin_users_post.go` (create)
- `go/internal/web/auth/admin_users_post_test.go` (create)
- `go/internal/web/auth/testdata/admin_users.json` (create)
- `go/cmd/ubyhost-web/register_web_auth_admin_users_test.go` (create)
- `App/scripts/admin_users_golden.py` (create)
- `go/internal/web/auth/auth.go` (edit)
- `go/internal/web/auth/auth_test.go` (edit)
- `go/internal/web/auth/i18n_keys.txt` (edit)
- `go/internal/web/auth/i18n.json` (regenerate)
- `docs/tasks/1504-go-auth-admin-users.md` (Status)
- `docs/tasks/1504-report.md` (this file)

## 2. Commands (last 5 lines)

**Step 0:** sha256 all OK; anchors 11×1; grep `No such file` 5, route handlers 0.

**Step 1 copy/build:** five `??` new files; go build clean.

**Step 2:** `added 3 rows` / `route count 23 -> 26`; vet clean.

**Step 3:** `wrote i18n.json`; pytest `2 passed`.

**Step 4 PG:** `server started` (port 55504); five `--- PASS`, two `ok`, no SKIP; golden subtests `42`; package suite all `ok`.

**Step 5:** `wrote admin_users.json`; replay `ok`; status clean after checkout.

**§6:** gofmt/build/vet/tidy/context_lint clean; pytest `2 passed`.

## 3. Acceptance (§7)

- [x] Commits: steps 1, 2, 3, report.
- [x] Changed files match §3 only.
- [x] Sidecar `cmp` would be silent (copied from hashes).
- [x] Step 4: five PASS, 42, all ok, SKIP **0**; step 5 ok.
- [x] No forbidden paths in commits.

## 4. Deviations

- PostgreSQL 16 was not on the VM; installed `postgresql-16` via apt; used `sudo chown` / `sudo -u postgres` for `/var/tmp/pg55504` (plain `su postgres` chown failed).

## 5. Questions

None.

## 6. Owner steps

Per brief §Owner: no deploy for this brief alone; switch paths in `UBYHOST_GO_PATHS` when the big PR ships.