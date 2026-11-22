# 2003: Host HTML Go pages use NotFoundPage, not bare `http.NotFound`

Status: review
Depends on: 2002 | Base commit: db9987149 | Branch: cursor/2003-go-host-branded-404-sweep-4fe8
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

After 2002, the mux catch-all and stay detail already render `hostweb.NotFoundPage`, and trailing slashes redirect. A sweep of Go still finds many host HTML handlers that answer with Go's bare `404 page not found` or plain `Not found.` — the same black page the owner saw from the stay email. Replace those host HTML call sites with `hostweb.NotFoundPage` and add a pin test so a new bare `http.NotFound` in the listed host packages fails CI.

## 2. Context

Rules: AGENTS.md go-first; UX gate does **not** apply (no template/CSS/guest-page change — only the existing branded 404 HTML from 2002). Privacy/copy unchanged.

**Sweep result (2026-11-22, on `main` / after 2002):** ~86 `http.NotFound` / `StatusNotFound` sites under `go/`. Classes:

| Class | Action in this brief |
|---|---|
| Host HTML GET/POST that a logged-in host can hit (settings, properties detail/new, submissions, guest edit, stay POST helpers, exports path parse, admin `/dev/ui`) | → `hostweb.NotFoundPage` |
| staydetail GET | already fixed in 2002 — do not re-touch |
| JSON / FastAPI-shaped (`{"detail":"Not Found"}`, `{"ok":false}`, stay-fees `pgNotFound`) | leave |
| Guest forms (`go/internal/web/guest/`) | leave (own unavailable page) |
| Booking site (`go/internal/web/booking/`) | leave (public guest booking) |
| Static files | leave |
| `properties/misc.go` alert: plain `No such alert.` matching Python | leave |
| `public/pages_render.go` marketing/guide JSON 404 | leave |
| Trailing-slash class | fixed mux-wide by 2002 `CanonicalSlash` — no per-route work |

Exact excerpts (verify verbatim on the 2002 tip `db9987149`; if any is missing, STOP §8):

- `go/internal/hostweb/notfound.go` (2002): `func NotFoundPage(w http.ResponseWriter, r *http.Request)` — branded HTML when `WantsHTML`, else empty 404 body.
- `go/internal/web/settings/settings.go:103`: `http.NotFound(w, r)` (unknown settings group).
- `go/internal/web/properties/apartment_detail.go:257-259` and `:282-284`: `w.WriteHeader(http.StatusNotFound)` + `_, _ = w.Write([]byte("Not found."))` (missing apartment / copy source). Comment at top of that file already says these should be Python's branded 404.
- `go/internal/web/properties/apartment_new.go:344-347`: same plain `Not found.` when copy source missing.
- `go/internal/web/submissions/handlers.go:70`: `http.NotFound(w, r)` on bad `submission_id` parse.
- `go/internal/web/stays/guest_edit.go:204` (`parseResGuestID`) and `:476` (`!found` guest): `http.NotFound(w, r)`.
- `go/internal/web/stays/claim_ops.go:185` (`parseClaimID`): `http.NotFound(w, r)`.
- `go/internal/web/stays/submit.go:44` (`parseSubmitID`): `http.NotFound(w, r)`.
- `go/internal/web/staydetail/post.go:48`: `http.NotFound(w, r)` on bad id parse.
- `go/internal/web/stays/edit_posts.go` lines **257, 325, 392, 433, 474**: `http.NotFound(w, r)` on bad id parse. **Keep** the nearby `Content-Type: application/json` + `{"ok":false}` blocks at ~272 and ~338 unchanged.
- `go/internal/web/exports/exports.go:227` (`pathID`): `http.NotFound(w, r)`.
- `go/internal/web/public/dev_ui.go:101`: `http.NotFound(w, r)` for non-admin.

