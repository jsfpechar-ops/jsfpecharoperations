# 1301-fix-1: Go property pages, review fixes

Status: review
Depends on: 1301 | Base commit: 620119d | Branch: task/1301-go-property-pages
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B

## 1. Objective

Two review findings on brief 1301: (1) `GET /guide` treated an empty `UBYHOST_UBYPORT_ENV` as `mock`; Python (`App/app/config.py` ~296, `os.environ.get("UBYHOST_UBYPORT_ENV", "mock").lower()`) keeps `""`, so the demo section is hidden. Go now reads that key through an injectable `lookupEnv` (`os.LookupEnv` in production) and defaults to `mock` only when the key is missing; a new golden case covers `""`. (2) The `guest_links_admin_inside` case now enters workspace 131001 (one live property), so its `Location` names that property and cannot match the admin's own (empty) workspace by accident.

## 2. Context

The brief writer applied the patch in step 1 on 620119d and ran §6 green; the sums in step 2 and step 3 are from that dry run. `RegisterPages` gains a `lookupEnv func(string) (string, bool)` parameter after `getenv`; `Pages` becomes its own struct (it no longer converts 1300's `server`). Tests never read the process env: the golden test builds `lookup` from the case env plus `testEnv`. Python's side needed no change (`apply_env` already keeps `""`).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/properties/pages.go` | edit (patch) | `Pages` struct, `lookupEnv`, UbyPort env read |
| `go/internal/web/properties/pages_test.go` | edit (patch) | pass `lookup` |
| `go/internal/web/properties/testdata/pages_cases.json` | edit (patch) | new case, `as` 131001 |
| `go/internal/web/properties/testdata/pages_golden.json` | regenerate (step 3) | 11 cases |
| `go/cmd/ubyhost-web/register_web_properties.go` | edit (patch) | pass `os.LookupEnv` |
| `docs/tasks/1301-fix-1-go-property-pages.md` | edit | `Status:` line only |
| `docs/tasks/1301-fix-1-report.md` | create | report |

No other file may change.

## 4. Steps

1. From the repo root, on `task/1301-go-property-pages` (check with `git branch --show-current`), write the patch to a file, check it and apply it:

```bash
cat > /var/tmp/1301-fix-1.patch <<'PATCH'
diff --git a/go/cmd/ubyhost-web/register_web_properties.go b/go/cmd/ubyhost-web/register_web_properties.go
index e4ecf49..3860027 100644
--- a/go/cmd/ubyhost-web/register_web_properties.go
+++ b/go/cmd/ubyhost-web/register_web_properties.go
@@ -16,6 +16,6 @@ import (
 func init() {
 	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
 		properties.Register(mux, m.wrap, pool, os.Getenv, time.Now)
-		properties.RegisterPages(mux, m.wrap, pool, os.Getenv, time.Now)
+		properties.RegisterPages(mux, m.wrap, pool, os.Getenv, os.LookupEnv, time.Now)
 	})
 }
diff --git a/go/internal/web/properties/pages.go b/go/internal/web/properties/pages.go
index 2f15992..3582259 100644
--- a/go/internal/web/properties/pages.go
+++ b/go/internal/web/properties/pages.go
@@ -28,8 +28,10 @@ var pages = layout.MustParse(catalog, pageFiles, "templates/*.tmpl")
 
 // RegisterPages adds the GET routes. It only builds handlers; the pool is
 // first used inside a request.
