# 1330-fix-1: stay fee review findings

Status: todo
Depends on: 1330 | Base commit: bafc793 | Branch: claude/1330-go-stay-fees
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B
Report: docs/tasks/1330-fix-1-report.md

## 1. Objective

Fix four review findings in the Go stay fee routes of brief 1330 so they answer like FastAPI: HEAD on the CSV route is a 405, a path id outside int64 is "not found" instead of 422, multipart/form-data bodies are read, and the test seeds the legal version it also sets in its env. Only `go/internal/web/stayfees/handlers.go` and `actions_test.go` change; the golden JSON files do not.

## 2. Context

All code is finished and dry-run. It is one `git apply` patch, inside this brief between the lines `<!-- patch:start -->` and `<!-- patch:end -->` (§4). You extract it, check its sha256, apply it, run the tests and commit. You write no code. If a sha256 differs or `git apply --check` fails: STOP (§8).

What the patch does (for the reviewer; you need not read the code):

1. **HEAD on `GET /stay-fees/{apartment_id}/csv`.** Go 1.22 `GET` patterns also match HEAD, so HEAD ran login, decrypted the CSV and wrote a `stay_fee_csv` audit row. FastAPI lists GET only and answers HEAD with `405`, `Allow: GET`, `Content-Type: application/json`, body `{"detail":"Method Not Allowed"}` (checked with the App venv: FastAPI TestClient, HEAD on a GET-only route). `CSVHandler` now answers exactly that first, before CSRF, login or any DB access (new `methodNotAllowed`). Test `TestCSVHeadNotAllowed` runs with a nil pool, so any DB access would panic.
2. **Path ids outside int64.** Pydantic parses `99999999999999999999` (and with sign, `+00…`, `-…`) as an int; on Postgres psycopg sends it as numeric and the lookup finds no row (checked: `SELECT count(*) FROM t WHERE id = %s` with `10**20` gives 0). `pathID` now returns a `pathInt{id, text, none}`: ParseInt first; else `big.Int.SetString(raw, 10)` (ASCII digits, optional sign, no underscores) gives `none: true` and `text` = `str(int)`; anything else stays 422. New `pathApartment` returns no apartment for `none` without a query; the undo adjustment and filing lookups are skipped for `none` (found = false / row = nil), so each handler takes its own not-found branch: `flash.error.no_such_apartment`, the undo plain redirect, or `flash.stay_fees.report_blocked`. The CSV route builds its identity-hidden and future-month redirects from `text` (canonical, as Python `str(apartment_id)`). After a successful lookup the handlers use `apt.ID` (equal to the path id). Test `TestOverflowIDNotFound` replays 12 golden not-found cases with the id replaced and expects the golden answer, checks three non-integer ids stay 422, and checks no row changed.
3. **multipart/form-data.** Python `_supplied_csrf_token` and the routes use `await request.form()`, which reads multipart. Today `hostweb.CSRF` (read-only, `go/internal/hostweb/gate.go` 129-153) only calls `r.ParseForm`, which skips multipart bodies. `deps.enter` now, for a POST whose media type is `multipart/form-data`, wraps the body in `http.MaxBytesReader` (1 MiB, Starlette's default part size) and calls `r.ParseMultipartForm` once **before** `hostweb.CSRF`. That fills `r.PostForm`, so CSRF's `ParseForm` reads no body and finds `_csrf`; the later `ParseForm` in `enter` is a no-op. Interaction with draft PR #986 (another thread; makes `hostweb.CSRF` read multipart itself): Go's `ParseMultipartForm` returns at once when `r.MultipartForm` is already set, so CSRF's own call after #986 is a no-op and the body is read once, with or without #986. Nothing here depends on #986. A parse error is logged and the request goes on (CSRF then fails if the token was only in the body). Test `TestMultipartForm` posts the golden "scope ok" case as multipart with the token in `_csrf` and no header, and expects the golden redirect and the saved ruling.
4. **Legal version in the test.** `session.AcceptancePending` reads `UBYHOST_TERMS_VERSION`, `UBYHOST_PRIVACY_VERSION`, `UBYHOST_DPA_VERSION` through `versionOr`, defaulting to the unexported `defaultVersion = "1.7"` (`go/internal/session/session.go` 32, 284-320); the default is not reachable from package `stayfees`. The test now sets all three in a shared `goldenEnv()` to `acceptedVersion = "test-accepted"` and seeds `legal_acceptance` with the same constant, so it no longer depends on the default. Dry-run check: seeding `'1.7'` with this env makes the DB tests fail, so the env is really read.

Correction of brief 1330 deviation 2 (the old brief is not edited; the PR body uses this text): "Month and form ids: Python `str.isdigit` also accepts non-ASCII digits (a month like `２０２６-10` parses; a form id like `٣` is looked up as 3; `²` crashes `int()` with a 500). Go accepts only ASCII digits: such a month falls back to the default month, such a form id means not found. Path ids: FastAPI answers 422 for non-ASCII digits, as Go does, and an id outside int64 is looked up and not found, as Go now does (1330-fix-1). Left: pydantic also accepts `1_0`, ` 5` and `5.0` as path ids, where Go answers 422; on SQLite (tests only) Python answers 500 for an id outside int64."

Known, left as is (not in this brief): FastAPI's 422 body is a detail list, Go's is `{"detail":"Unprocessable Entity"}`; other methods (PUT, DELETE) get Go's mux 405 in text/plain, FastAPI's is JSON.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/stayfees/handlers.go` | edit | HEAD 405, `pathInt`/`pathApartment`, multipart parse in `enter` |
| `go/internal/web/stayfees/actions_test.go` | edit | `goldenEnv`/`acceptedVersion`, three new tests |
| `docs/tasks/1330-fix-1-report.md` | new | your report |

No other file may change. The golden JSON files and `App/` do not change. This brief is already committed.

## 4. Steps

Run every command from the repo root unless it says `cd`.

1. Extract the patch and check it:

```bash
awk '/^<!-- patch:start -->$/{f=1;next} /^<!-- patch:end -->$/{f=0} f' docs/tasks/1330-fix-1-go-stay-fee-review.md | sed '1d;$d' > /tmp/1330-fix-1.patch && sha256sum /tmp/1330-fix-1.patch 2>&1 | tail -3 && git apply --check /tmp/1330-fix-1.patch 2>&1 | tail -10
```

   Expect `6321385313e441c615fba83cfa87d1939346eac0b7027486ee370d4c61ad446d  /tmp/1330-fix-1.patch` and nothing from `git apply --check`. Otherwise STOP.
2. Apply it and check the two files:

```bash
git apply /tmp/1330-fix-1.patch && git status --short 2>&1 | tail -10 && sha256sum -c 2>&1 <<'EOF2' | tail -5
762c16900bb6a49f578cc359882c3d83f653044cc235025e48e52730f5a5dbca  go/internal/web/stayfees/handlers.go
22f6acac16ec5947eeb01ece5787306e86b8efef7e82c70d3cb6aa6d1192fca6  go/internal/web/stayfees/actions_test.go
EOF2
```

   Expect exactly ` M go/internal/web/stayfees/actions_test.go` and ` M go/internal/web/stayfees/handlers.go`, then two `OK` lines. Otherwise STOP.
3. Run the commands of §6. Commit: `git add go/internal/web/stayfees/handlers.go go/internal/web/stayfees/actions_test.go && git commit -m "1330-fix-1 step 3: stay fee review fixes" 2>&1 | tail -5`
4. `python3 scripts/context_lint.py 2>&1 | tail -3` ends with `context lint: OK`.
5. Write the report (§9), set this brief's `Status: review`, commit both as `1330-fix-1 step 5: report`. Do not push: the orchestrator pushes. Put in the report, for the PR body: the four fixes of §2 (one line each), the corrected deviation 2 text of §2, and "No new outbound request. No new personal-data field. Routes stay off: Caddy routes only UBYHOST_GO_PATHS to Go."

## 5. Do not touch

Read-only: `go/internal/hostweb/`, `go/internal/session/`, `go/internal/secure/`, `go/cmd/ubyhost-web/` (all of it), `go/go.mod`, `go/go.sum`, `go/internal/web/stayfees/testdata/`, `go/internal/web/stayfees/i18n.json`, `App/` (all of it), `docs/tasks/1330-go-stay-fee-actions.md`, every env file, Caddy file and doc. Never edit a patched file by hand: if a test fails, STOP (§8). Hard rules 2 (no new outbound request, no new personal-data field), 3, 5, 8.

## 6. Commands

Go needs Postgres on port 54330. If `pg_isready -h 127.0.0.1 -p 54330` does not say `accepting connections`, start it (pg_ctl refuses root):

```bash
su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1330/data -o '-p 54330 -k /var/tmp/pg1330' -l /var/tmp/pg1330/log start" 2>&1 | tail -3
```

If `/var/tmp/pg1330/data` does not exist, first run: `mkdir -p /var/tmp/pg1330 && chown postgres /var/tmp/pg1330 && su postgres -c "/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1330/data -A trust >/dev/null" 2>&1 | tail -3`

- `cd go && gofmt -l internal/web/stayfees cmd/ubyhost-web && go vet ./internal/web/stayfees/ ./cmd/ubyhost-web/ 2>&1 | tail -30` -> no output.
- `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:54330/postgres go test ./internal/web/stayfees/ ./cmd/ubyhost-web/ -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL)|SKIP' | tail -30` -> every line `--- PASS`, two `ok` lines, no `SKIP`, no `FAIL`. These must say PASS (not skipped): `TestActionsMatchPython`, `TestCSRFRequired`, `TestCSVHeadNotAllowed`, `TestOverflowIDNotFound`, `TestMultipartForm`.