Each of those packages already imports `github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb` (confirm; if a file does not, add that import only).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/settings/settings.go` | edit | `http.NotFound` → `hostweb.NotFoundPage` |
| `go/internal/web/properties/apartment_detail.go` | edit | both plain `Not found.` blocks → `hostweb.NotFoundPage(w, r); return` |
| `go/internal/web/properties/apartment_new.go` | edit | plain `Not found.` block → `hostweb.NotFoundPage` |
| `go/internal/web/submissions/handlers.go` | edit | `http.NotFound` → `hostweb.NotFoundPage` |
| `go/internal/web/stays/guest_edit.go` | edit | both `http.NotFound` → `hostweb.NotFoundPage` |
| `go/internal/web/stays/claim_ops.go` | edit | `http.NotFound` → `hostweb.NotFoundPage` |
| `go/internal/web/stays/submit.go` | edit | `http.NotFound` → `hostweb.NotFoundPage` |
| `go/internal/web/staydetail/post.go` | edit | `http.NotFound` → `hostweb.NotFoundPage` |
| `go/internal/web/stays/edit_posts.go` | edit | five parse-error `http.NotFound` only → `hostweb.NotFoundPage` |
| `go/internal/web/exports/exports.go` | edit | `pathID` `http.NotFound` → `hostweb.NotFoundPage` (add `hostweb` import if missing) |
| `go/internal/web/public/dev_ui.go` | edit | `http.NotFound` → `hostweb.NotFoundPage` |
| `go/internal/hostweb/notfound_host_pin_test.go` | new | pin: listed host files must not contain `http.NotFound(` or `[]byte("Not found.")` |
| `docs/tasks/2003-report.md` | new | §9 report |
| `docs/tasks/2003-go-host-branded-404-sweep.md` | edit | set `Status: review` when done |

No other file may change. Do **not** edit `misc.go`, booking, guest, stayfees, customers, invoices, billing, ai, staticfiles, pages_render, or staydetail GET handlers.

## 4. Steps

1. Branch from 2002 tip: `git fetch origin task/2002-go-host-404-slash-and-branded && git checkout -B cursor/2003-go-host-branded-404-sweep-4fe8 origin/task/2002-go-host-404-slash-and-branded`. Confirm `NotFoundPage` exists: `grep -n 'func NotFoundPage' go/internal/hostweb/notfound.go`.

2. In every §3 edit file, replace each in-scope call as follows (exact):
   - `http.NotFound(w, r)` → `hostweb.NotFoundPage(w, r)`
   - For apartment_detail (both sites) and apartment_new, replace the three-line block:
     ```
     w.WriteHeader(http.StatusNotFound)
     _, _ = w.Write([]byte("Not found."))
     return
     ```
     with:
     ```
     hostweb.NotFoundPage(w, r)
     return
     ```
   - In `edit_posts.go`, change **only** the five parse-error `http.NotFound` lines; leave JSON `{"ok":false}` 404s alone.

3. Ensure each edited file imports `hostweb` (already true for most). For `exports/exports.go`, add:
   `"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"`
   if the import is missing.

4. Add `go/internal/hostweb/notfound_host_pin_test.go`:

```go
package hostweb

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// Host HTML packages that must not regress to bare http.NotFound / plain "Not found."
// Guest, booking, JSON APIs, misc alert, and marketing pages are intentionally out of scope (brief 2003).
var hostNotFoundPinFiles = []string{
	"internal/web/settings/settings.go",
	"internal/web/properties/apartment_detail.go",
	"internal/web/properties/apartment_new.go",
	"internal/web/submissions/handlers.go",
	"internal/web/stays/guest_edit.go",
	"internal/web/stays/claim_ops.go",
	"internal/web/stays/submit.go",
	"internal/web/stays/edit_posts.go",
	"internal/web/staydetail/post.go",
	"internal/web/staydetail/handlers.go",
	"internal/web/exports/exports.go",
	"internal/web/public/dev_ui_page.go",
}

func TestHostPackagesNoBareNotFound(t *testing.T) {
	root := filepath.Clean("..") // go/internal → go/
	for _, rel := range hostNotFoundPinFiles {
		path := filepath.Join(root, rel)
		b, err := os.ReadFile(path)
		if err != nil {
			t.Fatalf("%s: %v", rel, err)
		}
		s := string(b)
		if strings.Contains(s, "http.NotFound(") {
			t.Errorf("%s: still has http.NotFound(; use hostweb.NotFoundPage", rel)
		}
		if strings.Contains(s, `[]byte("Not found.")`) {
			t.Errorf("%s: still has plain Not found. body; use hostweb.NotFoundPage", rel)
		}
	}
}
```

   Confirm the relative root: the test lives in `go/internal/hostweb/`, so `..` is `go/internal` — **wrong**. Fix the root to find `go/` modules:

   Use this instead for path resolution (replace the `root :=` line and Join):

```go
	// Test file is go/internal/hostweb/…; module root is go/.
	_, thisFile, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("runtime.Caller failed")
	}
	goRoot := filepath.Clean(filepath.Join(filepath.Dir(thisFile), "../.."))
	for _, rel := range hostNotFoundPinFiles {
		path := filepath.Join(goRoot, rel)
		// …
```

   Add `"runtime"` to the import list. Keep `hostNotFoundPinFiles` paths relative to `go/` as listed.

5. Format and test (from `go/`):

```bash
gofmt -w internal/web/settings/settings.go internal/web/properties/apartment_detail.go internal/web/properties/apartment_new.go internal/web/submissions/handlers.go internal/web/stays/guest_edit.go internal/web/stays/claim_ops.go internal/web/stays/submit.go internal/web/stays/edit_posts.go internal/web/staydetail/post.go internal/web/exports/exports.go internal/web/public/dev_ui_page.go internal/hostweb/notfound_host_pin_test.go
go test ./internal/hostweb/ ./internal/web/settings/ ./internal/web/properties/ ./internal/web/submissions/ ./internal/web/stays/ ./internal/web/staydetail/ ./internal/web/exports/ ./internal/web/public/ -count=1 2>&1 | tail -30
```

   Expected: pin test PASS; packages that need DB may skip; no FAIL.

6. From repo root: `python3 scripts/context_lint.py 2>&1 | tail -30` → exit 0.

7. Write `docs/tasks/2003-report.md` (§9) and set this brief's Status to `review`. Commit on `cursor/2003-go-host-branded-404-sweep-4fe8`. Do not push to `main`. Owner merges with `scripts/merge-pr-on-green.sh` after 2002 is on main (or stack this PR on #1256).

## 5. Do not touch

- `go/internal/web/guest/**`, `go/internal/web/booking/**`, `go/internal/web/staticfiles/**`
- `go/internal/web/customers/**`, `invoices/**`, `billing/**`, `ai/**`, `stayfees/**` (JSON 404s)
- `go/internal/web/properties/misc.go` (plain `No such alert.`)
- `go/internal/web/public/pages_render.go`
- `go/internal/web/staydetail/handlers.go` (2002 already uses `stayNotFound` → `NotFoundPage`; pin only reads it)
- Python, Caddy, `UBYHOST_GO_PATHS`, templates, CSS
- No new dependency

## 6. Commands

```bash
cd go && gofmt -l internal/web/settings/settings.go internal/web/properties/apartment_detail.go internal/web/properties/apartment_new.go internal/web/submissions/handlers.go internal/web/stays/*.go internal/web/staydetail/post.go internal/web/exports/exports.go internal/web/public/dev_ui_page.go internal/hostweb/notfound_host_pin_test.go 2>&1 | tail -30
# expect: empty

cd go && go test ./internal/hostweb/ -run TestHostPackagesNoBareNotFound -count=1 2>&1 | tail -30
# expect: PASS

cd go && go test ./internal/hostweb/ ./internal/web/staydetail/ ./internal/web/stays/ ./internal/web/settings/ ./internal/web/submissions/ ./internal/web/properties/ ./internal/web/exports/ ./internal/web/public/ -count=1 2>&1 | tail -30
# expect: ok / PASS; skips OK

cd .. && python3 scripts/context_lint.py 2>&1 | tail -30
# expect: exit 0

# proof no bare left in scope:
rg -n 'http\.NotFound\(|\[\]byte\("Not found\."\)' go/internal/web/settings go/internal/web/properties/apartment_detail.go go/internal/web/properties/apartment_new.go go/internal/web/submissions go/internal/web/stays go/internal/web/staydetail go/internal/web/exports/exports.go go/internal/web/public/dev_ui.go 2>&1 | tail -30
# expect: only JSON {"ok":false} WriteHeader lines in edit_posts.go if any; zero http.NotFound(
```

## 7. Acceptance

- [ ] Every §3 host HTML site uses `hostweb.NotFoundPage`; no `http.NotFound(` and no `[]byte("Not found.")` in the pin file list.
- [ ] `edit_posts.go` still returns JSON `{"ok":false}` with 404 when the stay is missing after a valid id parse.
- [ ] `TestHostPackagesNoBareNotFound` PASS.
- [ ] Package tests in §6 green (skips OK); `context_lint.py` exit 0.
- [ ] Report lists what was left out (guest, booking, JSON, misc alert) so the next sweep does not re-open them by mistake.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`);
- `exports/exports.go` lacks a clean place for the `hostweb` import;
- a file outside §3 needs a change;
- 2002 tip does not contain `NotFoundPage`;
- a step is unclear.

## 9. Report

Write `docs/tasks/2003-report.md` (600 tokens at most) and set `Status: review`.

## Risk list (for the reviewer)

- `apartment_detail.go` / `apartment_new.go` (plain text → branded)
- `stays/edit_posts.go` (only parse paths; JSON kept)
- `notfound_host_pin_test.go` (path to module root)
- `exports/exports.go` (download path parse)

## Owner steps

1. Merge PR #1256 (task 2002) with `scripts/merge-pr-on-green.sh` when green.
2. Then merge this 2003 PR the same way (or stack it on #1256 first).
3. After deploy: open a missing apartment URL and an unknown `/settings/nope` while logged in — expect the branded "Page not found" page, not black `404 page not found`.
4. Guest booking and guest form 404s stay as they are (out of scope).