-func RegisterPages(mux *http.ServeMux, wrap Wrap, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) {
-	s := &Pages{pool: pool, getenv: getenv, now: now}
+// lookupEnv is os.LookupEnv in production; it tells an unset key from an
+// empty one where Python's os.environ.get(key, default) does.
+func RegisterPages(mux *http.ServeMux, wrap Wrap, pool *pgxpool.Pool, getenv func(string) string, lookupEnv func(string) (string, bool), now func() time.Time) {
+	s := &Pages{pool: pool, getenv: getenv, lookupEnv: lookupEnv, now: now}
 	for _, route := range []struct {
 		path string
 		h    http.HandlerFunc
@@ -41,8 +43,13 @@ func RegisterPages(mux *http.ServeMux, wrap Wrap, pool *pgxpool.Pool, getenv fun
 	}
 }
 
-// Pages serves the GET routes; it shares the action server's fields.
-type Pages server
+// Pages serves the GET routes.
+type Pages struct {
+	pool      *pgxpool.Pool
+	getenv    func(string) string
+	lookupEnv func(string) (string, bool)
+	now       func() time.Time
+}
 
 // workflowStep is one row of workflow.steps(None) (App/app/workflow.py).
 type workflowStep struct {
@@ -136,12 +143,13 @@ func (s *Pages) guide(w http.ResponseWriter, r *http.Request) {
 		}
 		havel = aiOnTestList(s.getenv, email)
 	}
-	// config.UBYPORT_ENV == "mock" (default mock, lower-cased; an empty value
-	// counts as unset, as layout's env banner reads it).
-	env := strings.ToLower(s.getenv("UBYHOST_UBYPORT_ENV"))
-	if env == "" {
+	// config.UBYPORT_ENV == "mock": os.environ.get(key, "mock").lower(), so
+	// only a missing key is mock; a key set to "" is not.
+	env, set := s.lookupEnv("UBYHOST_UBYPORT_ENV")
+	if !set {
 		env = "mock"
 	}
+	env = strings.ToLower(env)
 	page := layout.Page{
 		Title:    catalog.T(hostweb.Lang(r), "guide.title", nil),
 		Nav:      "guide",
diff --git a/go/internal/web/properties/pages_test.go b/go/internal/web/properties/pages_test.go
index 4581340..729b6ce 100644
--- a/go/internal/web/properties/pages_test.go
+++ b/go/internal/web/properties/pages_test.go
@@ -143,8 +143,15 @@ func TestPagesMatchPython(t *testing.T) {
 			}
 			return testEnv(k)
 		}
+		lookup := func(k string) (string, bool) {
+			if v, ok := tc.Env[k]; ok {
+				return v, true
+			}
+			v := testEnv(k)
+			return v, v != ""
+		}
 		mux := http.NewServeMux()
-		RegisterPages(mux, func(_ string, h http.HandlerFunc) http.Handler { return h }, pool, env, testClock)
+		RegisterPages(mux, func(_ string, h http.HandlerFunc) http.Handler { return h }, pool, env, lookup, testClock)
 		req := httptest.NewRequest(http.MethodGet, tc.Path, nil)
 		req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: tc.Lang})
 		if tc.User != 0 {
@@ -189,7 +196,7 @@ func TestPagesMatchPython(t *testing.T) {
 
 func TestPagesRegisterDoesNotTouchThePool(t *testing.T) {
 	mux := http.NewServeMux()
-	RegisterPages(mux, func(_ string, h http.HandlerFunc) http.Handler { return h }, nil, testEnv, testClock)
+	RegisterPages(mux, func(_ string, h http.HandlerFunc) http.Handler { return h }, nil, testEnv, func(string) (string, bool) { return "", false }, testClock)
 	req := httptest.NewRequest(http.MethodPost, "/guide", nil)
 	rec := httptest.NewRecorder()
 	mux.ServeHTTP(rec, req)
diff --git a/go/internal/web/properties/testdata/pages_cases.json b/go/internal/web/properties/testdata/pages_cases.json
index 551504d..ff399af 100644
--- a/go/internal/web/properties/testdata/pages_cases.json
+++ b/go/internal/web/properties/testdata/pages_cases.json
@@ -133,6 +133,15 @@
     "UBYHOST_AI_TEST_EMAILS": "Pages-Admin@example.test, other@example.test"
    }
   },
+  {
+   "name": "guide_empty_ubyport_env",
+   "path": "/guide",
+   "user": 131001,
+   "lang": "en",
+   "env": {
+    "UBYHOST_UBYPORT_ENV": ""
+   }
+  },
   {
    "name": "guide_signed_out",
    "path": "/guide",
@@ -165,7 +174,7 @@
    "name": "guest_links_admin_inside",
    "path": "/guest-links",
    "user": 131004,
-   "as": 131002,
+   "as": 131001,
    "lang": "en",
    "env": {}
   },
PATCH
git apply --check /var/tmp/1301-fix-1.patch && echo CHECK OK && git apply /var/tmp/1301-fix-1.patch && echo APPLIED
```

Expected: `CHECK OK`, then `APPLIED`. Any error: stop (§8).

2. Check the patched files:

```bash
sha256sum -c <<'SUMS' 2>&1 | tail -5
e40380e2dea705e80c2411dbabbb1f5945a0177c7039397798def5105d96eabe  go/cmd/ubyhost-web/register_web_properties.go
d9d7dab1782ef1cdf042fb16e843f6fc920903bd4b229a048db8cebf06776549  go/internal/web/properties/pages.go
73664792902004d74d3121bb673e5fa1961b8c740593e1ef77f9bb45d5a726e5  go/internal/web/properties/pages_test.go
644350ea9148cadf84ebc6226d9a1134ab13f852da27ecddc181aa6e89f471e1  go/internal/web/properties/testdata/pages_cases.json
SUMS
```

Expected: 4 `OK`.

3. Regenerate the golden from Python and check it:

```bash
cd App && UBYHOST_WRITE_GOLDEN=1 .venv/bin/python -m pytest tests/test_go_properties_pages.py -q --tb=short -x 2>&1 | tail -3 && sha256sum ../go/internal/web/properties/testdata/pages_golden.json
```

Expected: `2 passed`, then `d9b572b82ca77159ce437899fa132264c695bfef42ec3c94603c6ed1c085bb3c  ../go/internal/web/properties/testdata/pages_golden.json`. Different: stop (§8); never edit the golden by hand.

4. Run §6, then commit: `git add go/internal/web/properties go/cmd/ubyhost-web/register_web_properties.go && git commit -q -m "1301-fix-1: UbyPort env unset vs empty, admin case" && git show --stat HEAD | tail -8`.

5. Set `Status: review` here, write `docs/tasks/1301-fix-1-report.md` (§9), commit both.

## 5. Do not touch

Everything outside §3, in particular `go/internal/hostweb/`, 1300's files, `App/` (the Python test stays as it is), deploy and env docs. Nothing to `UBYHOST_GO_PATHS`. No new dependency. Hard rules 3, 4, 5, 8. Never push to `main`; never merge.

## 6. Commands

```bash
export UBYHOST_TEST_DATABASE_URL=postgresql://...   # as the environment gives; unset = stop (§8)
cd go && test -z "$(gofmt -l .)" && go vet ./... 2>&1 | tail -5 && go test -count=1 -v ./internal/web/properties/ ./internal/hostweb/... ./cmd/ubyhost-web/ 2>&1 | grep -E '^(--- (FAIL|SKIP)|ok|FAIL)|PASS: TestPages' | tail -12 && go build -o /dev/null ./cmd/ubyhost-web && echo BUILD OK
cd App && .venv/bin/python -m pytest tests/test_go_properties_pages.py tests/test_go_properties_actions.py -q --tb=short -x 2>&1 | tail -3
python3 scripts/context_lint.py 2>&1 | tail -3
```

Expected: no `SKIP`/`FAIL`; `--- PASS: TestPagesMatchPython`, `--- PASS: TestPagesRegisterDoesNotTouchThePool`; four `ok`; `BUILD OK`; `4 passed`; `context lint: OK`.

## 7. Acceptance

- [ ] Step 1 `CHECK OK` and `APPLIED`; step 2: 4 `OK`; step 3: the golden sum.
- [ ] §6 green, `TestPagesMatchPython` not skipped.
- [ ] `git diff --stat 620119d..HEAD` lists only §3 paths plus this brief.
- [ ] `grep -c '"name": "guide_empty_ubyport_env"' go/internal/web/properties/testdata/pages_golden.json` prints `1`.

## 8. Stop and ask

Stop and write the report if: the patch does not apply, a sum differs, `TestPagesMatchPython` skips, a test fails twice, a file outside §3 needs a change, you reach 25 tool calls or about 50k tokens, a step is unclear, or you would need push, merge, secrets or deploy.

## 9. Report

`docs/tasks/1301-fix-1-report.md` (400 tokens at most): `git diff --stat 620119d..HEAD`, each command with its last 5 lines, §7 ticked, deviations, questions. Set `Status: review`.

## Risk list (for the reviewer)

- `pages.go` guide: `lookupEnv` result lower-cased after the default; only a missing key is `mock`.
- `register_web_properties.go`: `os.LookupEnv` passed in the new position.
- Golden: `guide_empty_ubyport_env` has no demo section; `guest_links_admin_inside` now redirects to `/apartments/131201?view=settings&section=guests#communication`.

## Owner steps

1. Wait for the draft PR's CI to go green. Nothing to deploy; the routes stay off.