No Python command: the golden script and `App/` are unchanged.

## 7. Acceptance

- [ ] Patch sha256 `6321385313e441c615fba83cfa87d1939346eac0b7027486ee370d4c61ad446d`; after step 2 the two file hashes match.
- [ ] gofmt and go vet print nothing.
- [ ] Go tests all PASS, the five named tests run (not skipped).
- [ ] `git diff --stat bafc793..HEAD` lists only §3 paths and this brief.
- [ ] `python3 scripts/context_lint.py` ends `context lint: OK`.

## 8. Stop and ask

Stop, and write the report, if:

- the patch sha256 or a file sha256 differs, or `git apply --check` prints anything;
- a test fails twice, or a DB test skips;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1330-fix-1-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat bafc793..HEAD`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- go/internal/web/stayfees/handlers.go: `enter` (multipart parse before CSRF, body cap), `pathID`/`pathInt`/`pathApartment` (no query for `none`; `apt.ID` after lookup), `UndoHandler` and `filingMark` (skipped lookups), `CSVHandler` (HEAD 405 first; redirects use `text`; `backPath` set only when the apartment exists).
- go/internal/web/stayfees/actions_test.go: `goldenEnv` used by every DB test; the three new tests.

## Owner steps

1. Wait for CI to go green on the draft PR of brief 1330, then merge it with `scripts/merge-pr-on-green.sh`. Nothing is switched on by the merge.

## Patch

Do not edit. Step 1 extracts it.

<!-- patch:start -->
```diff
diff --git a/go/internal/web/stayfees/actions_test.go b/go/internal/web/stayfees/actions_test.go
index ebd5c77..8346eaf 100644
--- a/go/internal/web/stayfees/actions_test.go
+++ b/go/internal/web/stayfees/actions_test.go
@@ -7,6 +7,7 @@ import (
 	"encoding/hex"
 	"encoding/json"
 	"fmt"
+	"mime/multipart"
 	"net/http"
 	"net/http/httptest"
 	"net/url"
@@ -28,6 +29,23 @@ import (
 // goldenSecret is the UBYHOST_SECRET_KEY App/scripts/stay_fee_actions_golden.py runs with.
 const goldenSecret = "golden-secret-key-not-for-real-use"
 
+// acceptedVersion is the legal version the tests run with: goldenEnv sets
+// UBYHOST_TERMS_VERSION, UBYHOST_PRIVACY_VERSION and UBYHOST_DPA_VERSION, which
+// session.AcceptancePending reads, and seed stores it as accepted. The test so
+// does not depend on the session package's unexported default.
+const acceptedVersion = "test-accepted"
+
+// goldenEnv is the environment every test runs with.
+func goldenEnv() func(string) string {
+	env := map[string]string{
+		"UBYHOST_SECRET_KEY":      goldenSecret,
+		"UBYHOST_TERMS_VERSION":   acceptedVersion,
+		"UBYHOST_PRIVACY_VERSION": acceptedVersion,
+		"UBYHOST_DPA_VERSION":     acceptedVersion,
+	}
+	return func(k string) string { return env[k] }
+}
+
 type goldenTable struct {
 	Table   string   `json:"table"`
 	Columns []string `json:"columns"`
@@ -174,12 +192,12 @@ func seed(t *testing.T, pool *pgxpool.Pool, g golden) {
 		}
 	}
 	// acceptance.pending is switched off in the golden script; here every
-	// account has accepted the current versions.
+	// account has accepted the version goldenEnv names.
 	for _, uid := range []int{1, 2, 3} {
 		for _, doc := range []string{"terms", "privacy", "dpa"} {
 			if _, err := pool.Exec(ctx,
-				`INSERT INTO legal_acceptance (user_account_id, document, version, accepted_at, method) VALUES ($1, $2, '1.7', '2026-01-01', 'clickwrap')`,
-				uid, doc); err != nil {
+				`INSERT INTO legal_acceptance (user_account_id, document, version, accepted_at, method) VALUES ($1, $2, $3, '2026-01-01', 'clickwrap')`,
+				uid, doc, acceptedVersion); err != nil {
 				t.Fatal(err)
 			}
 		}
@@ -355,8 +373,7 @@ func TestActionsMatchPython(t *testing.T) {
 	if err != nil {
 		t.Fatal(err)
 	}
-	env := map[string]string{"UBYHOST_SECRET_KEY": goldenSecret}
-	getenv := func(k string) string { return env[k] }
+	getenv := goldenEnv()
 	keys, err := secure.LoadDataKeys(getenv)
 	if err != nil {
 		t.Fatal(err)
@@ -440,8 +457,7 @@ func TestCSRFRequired(t *testing.T) {
 	pool := testPool(t)
 	seed(t, pool, g)
 	at, _ := time.Parse(time.RFC3339, g.Now)
-	env := map[string]string{"UBYHOST_SECRET_KEY": goldenSecret}
-	getenv := func(k string) string { return env[k] }
+	getenv := goldenEnv()
 	mux := newMux(pool, getenv, func() time.Time { return at })
 	req := httptest.NewRequest(http.MethodPost, "/stay-fees/12/filings/1/sent", strings.NewReader("month=2026-10"))
 	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
@@ -475,3 +491,163 @@ func TestRoutesNeedNoPool(t *testing.T) {
 		mux.Handle(r.Pattern, r.Handler)
 	}
 }
+
+// goldenCaseNamed returns the golden case with this name.
+func goldenCaseNamed(t *testing.T, g golden, name string) goldenCase {
+	t.Helper()
+	for _, c := range g.Cases {
+		if c.Name == name {
+			return c
+		}
+	}
+	t.Fatalf("golden file has no case %q", name)
+	return goldenCase{}
+}
+
+// TestCSVHeadNotAllowed: FastAPI lists GET only, so HEAD is a 405 with
+// Allow: GET before any dependency runs. The nil pool proves no DB access.
+func TestCSVHeadNotAllowed(t *testing.T) {
+	at := time.Date(2026, 11, 13, 9, 0, 0, 0, time.UTC)
+	mux := newMux(nil, goldenEnv(), func() time.Time { return at })
+	req := httptest.NewRequest(http.MethodHead, "/stay-fees/12/csv?month=2026-10", nil)
+	req.AddCookie(&http.Cookie{Name: session.CookieName, Value: sessionFor("host1", at)})
+	rec := httptest.NewRecorder()
+	mux.ServeHTTP(rec, req)
+	if rec.Code != http.StatusMethodNotAllowed {
+		t.Fatalf("status %d, want 405", rec.Code)
+	}
+	if got := rec.Header().Get("Allow"); got != "GET" {
+		t.Errorf("Allow %q, want GET", got)
+	}
+	if got := rec.Header().Get("Content-Type"); got != "application/json" {
+		t.Errorf("Content-Type %q, want application/json", got)
+	}
+	if got := rec.Body.String(); got != `{"detail":"Method Not Allowed"}` {
+		t.Errorf("body %q", got)
+	}
+}
+
+// TestOverflowIDNotFound: an all-digit path id outside int64 parses in
+// FastAPI and Postgres finds no row for it, so each route takes its not-found
+// branch. Every case replays a golden not-found case with the id replaced and
+// expects the golden answer (redirect texts carry str(int) of the id). A
+// non-integer id stays a 422.
+func TestOverflowIDNotFound(t *testing.T) {
+	g := loadGolden(t)
+	pool := testPool(t)
+	seed(t, pool, g)
+	at, err := time.Parse(time.RFC3339, g.Now)
+	if err != nil {
+		t.Fatal(err)
+	}
+	getenv := goldenEnv()
+	keys, err := secure.LoadDataKeys(getenv)
+	if err != nil {
+		t.Fatal(err)
+	}
+	mux := newMux(pool, getenv, func() time.Time { return at })
+	noSuchApartment := str(goldenCaseNamed(t, g, "csv foreign apartment").Location)
+	const big = "99999999999999999999"
+	cases := []struct {
+		golden             string
+		pathOld, pathNew   string
+		whereOld, whereNew string
+	}{
+		{"undo foreign apartment", "/20/", "/" + big + "/", "", ""},
+		{"undo missing row", "/999/", "/" + big + "/", "", ""},
+		{"scope missing apartment", "/999/", "/" + big + "/", "", ""},
+		{"copy foreign target", "/20/", "/" + big + "/", "", ""},
+		{"paid missing apartment (python 500)", "/999/", "/" + big + "/", "", ""},
+		{"sent foreign apartment", "/20/", "/" + big + "/", "", ""},
+		{"sent filing of another apartment", "/filings/1/", "/filings/" + big + "/", "", ""},
+		{"paid filing foreign apartment", "/20/", "/-" + big + "/", "", ""},
+		{"paid filing wrong month", "/filings/3/", "/filings/" + big + "/", "", ""},
+		{"csv missing apartment", "/999/", "/" + big + "/", "", ""},
+		{"csv future month", "/12/", "/+000" + big + "/", "/12/", "/" + big + "/"},
+		{"csv identity hidden", "/12/", "/" + big + "/", "/12?", "/" + big + "?"},
+	}
+	saved := identityVisible
+	t.Cleanup(func() { identityVisible = saved })
+	before := normal(t, snapshot(t, pool, keys))
+	for _, tc := range cases {
+		c := goldenCaseNamed(t, g, tc.golden)
+		c.Path = strings.Replace(c.Path, tc.pathOld, tc.pathNew, 1)
+		wantStatus, wantLocation := c.Status, str(c.Location)
+		if strings.HasSuffix(c.Name, "(python 500)") {
+			wantStatus, wantLocation = http.StatusSeeOther, noSuchApartment
+		}
+		if tc.whereOld != "" {
+			wantLocation = strings.Replace(wantLocation, tc.whereOld, tc.whereNew, 1)
+		}
+		identityVisible = saved
+		if c.IdentityHidden {
+			identityVisible = func(*session.Host) bool { return false }
+		}
+		rec := httptest.NewRecorder()
+		mux.ServeHTTP(rec, request(t, c, at))
+		if rec.Code != wantStatus || rec.Header().Get("Location") != wantLocation {
+			t.Errorf("%s: %d %q, want %d %q (%s)", c.Path, rec.Code, rec.Header().Get("Location"), wantStatus, wantLocation, rec.Body.String())
+		}
+	}
+	identityVisible = saved
+	for _, path := range []string{"/stay-fees/1x/csv", "/stay-fees/%D9%A3/csv", "/stay-fees/12/filings/1.5/sent"} {
+		c := goldenCase{Method: http.MethodGet, Path: path, Who: &[]string{"host1"}[0]}
+		if strings.HasSuffix(path, "/sent") {
+			c.Method = http.MethodPost
+		}
+		rec := httptest.NewRecorder()
+		mux.ServeHTTP(rec, request(t, c, at))
+		if rec.Code != http.StatusUnprocessableEntity {
+			t.Errorf("%s: status %d, want 422", path, rec.Code)
+		}
+	}
+	if after := normal(t, snapshot(t, pool, keys)); !reflect.DeepEqual(after, before) {
+		t.Errorf("a not-found request changed rows:\n got %v\nwant %v", after, before)
+	}
+}
+
+// TestMultipartForm: request.form() reads multipart/form-data too. The golden
+// "scope ok" case, posted as multipart with the CSRF token in the _csrf field
+// (no header), gives the same redirect and saves the ruling.
+func TestMultipartForm(t *testing.T) {
+	g := loadGolden(t)
+	pool := testPool(t)
+	seed(t, pool, g)
+	at, err := time.Parse(time.RFC3339, g.Now)
+	if err != nil {
+		t.Fatal(err)
+	}
+	mux := newMux(pool, goldenEnv(), func() time.Time { return at })
+	c := goldenCaseNamed(t, g, "scope ok")
+	ck, token := csrfPair(t, at)
+	var body strings.Builder
+	mw := multipart.NewWriter(&body)
+	if err := mw.WriteField("_csrf", token); err != nil {
+		t.Fatal(err)
+	}
+	for _, k := range []string{"month", "reference", "rule"} {
+		if err := mw.WriteField(k, c.Form[k]); err != nil {
+			t.Fatal(err)
+		}
+	}
+	if err := mw.Close(); err != nil {
+		t.Fatal(err)
+	}
+	req := httptest.NewRequest(http.MethodPost, c.Path, strings.NewReader(body.String()))
+	req.Header.Set("Content-Type", mw.FormDataContentType())
+	req.AddCookie(ck)
+	req.AddCookie(&http.Cookie{Name: session.CookieName, Value: sessionFor(*c.Who, at)})
+	rec := httptest.NewRecorder()
+	mux.ServeHTTP(rec, req)
+	if rec.Code != c.Status || rec.Header().Get("Location") != str(c.Location) {
+		t.Fatalf("%d %q, want %d %q (%s)", rec.Code, rec.Header().Get("Location"), c.Status, str(c.Location), rec.Body.String())
+	}
+	var rule, reference string
+	if err := pool.QueryRow(context.Background(),
+		`SELECT stay_fee_scope_rule, stay_fee_scope_reference FROM apartment WHERE id = 12`).Scan(&rule, &reference); err != nil {
+		t.Fatal(err)
+	}
+	if rule != c.Form["rule"] || reference != c.Form["reference"] {
+		t.Errorf("saved %q %q, want %q %q", rule, reference, c.Form["rule"], c.Form["reference"])
+	}
+}
diff --git a/go/internal/web/stayfees/handlers.go b/go/internal/web/stayfees/handlers.go
index f0cf063..7310c2c 100644
--- a/go/internal/web/stayfees/handlers.go
+++ b/go/internal/web/stayfees/handlers.go
@@ -11,6 +11,8 @@ import (
 	"errors"
 	"io"
 	"log"
+	"math/big"
+	"mime"
 	"net/http"
 	"strconv"
 	"strings"
@@ -66,6 +68,15 @@ type call struct {
 func (d deps) enter(w http.ResponseWriter, r *http.Request) *call {
 	at := d.now()
 	if r.Method == http.MethodPost {
+		// request.form() reads multipart bodies too. Parse one here, once,
+		// before CSRF: CSRF then finds r.PostForm filled and reads no body,
+		// and a later ParseMultipartForm (also inside CSRF) is a no-op.
+		if isMultipart(r) {
+			r.Body = http.MaxBytesReader(w, r.Body, multipartMaxBody)
+			if err := r.ParseMultipartForm(multipartMaxBody); err != nil {
+				log.Printf("stayfees: multipart form: %v", err)
+			}
+		}
 		if !hostweb.CSRF(w, r, d.getenv, at) {
 			return nil
 		}
@@ -85,6 +96,24 @@ func (d deps) enter(w http.ResponseWriter, r *http.Request) *call {
 	return &call{deps: d, w: w, r: r, h: h, at: at, lang: hostweb.Lang(r), owner: h.Workspace.ID}
 }
 
+// multipartMaxBody caps a multipart/form-data body (Starlette's default
+// max_part_size is 1 MiB). These forms carry a few short fields.
+const multipartMaxBody = 1 << 20
+
+// isMultipart reports a multipart/form-data body.
+func isMultipart(r *http.Request) bool {
+	mediaType, _, err := mime.ParseMediaType(r.Header.Get("Content-Type"))
+	return err == nil && mediaType == "multipart/form-data"
+}
+
+// methodNotAllowed is Starlette's 405 for a method the route does not list.
+func methodNotAllowed(w http.ResponseWriter, allow string) {
+	w.Header().Set("Allow", allow)
+	w.Header().Set("Content-Type", "application/json")
+	w.WriteHeader(http.StatusMethodNotAllowed)
+	_, _ = io.WriteString(w, `{"detail":"Method Not Allowed"}`)
+}
+
 // flash is admin_helpers.flash: the text in the host's language, with its key.
 func (c *call) flash(key string, params map[string]any) hostweb.Flash {
 	return hostweb.Flash{Text: catalog.T(c.lang, key, params), Key: key}
@@ -139,16 +168,30 @@ func fail(w http.ResponseWriter, err error) {
 	_, _ = io.WriteString(w, "Internal Server Error")
 }
 
-// pathID reads an int path parameter. FastAPI answers 422 for a bad one.
-func pathID(w http.ResponseWriter, r *http.Request, name string) (int64, bool) {
-	id, err := strconv.ParseInt(r.PathValue(name), 10, 64)
-	if err != nil {
-		w.Header().Set("Content-Type", "application/json")
-		w.WriteHeader(http.StatusUnprocessableEntity)
-		_, _ = io.WriteString(w, `{"detail":"Unprocessable Entity"}`)
-		return 0, false
+// pathInt is an int path parameter. text is str(int) of it, for redirects.
+// none is set for an integer outside int64: Python parses it and Postgres
+// finds no row for it, so the handler takes its not-found branch without a
+// query.
+type pathInt struct {
+	id   int64
+	text string
+	none bool
+}
+
+// pathID reads an int path parameter. FastAPI answers 422 when it is not an
+// integer (ASCII digits with an optional sign).
+func pathID(w http.ResponseWriter, r *http.Request, name string) (pathInt, bool) {
+	raw := r.PathValue(name)
+	if id, err := strconv.ParseInt(raw, 10, 64); err == nil {
+		return pathInt{id: id, text: strconv.FormatInt(id, 10)}, true
 	}
-	return id, true
+	if n, ok := new(big.Int).SetString(raw, 10); ok {
+		return pathInt{text: n.String(), none: true}, true
+	}
+	w.Header().Set("Content-Type", "application/json")
+	w.WriteHeader(http.StatusUnprocessableEntity)
+	_, _ = io.WriteString(w, `{"detail":"Unprocessable Entity"}`)
+	return pathInt{}, false
 }
 
 // isDigits is str.isdigit for ASCII: one or more digits.
@@ -180,6 +223,14 @@ func (c *call) apartmentOf(ctx context.Context, id int64) (*apartment, error) {
 	return &a, nil
 }
 
+// pathApartment is apartmentOf for a path id: none when the id is outside int64.
+func (c *call) pathApartment(ctx context.Context, p pathInt) (*apartment, error) {
+	if p.none {
+		return nil, nil
+	}
+	return c.apartmentOf(ctx, p.id)
+}
+
 // filing is the part of a stay_fee_filing row the routes read.
 type filing struct {
 	ID        int64
@@ -255,7 +306,7 @@ func UndoHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time
 			return
 		}
 		ctx := r.Context()
-		apt, err := c.apartmentOf(ctx, apartmentID)
+		apt, err := c.pathApartment(ctx, apartmentID)
 		if err != nil {
 			c.fail(err)
 			return
@@ -267,15 +318,18 @@ func UndoHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time
 		month := c.month()
 		var sealed int64
 		var reversed string
-		err = pool.QueryRow(ctx,
-			`SELECT COALESCE(filing_id, 0), COALESCE(reversed_at, '') FROM stay_fee_adjustment
-			WHERE id = $1 AND apartment_id = $2`, adjustmentID, apartmentID).Scan(&sealed, &reversed)
-		found := !errors.Is(err, pgx.ErrNoRows)
-		if err != nil && found {
-			c.fail(err)
-			return
+		found := false
+		if !adjustmentID.none {
+			err = pool.QueryRow(ctx,
+				`SELECT COALESCE(filing_id, 0), COALESCE(reversed_at, '') FROM stay_fee_adjustment
+				WHERE id = $1 AND apartment_id = $2`, adjustmentID.id, apt.ID).Scan(&sealed, &reversed)
+			found = !errors.Is(err, pgx.ErrNoRows)
+			if err != nil && found {
+				c.fail(err)
+				return
+			}
 		}
-		back := monthPath(apartmentID, month)
+		back := monthPath(apt.ID, month)
 		if found && sealed != 0 {
 			c.back(back, hostweb.Flash{}, c.flash("flash.stay_fees.adjust_sealed", nil))
 			return
@@ -283,11 +337,11 @@ func UndoHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time
 		if found && reversed == "" {
 			if _, err := pool.Exec(ctx,
 				`UPDATE stay_fee_adjustment SET reversed_at = $1, reversed_by = $2 WHERE id = $3`,
-				stamp(c.at), c.owner, adjustmentID); err != nil {
+				stamp(c.at), c.owner, adjustmentID.id); err != nil {
 				c.fail(err)
 				return
 			}
-			if err := c.audit("stay_fee_adjustment_undo", "id="+strconv.FormatInt(adjustmentID, 10)); err != nil {
+			if err := c.audit("stay_fee_adjustment_undo", "id="+adjustmentID.text); err != nil {
 				c.fail(err)
 				return
 			}
@@ -426,7 +480,7 @@ func ScopeRulingHandler(pool *pgxpool.Pool, getenv func(string) string, now func
 			return
 		}
 		ctx := r.Context()
-		apt, err := c.apartmentOf(ctx, apartmentID)
+		apt, err := c.pathApartment(ctx, apartmentID)
 		if err != nil {
 			c.fail(err)
 			return
@@ -435,7 +489,7 @@ func ScopeRulingHandler(pool *pgxpool.Pool, getenv func(string) string, now func
 			c.noSuchApartment()
 			return
 		}
-		backPath := monthPath(apartmentID, c.month())
+		backPath := monthPath(apt.ID, c.month())
 		rule := c.formStr("rule")
 		reference := strings.TrimSpace(truncRunes(c.formStr("reference"), referenceMax))
 		if !contains(scopeRules, rule) || len([]rune(reference)) < 3 {
@@ -469,7 +523,7 @@ func CopySetupHandler(pool *pgxpool.Pool, getenv func(string) string, now func()
 			return
 		}
 		ctx := r.Context()
-		apt, err := c.apartmentOf(ctx, apartmentID)
+		apt, err := c.pathApartment(ctx, apartmentID)
 		if err != nil {
 			c.fail(err)
 			return
@@ -478,7 +532,7 @@ func CopySetupHandler(pool *pgxpool.Pool, getenv func(string) string, now func()
 			c.noSuchApartment()
 			return
 		}
-		backPath := feeReturnPath(c.formStr("return_to"), apartmentID)
+		backPath := feeReturnPath(c.formStr("return_to"), apt.ID)
 		if backPath == "" {
 			backPath = "/stay-fees"
 		}
@@ -535,7 +589,7 @@ func PaidHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time
 			return
 		}
 		ctx := r.Context()
-		apt, err := c.apartmentOf(ctx, apartmentID)
+		apt, err := c.pathApartment(ctx, apartmentID)
 		if err != nil {
 			c.fail(err)
 			return
@@ -545,7 +599,7 @@ func PaidHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time
 			return
 		}
 		month := c.month()
-		backPath := feeReturnPath(c.formStr("return_to"), apartmentID)
+		backPath := feeReturnPath(c.formStr("return_to"), apt.ID)
 		if backPath == "" {
 			backPath = "/stay-fees?month=" + monthKey(month)
 		}
@@ -598,7 +652,7 @@ func filingMark(pool *pgxpool.Pool, getenv func(string) string, now func() time.
 			return
 		}
 		ctx := r.Context()
-		apt, err := c.apartmentOf(ctx, apartmentID)
+		apt, err := c.pathApartment(ctx, apartmentID)
 		if err != nil {
 			c.fail(err)
 			return
@@ -608,11 +662,13 @@ func filingMark(pool *pgxpool.Pool, getenv func(string) string, now func() time.
 			return
 		}
 		month := c.month()
-		back := monthPath(apartmentID, month)
-		row, err := c.filingForMonth(ctx, apartmentID, month, filingID)
-		if err != nil {
-			c.fail(err)
-			return
+		back := monthPath(apt.ID, month)
+		var row *filing
+		if !filingID.none {
+			if row, err = c.filingForMonth(ctx, apt.ID, month, filingID.id); err != nil {
+				c.fail(err)
+				return
+			}
 		}
 		if row == nil {
 			c.back(back, hostweb.Flash{}, c.flash("flash.stay_fees.report_blocked", nil))
@@ -620,7 +676,7 @@ func filingMark(pool *pgxpool.Pool, getenv func(string) string, now func() time.
 		}
 		nowText := stamp(c.at)
 		idText := strconv.FormatInt(row.ID, 10)
-		aptText := strconv.FormatInt(apartmentID, 10)
+		aptText := strconv.FormatInt(apt.ID, 10)
 		if paid {
 			if row.PaidAt == "" {
 				sent := row.SentAt
@@ -679,6 +735,12 @@ var identityVisible = func(h *session.Host) bool {
 func CSVHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
 	d := deps{pool, getenv, now}
 	return func(w http.ResponseWriter, r *http.Request) {
+		// Go's "GET" pattern also matches HEAD; the FastAPI route lists GET
+		// only, so HEAD is a 405 before any dependency runs.
+		if r.Method == http.MethodHead {
+			methodNotAllowed(w, http.MethodGet)
+			return
+		}
 		c := d.enter(w, r)
 		if c == nil {
 			return
@@ -687,7 +749,7 @@ func CSVHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.
 		if !ok {
 			return
 		}
-		aptText := strconv.FormatInt(apartmentID, 10)
+		aptText := apartmentID.text
 		// The register CSV lists every guest's document number.
 		if !identityVisible(c.h) {
 			c.back("/stay-fees/"+aptText, hostweb.Flash{}, c.flash("flash.error.identity_hidden_export", nil))
@@ -710,14 +772,15 @@ func CSVHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.
 			}
 		}
 		ctx := r.Context()
-		apt, err := c.apartmentOf(ctx, apartmentID)
+		apt, err := c.pathApartment(ctx, apartmentID)
 		if err != nil {
 			c.fail(err)
 			return
 		}
-		backPath := monthPath(apartmentID, selected)
+		var backPath string
 		var row *filing
 		if apt != nil {
+			backPath = monthPath(apt.ID, selected)
 			if row, err = c.covering(ctx, apt.ID, selected); err != nil {
 				c.fail(err)
 				return
```
<!-- patch:end -->
