# 1310-fix-1: review findings on the Go cleaning port

Status: review
Depends on: 1310 | Base commit: 7a754a0 | Branch: task/1310-go-cleaning-schedule
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Fix three review findings in `go/internal/web/cleaning`: a test for the Prague-midnight edge of `today()`, a panic-free `color` for negative ids, and a body limit on the delete form when the CSRF token comes in a header. No behaviour changes for any golden case.

## 2. Context

Tier B. Rules: no new dependency (4), `go/internal/hostweb` is read-only (its `csrfMaxBody = 64 << 10` is unexported, so the cleaning package keeps its own copy of the value).

Finding 1: why a unit test and not a golden case. `App/scripts/cleaning_golden.py` lines 283-290 replace `cleaning.today` with a lambda that returns the constant `TODAY`, so Python's real `today()` (`datetime.now(ZoneInfo("Europe/Prague")).date()`) never runs in the golden. A 22:30 UTC case would need a frozen wall clock in Python (session `iat`, `utcnow` stamps, CSRF timestamps all read it) and a second clock in `golden_test.go`. The Python side is one stdlib call; the Go side (`deadlines.LocalNow`) is what needs proof, so a focused Go test covers it. The golden is not changed.

Finding 2: `render.go` `color` indexes `[id%3]`; Go's `%` keeps the sign, so a negative id panics.

Finding 3: `hostweb.CSRF` wraps `r.Body` in `http.MaxBytesReader` only when the token is not in the `X-CSRF-Token` header. `DeleteHandler` then calls `r.ParseForm()` with no limit. Oversized bodies now get 413 `{"detail":"Request Entity Too Large"}`; other parse errors are ignored as before.

Leave alone: `pyInt` strictness; the 500 on an undecryptable note (Python behaves the same).

## 3. Files

| Path | Action | What |
|---|---|---|
| go/internal/web/cleaning/render.go | edit | named `color`, sign-safe |
| go/internal/web/cleaning/handler.go | edit | `parseLimitedForm`, used by DeleteHandler |
| go/internal/web/cleaning/fix_test.go | create | 3 unit tests |
| docs/tasks/1310-fix-1-review-findings.md | edit | Status line only |
| docs/tasks/1310-fix-1-report.md | create | report |

No other file may change.

## 4. Steps

Work in `$(git rev-parse --show-toplevel)`, branch `task/1310-go-cleaning-schedule`. Apply each diff literally (Edit tool, exact strings, tabs as in the file).

**Step 1. render.go.** Replace

```go
var funcs = template.FuncMap{
	"ct": ct, "t": t, "cdate": cdate, "cday": cday, "cshort": cshort, "icon": icon,
	"window": window, "first": first,
	"color":  func(id int64) string { return []string{"teal", "blue", "purple"}[id%3] },
```

with

```go
// color picks the calendar colour; ((id%3)+3)%3 keeps a negative id in range.
func color(id int64) string { return []string{"teal", "blue", "purple"}[((id%3)+3)%3] }

var funcs = template.FuncMap{
	"ct": ct, "t": t, "cdate": cdate, "cday": cday, "cshort": cshort, "icon": icon,
	"window": window, "first": first,
	"color":  color,
```

Commit `1310-fix-1 step 1: sign-safe cleaning color`.

**Step 2. handler.go.** (a) Replace

```go
// DeleteHandler serves POST /cleaning/events/{id}/delete: dismiss one cleaning.
```

with

```go
// formMaxBody is hostweb's csrfMaxBody. hostweb.CSRF sets that limit only when
// the token comes in the form, so a header token left the body unlimited.
const formMaxBody = 64 << 10

// parseLimitedForm parses the form with the hostweb.CSRF body limit. It returns
// false after writing 413 when the body is too large.
func parseLimitedForm(w http.ResponseWriter, r *http.Request) bool {
	r.Body = http.MaxBytesReader(w, r.Body, formMaxBody)
	var tooBig *http.MaxBytesError
	if err := r.ParseForm(); errors.As(err, &tooBig) {
		writeDetail(w, http.StatusRequestEntityTooLarge, "Request Entity Too Large")
		return false
	}
	return true
}

// DeleteHandler serves POST /cleaning/events/{id}/delete: dismiss one cleaning.
```

(b) Replace

```go
		revision := int64(0)
		_ = r.ParseForm()
```

with

```go
		revision := int64(0)
		if !parseLimitedForm(w, r) {
			return
		}
```

(`errors` is already imported.) Commit `1310-fix-1 step 2: limit delete form body`.

**Step 3. Create `go/internal/web/cleaning/fix_test.go`** with exactly:

