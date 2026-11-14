# 1624 report: Go mail unsubscribe page (GET and POST /mail/unsubscribe/{token})

Status: review (one-big-PR mode, branch go-wave3, not pushed)

## 1. Files changed

- `go/internal/web/public/templates/unsub/unsubscribe.tmpl` (create, sha256 verified)
- `go/internal/web/public/unsub_page.go` (create, sha256 verified)
- `go/internal/web/public/unsub_store.go` (create, sha256 verified)
- `go/internal/web/public/unsub_token.go` (create, sha256 verified)
- `go/internal/web/public/unsub_test.go` (create, sha256 verified)
- `go/internal/web/public/unsub_shots_test.go` (create, sha256 verified)
- `go/cmd/ubyhost-web/register_web_public.go` (step 5: two `mux.Handle` lines for GET and POST, plus the `UnsubDeps` line; 3 insertions)
- `docs/tasks/1624-go-public-unsubscribe.md` (Status line only)
- `docs/tasks/1624-report.md` (this file)

Commits: `1624 step 1` (68bd41d), `1624 step 5`, then `1624 step 11` (brief status and this report).

## 2. Commands

- Phase 0 anchors: all counts matched (catalog_unsub.json and testdata/unsub/cases.json present; golden helpers 5; public.go 4; langCookieMaxAge 2; UnsubscribeToken/EmailHash 2; NewTimedSerializer 1; UTCNow 1; register loop 1).
- Step 1: `sha256sum` of all six files matched the brief (values printed and compared by hand; the `sha256sum -c` form was refused by the worktree guard, so the checks were done by reading the printed hashes).
- Step 2: `gofmt -l internal/web/public; go vet ./internal/web/public/` gave no output.
- Step 3: `go test ./internal/web/public/ -count=1 -v -run 'TestUnsubTokenFromGo|TestCSRFTokenBinding|TestUnsubEveryActionEscapes'`
  ```
  --- PASS: TestUnsubTokenFromGo (0.00s)
  --- PASS: TestCSRFTokenBinding (0.00s)
  --- PASS: TestUnsubEveryActionEscapes (0.00s)
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/public	0.020s
  ```
- Step 5: `gofmt -l cmd internal/web/public; go build ./...; go vet ./internal/web/public/... ./cmd/ubyhost-web/...` gave no output; `go test ./internal/web/public/... ./cmd/ubyhost-web/... -count=1`
  ```
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/public	0.207s
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	0.105s
  ```
- Step 6: PostgreSQL 16 on port 55744 (data under /var/tmp/pg-1624, stopped and removed afterwards). `UBYHOST_TEST_DATABASE_URL=... go test ./internal/web/public/ -count=1 -v -run 'TestUnsub'`
  ```
  --- PASS: TestUnsubGolden (0.72s)
  --- PASS: TestUnsubSignedInHost (0.71s)
  --- PASS: TestUnsubLoadsNothingFromOutside (0.54s)
  --- PASS: TestUnsubTokenFromGo (0.00s)
  --- PASS: TestUnsubEveryActionEscapes (0.00s)
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/public	1.992s
  ```
- Step 11: `python3 scripts/context_lint.py | grep -v '^WARN'` gave `context lint: OK`.

SKIP count in the commands above: 0. No test was skipped.

## 3. Acceptance (§7)

- [x] Step 1 printed OK for all 6 files (checked by hand, see above).
- [x] Step 3 shows three PASS and ok; step 5 shows ok twice.
- [x] Step 6 shows TestUnsubGolden PASS (database tests ran, not skipped).
- [x] Commits: `1624 step 1`, `1624 step 5`, `1624 step 11`.
- [x] 9 PNGs in `/mnt/project-files/ux-shots/public-unsubscribe/`, all ok (no horizontal overflow).

## 4. Screenshots

Taken with Node Playwright (the venv has no Python Playwright). Each width ran against a freshly seeded server, because a POST in the 390 px run opts the host out and the later widths would otherwise show the confirmation state.

- `form-390.png`: Czech page, logo, EN/CS/VI switch with CS selected, test-environment banner (non-production), the title "Tipy k nastavení e-mailem", the question, and one full-width red button "Odhlásit tipy". Footer links below. Nothing cut off.
- `done-390.png`: after the button press: the title and "Hotovo. Tipy k nastavení už dostávat nebudete. V Nastavení je můžete znovu zapnout." Footer. Nothing cut off.
- `invalid-390.png`: forged token: "Tento odkaz pro odhlášení není platný..." message and footer. Nothing cut off.

## 5. Deviations

- The POST writes its rows in one transaction (Python commits each statement alone), as the brief already says.
- Screenshot run: the first 390 px pass ran in the same server session as 768 and 1280, so the 768 px "done" click timed out (the host was already opted out). Re-ran each width on a restarted server; the final PNGs come from those runs. No product change.
- Screenshots were taken with Node Playwright, not the Python script in the brief (no Python Playwright in the venv).

## 6. Questions

None.

## 7. Owner steps left

None in this brief. The `UBYHOST_GO_PATHS` switch for `/mail/unsubscribe/*` stays a separate step (after the mail job's links are checked once on staging).
