# 1501 report

Status: review. Branch go-wave3 (one big PR mode: no branch, no push, no PR).

## 1. Files changed (commits `1501 step 1` to `1501 step 4`)

- go/internal/clientip/: clientip.go, clientip_test.go, testdata/clientip.json
- go/internal/turnstile/: turnstile.go, turnstile_test.go, turnstile_db_test.go, testdata/turnstile.json
- go/internal/mail/: auth_link.go, auth_queue.go, auth_link_test.go, auth_queue_test.go, testdata/auth_mail.json
- go/internal/web/auth/: finish.go, finish_test.go, testdata/finish_login.json
- App/scripts/auth_shared_golden.py
- docs/tasks/1501-go-auth-shared.md (Status line only), docs/tasks/1501-report.md

## 2. Commands (last lines of output)

- Step 0: `git status --short` empty; missing-file count `6`; sha256 `16 OK`; nine anchors `1` each.
- Step 1 (clientip, turnstile): gofmt, build, vet silent; `ok` for turnstile; clientip passed; 0 SKIP.
- Step 2 (mail): `ok github.com/.../go/internal/mail 6.589s`; 0 SKIP.
- Step 3 (web/auth): `ok .../go/internal/web/auth 16.197s`; 0 SKIP.
- Step 4 (golden script): four `wrote go/internal/...` lines; hashes equal step 0 (clientip 8f91d9f4..., turnstile 3bbaf1c8..., finish_login eede7383..., auth_mail a233d3ef...); `git status` shows only the script before commit.
- Section 6: gofmt, build, vet silent; `go test` for the nine listed packages `ok` (web/auth, session, session/admingate, mail, hostweb, hostweb/layout, clientip, turnstile, cmd/ubyhost-web); `go mod tidy -diff` silent; `context_lint: OK`.

PostgreSQL 16 on port 5633 (disposable, data under /var/tmp/pg1501). 0 SKIP lines in all runs with `UBYHOST_TEST_DATABASE_URL` set.

## 3. Section 7

- [x] Steps 1 to 4 committed; report committed as `1501 report`.
- [x] Files as listed in section 1 (17 section-3 files plus the status line).
- [x] Copies equal the sidecar (hashes checked in step 0 and step 4).
- [x] Section 6 output as stated.
- [x] No go.mod, go.sum, App/app, hostweb, cmd or deploy file in the commits.

## 4. Deviations

- App/.venv was missing and was created with `requirements.txt` only (as step 4 says). It is untracked and not committed.

## 5. Questions

None.

## 6. Owner steps left

None for this brief. Brief 1502 adds the four Turnstile and proxy keys to the `ubyhost-go` service before `/login` moves to Go (brief section 2).