```go
package cleaning

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

// TestTodayPragueMidnight: from 22:00 UTC (summer) or 23:00 UTC (winter) it is
// already the next day in Prague. The golden pins cleaning.today() to one
// constant date in cleaning_golden.py, so it never reaches this edge.
func TestTodayPragueMidnight(t *testing.T) {
	cases := []struct {
		at   time.Time
		want string
	}{
		{time.Date(2026, 5, 10, 21, 59, 0, 0, time.UTC), "2026-05-10"},
		{time.Date(2026, 5, 10, 22, 30, 0, 0, time.UTC), "2026-05-11"},
		{time.Date(2026, 12, 31, 22, 30, 0, 0, time.UTC), "2026-12-31"},
		{time.Date(2026, 12, 31, 23, 30, 0, 0, time.UTC), "2027-01-01"},
	}
	for _, c := range cases {
		if got := iso(today(c.at)); got != c.want {
			t.Errorf("today(%s) = %s, want %s", c.at.Format(time.RFC3339), got, c.want)
		}
	}
}

func TestColorNegativeID(t *testing.T) {
	want := map[int64]string{-4: "purple", -3: "teal", -2: "blue", -1: "purple", 0: "teal", 1: "blue", 2: "purple", 3: "teal"}
	for id, w := range want {
		if got := color(id); got != w {
			t.Errorf("color(%d) = %s, want %s", id, got, w)
		}
	}
}

func TestParseLimitedForm(t *testing.T) {
	post := func(body string) (*http.Request, *httptest.ResponseRecorder) {
		r := httptest.NewRequest(http.MethodPost, "/cleaning/events/1/delete", strings.NewReader(body))
		r.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		return r, httptest.NewRecorder()
	}
	r, w := post("revision=3")
	if !parseLimitedForm(w, r) || r.PostForm.Get("revision") != "3" {
		t.Fatalf("small form: ok=false or revision=%q", r.PostForm.Get("revision"))
	}
	r, w = post("revision=3&pad=" + strings.Repeat("a", formMaxBody))
	if parseLimitedForm(w, r) {
		t.Fatal("oversized form accepted")
	}
	if w.Code != http.StatusRequestEntityTooLarge {
		t.Fatalf("status %d, want 413", w.Code)
	}
}
```

Commit `1310-fix-1 step 3: unit tests for today, color, form limit`.

**Step 4. Checks** (§6). Then set Status `review` in this brief, write the report (§9), commit `1310-fix-1 step 4: report`.

## 5. Do not touch

go/internal/hostweb (read-only), go/internal/deadlines, golden_test.go, testdata/, templates/, App/ (no golden regeneration), docs/context/*. Never push to main, never merge.

## 6. Commands

Postgres first. If `pg_isready -h 127.0.0.1 -p 55431` says `no response`, run:

```bash
su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1310 -o "-p 55431 -k /tmp" -l /var/tmp/pg1310.log start' 2>&1 | tail -3
```

Expect `server started`. If /var/tmp/pg1310 is missing: `mkdir -p /var/tmp/pg1310 && chown postgres /var/tmp/pg1310 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1310 -A trust' | tail -3`, then the start command.

```bash
cd go && gofmt -l ./internal/web/cleaning/ | tail -5
```

Expect no output.

```bash
cd go && go vet ./internal/web/cleaning/... 2>&1 | tail -5
```

Expect no output.

```bash
cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55431/postgres go test ./internal/web/cleaning/... ./cmd/ubyhost-web/... -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL)|SKIP' | tail -10
```

Expect `--- PASS` for TestTodayPragueMidnight, TestColorNegativeID, TestParseLimitedForm, TestCleaningMatchesPython (not SKIP), and `ok` for both packages.

```bash
sha256sum go/internal/web/cleaning/render.go go/internal/web/cleaning/handler.go go/internal/web/cleaning/fix_test.go
```

Expect:

```
965e8bd5045a2e4e4be136f1a0914fc80493259a920db2663a4bcbabb1249de4  go/internal/web/cleaning/render.go
630d097dfdd9f0e6654c6023309d7e98a0637b7166a96961790800b819f90508  go/internal/web/cleaning/handler.go
07444ede68a779cab8ad8fcee394a68b718ea872cc814dddc6dffeeec8a41cde  go/internal/web/cleaning/fix_test.go
```

```bash
python3 scripts/context_lint.py | tail -3
```

Expect `context lint: OK` (a status.md WARN line is fine).

## 7. Acceptance

- [ ] `git diff --stat 7a754a0..HEAD` lists only §3 files.
- [ ] 3 sha256 values match §6.
- [ ] gofmt and vet print nothing; 4 tests PASS, golden not skipped; lint OK.

## 8. Stop and ask

Stop, report `blocked`: an excerpt is not found; a sha differs; a test fails twice; 25 tool calls or ~50k tokens; a file outside §3 would change; push/merge/secrets/deploy needed.

## 9. Report

`docs/tasks/1310-fix-1-report.md`, at most 600 tokens: diff stat, each command's last 5 lines, §7 ticked, deviations, questions, owner steps.

## Risk list (for the reviewer)

go/internal/web/cleaning/handler.go (413 path, order still CSRF, id, login, owner, form), render.go (`color`).

## Owner steps

None (draft PR only).
