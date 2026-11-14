# 1630: A Go "not ported yet" answer falls back to Python instead of reaching the host

Status: todo
Depends on: none | Base commit: none (one big PR mode, see below) | Branch: the orchestrator's current branch
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

**One big PR mode.** Work on the branch that is checked out now. Never create a branch, never push, never open a PR, no `mcp__` tools. Commit after each step with the message `1630 step k` (k = the step number), and the report as `1630 report`. The orchestrator opens the one PR.

## 1. Objective

`go/internal/web/properties/lists.go` answers HTTP 501 ("not served by Go yet: ...") for three real cases: `GET /apartments` when the workspace has a live property, `GET /entities` when the workspace has an open alert, and `GET /entities?edit=` with a non-ASCII number. Caddy sends every path in `UBYHOST_GO_PATHS` to `ubyhost-go:8081` with no fallback, so if the owner listed `/apartments` or `/entities` (brief 1412 told him to, on staging), a real host sees a bare 501 page. After this brief a Go "not ported" answer is invisible: Caddy re-sends the same GET/HEAD request to Python and the host gets the normal Python page.

## 2. Context

Tier A (deploy routing). Rules: 3 nothing real in the repo; 4 no new dependency (nothing is added: the Caddy feature is built in, Go uses only `net/http`). No file under `App/` changes.

**Design chosen: (a) Caddy `handle_response`, not (b) a Go-side proxy.**

- (a) needs 12 lines of Caddyfile and one header in Go. Caddy already knows the Python upstream (`ubyhost:8080`) and already overwrites `CF-Connecting-IP` for it; the fallback reuses both.
- (b) would make Go dial Python (a new env var like `UBYHOST_PY_WEBHOOK_URL`, cookie/IP/header forwarding re-implemented, a second place that must keep `CF-Connecting-IP` trustworthy). More code, more risk of a header-trust bug. Chosen only if (a) fails; no concrete reason for that was found.
- Caddy v2 semantics relied on: `reverse_proxy` accepts response matchers (`@name { status 501 ... }`, matchers `status` and `header`) and `handle_response @name { ... }`. When it matches, Caddy does NOT copy Go's response; it runs the routes in the block instead. A `reverse_proxy` inside the block proxies the original client request again, to the new upstream. That re-send is only safe for a request with no body, so the block is reached only for GET and HEAD (the `method` matcher below). The Go answer is matched by status 501 AND the header `X-Ubyhost-Not-Ported: 1`, so a genuine 501 from anywhere else (Go panics are 500, but any future 501) is never re-sent. Python's answer carries no such header, so the client never sees it.
- The fallback is registered in its own `handle @go_read` block placed BEFORE the existing `handle @go`; `handle` blocks are mutually exclusive in order, so GET/HEAD to a Go path take the new block, every other method keeps the old `handle @go` (unchanged behaviour: a 501 to a POST is shown as is).
- `{client_ip}` / `{remote_host}` are request placeholders, so they evaluate the same inside the nested block. The nested `reverse_proxy` MUST keep the same `header_up CF-Connecting-IP ...` line as the plain Python block (a client-sent value must never reach the app).

**Limit, stated on purpose.** POST `/apartments` is not registered in the Go mux (Go answers 405), so `/apartments` is only safe in `UBYHOST_GO_PATHS` for GET and HEAD, and this fallback does not cover POST. On the PR branch POST `/entities` is also not registered (405); on go-wave3 `go/internal/web/properties/entities.go` registers `POST /entities` and `POST /entities/{id}` (brief 1522) but its "Fill from register" branch and the pages behind other 501s are not complete. Treat both POSTs as staying on Python until the owner has checked them: the "add" forms of those two pages break on any server that lists the paths (the 1412 owner steps already say "do not use them"). The fallback fixes the page view only. Do not widen it to POST.

**What a signed-in user notices when this deploys:** nothing, until `/apartments` or `/entities` is in `UBYHOST_GO_PATHS`. With the paths listed and a host that has a live property, `/apartments` shows the Python page (200) instead of a bare "not served by Go yet" error. With the paths not listed, Caddy behaves as before.

**Verified by the brief writer (2026-11-14).** Steps 1-4 applied exactly as written in a scratch tree (dropped afterwards): gofmt, `go build ./...` and `go vet` clean; `go test -v ./internal/web/properties/...` with PostgreSQL 16 passes, 0 FAIL, 0 SKIP, `TestNotPortedHeader` passes. `caddy validate --adapter caddyfile` (Caddy v2.10.2 built locally) prints `Valid configuration` for Caddyfile.acme and Caddyfile.cloudflare, each with and without `UBYHOST_APP_DOMAIN` (cloudflare needs the origin cert files, as in CI). Functional check with the same block on localhost and two stub upstreams (Go stub, Python stub): GET to a Go path with a 501 plus the header returns Python's 200; HEAD likewise; a 501 without the header passes through as 501; a POST to the same path is not re-sent (501 from Go); a path not in the list goes to Python; a client-sent `CF-Connecting-IP: 6.6.6.6` was replaced on both the Go hop and the Python fallback hop. Not run here: Docker (no daemon), so the `caddy-validate.sh` wrapper itself (step 5) was not run.

Anchors (step 0, each `grep -cF '<anchor>' <file>` prints 1 unless the table says 2):

| File | Anchor | Count |
|---|---|---|
| `go/internal/web/properties/lists.go` | `http.Error(w, "not served by Go yet: "+what, http.StatusNotImplemented)` | 1 |
| `go/internal/web/properties/lists.go` | `notPorted(w, "the property list")` | 1 |
| `go/internal/web/properties/lists.go` | `notPorted(w, "host alerts on this page")` | 1 |
| `go/internal/web/properties/lists_test.go` | `if rec.Code != tc.Go \|\| want.Status != http.StatusOK \|\| want.Name != tc.Name {` | 1 |
| `deploy/lightsail/caddy/Caddyfile.cloudflare` | `@go path {$UBYHOST_GO_PATHS:/__go_off__}` | 1 |
| `deploy/lightsail/caddy/Caddyfile.cloudflare` | `header_up CF-Connecting-IP {client_ip}` | 2 |
| `deploy/lightsail/caddy/Caddyfile.acme` | `@go path {$UBYHOST_GO_PATHS:/__go_off__}` | 1 |
| `deploy/lightsail/caddy/Caddyfile.acme` | `header_up CF-Connecting-IP {remote_host}` | 2 |
| `deploy/lightsail/scripts/caddy-validate.sh` | `caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile` | 1 |

(In `Caddyfile.cloudflare` the 2 hits of `header_up CF-Connecting-IP {client_ip}` are the Go block and the Python block; in `Caddyfile.acme` the 2 hits of `{remote_host}` likewise.) The `grep -cF` for the `\|\|` anchor: use `grep -cF 'if rec.Code != tc.Go || want.Status != http.StatusOK || want.Name != tc.Name {'` (the backslashes in the table are table escaping only).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/properties/lists.go` | edit | `notPorted` sets `X-Ubyhost-Not-Ported: 1` |
| `go/internal/web/properties/lists_test.go` | edit | the not-ported loop also checks the header |
| `go/internal/web/properties/notported_test.go` | create | unit test of `notPorted` |
| `deploy/lightsail/caddy/Caddyfile.cloudflare` | edit | new `handle @go_read` block |
| `deploy/lightsail/caddy/Caddyfile.acme` | edit | same block, `{remote_host}` |
| `docs/ENVIRONMENT.md` | edit | one sentence on the `UBYHOST_GO_PATHS` row |
| `docs/tasks/1630-report.md` | create | the report |

## 4. Steps

0. Checks (one call, repo root): `git status --short | tail -5` prints nothing; every anchor of section 2 prints its count. Anything else: STOP. No commit.

1. Go: mark the answer. In `go/internal/web/properties/lists.go` replace

```go
func notPorted(w http.ResponseWriter, what string) {
	http.Error(w, "not served by Go yet: "+what, http.StatusNotImplemented)
}
```

with

```go
func notPorted(w http.ResponseWriter, what string) {
	// Caddy re-sends a GET/HEAD that carries this header to Python (brief 1630).
	w.Header().Set("X-Ubyhost-Not-Ported", "1")
	http.Error(w, "not served by Go yet: "+what, http.StatusNotImplemented)
}
```

   Update the comment above `notPorted` to add: `The header X-Ubyhost-Not-Ported lets Caddy fall back to Python (brief 1630).` (`http.Error` keeps headers already set, it only overwrites Content-Type and X-Content-Type-Options.)

   Check: `cd go && gofmt -l internal/web/properties 2>&1 | tail -3; go vet ./internal/web/properties/ 2>&1 | tail -5` prints nothing. Commit `1630 step 1`.

2. Go tests. (a) Create `go/internal/web/properties/notported_test.go`:

```go
package properties

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// Brief 1630: every "not served by Go yet" answer is a 501 with the header
// Caddy matches on, so a real 501 from elsewhere is never re-sent to Python.
func TestNotPortedHeader(t *testing.T) {
	for _, what := range []string{
		"the property list",
		"host alerts on this page",
		"the business editor (?edit= with a non-ASCII number)",
		"the ARES lookup (Fill from register)",
	} {
		rec := httptest.NewRecorder()
		notPorted(rec, what)
		if rec.Code != http.StatusNotImplemented {
			t.Errorf("%s: code %d, want 501", what, rec.Code)
		}
		if got := rec.Header().Get("X-Ubyhost-Not-Ported"); got != "1" {
			t.Errorf("%s: header %q, want 1", what, got)
		}
	}
}
```

   (b) In `go/internal/web/properties/lists_test.go`, replace

```go
			if rec.Code != tc.Go || want.Status != http.StatusOK || want.Name != tc.Name {
```

   with

```go
			if rec.Code != tc.Go || want.Status != http.StatusOK || want.Name != tc.Name || rec.Header().Get("X-Ubyhost-Not-Ported") != "1" {
```

   This proves the header on the two real branches the golden file exercises (`the property list`, `host alerts on this page`); the branch with `?edit=` and the ARES placeholder go through the same helper, which (a) covers.

   Run: `cd go && gofmt -l internal/web/properties 2>&1 | tail -3; go vet ./internal/web/properties/ 2>&1 | tail -5; go test -count=1 -run 'TestNotPortedHeader' ./internal/web/properties/ 2>&1 | tail -5`. Expected: no gofmt/vet output, `ok`. Commit `1630 step 2`.

3. Caddyfile.cloudflare. Replace exactly this text

```
	@go path {$UBYHOST_GO_PATHS:/__go_off__}
	handle @go {
```

   with

```
	@go path {$UBYHOST_GO_PATHS:/__go_off__}
	# 1630: a Go page that is not ported yet answers 501 plus X-Ubyhost-Not-Ported.
	# For GET and HEAD (no body, safe to send again) Caddy then asks Python for the
	# same URL. Other methods and every other 501 are passed through unchanged.
	@go_read {
		path {$UBYHOST_GO_PATHS:/__go_off__}
		method GET HEAD
	}
	handle @go_read {
		reverse_proxy ubyhost-go:8081 {
			header_up CF-Connecting-IP {client_ip}
			@not_ported {
				status 501
				header X-Ubyhost-Not-Ported 1
			}
			handle_response @not_ported {
				reverse_proxy ubyhost:8080 {
					# Always overwrite: a client-sent CF-Connecting-IP must never reach the app.
					header_up CF-Connecting-IP {client_ip}
				}
			}
		}
	}
	handle @go {
```

   Leave the old `handle @go { ... }` block and the final `handle { ... }` block as they are. Commit `1630 step 3`.

4. Caddyfile.acme. The same replacement, with `{remote_host}` in both `header_up` lines (and the Python line's comment `# No Cloudflare in front: the TCP peer is the client.`):

```
	@go path {$UBYHOST_GO_PATHS:/__go_off__}
	# 1630: (same comment as in Caddyfile.cloudflare)
	@go_read {
		path {$UBYHOST_GO_PATHS:/__go_off__}
		method GET HEAD
	}
	handle @go_read {
		reverse_proxy ubyhost-go:8081 {
			header_up CF-Connecting-IP {remote_host}
			@not_ported {
				status 501
				header X-Ubyhost-Not-Ported 1
			}
			handle_response @not_ported {
				reverse_proxy ubyhost:8080 {
					# No Cloudflare in front: the TCP peer is the client.
					header_up CF-Connecting-IP {remote_host}
				}
			}
		}
	}
	handle @go {
```

   Commit `1630 step 4`.

5. Validate both Caddyfiles with the production image (exactly what CI does, `.github/workflows/ci.yml`, job "Validate every Caddyfile"). From the repo root:

```bash
cd deploy/lightsail && touch .env && openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj /CN=ubyhost.example -keyout caddy/certs/origin-key.pem -out caddy/certs/origin.pem 2>/dev/null
for f in caddy/Caddyfile.acme caddy/Caddyfile.cloudflare; do for app in "" app.ubyhost.example; do echo "==> $f '$app'"; cp "$f" caddy/Caddyfile.active; UBYHOST_DOMAIN=ubyhost.example ACME_EMAIL=ci@ubyhost.example UBYHOST_APP_DOMAIN="$app" ./scripts/caddy-validate.sh 2>&1 | tail -3; done; done
```

   Expected: four `Valid configuration` lines, no `Error`. The script needs a running Docker daemon (`docker info | head -2` first). If there is no daemon, or the image cannot be pulled, do NOT claim it passed: write "caddy validate not run" in the report and leave it to CI and the owner (step 1 of the owner steps). Afterwards delete the files this step created: `rm -f caddy/Caddyfile.active caddy/certs/origin-key.pem caddy/certs/origin.pem .env` (all are git-ignored, but `git status --short` must print nothing from `deploy/` except the two Caddyfiles). No commit.

6. `docs/ENVIRONMENT.md`: in the `UBYHOST_GO_PATHS` table row, directly before the sentence beginning `Booking-site events on` add: `A GET or HEAD to a listed path that Go answers with 501 and the header X-Ubyhost-Not-Ported (a page not ported yet) is sent again to Python by Caddy; POST is not, so keep paths whose forms Go does not serve (POST /apartments) off the list.` Check: `grep -cF 'X-Ubyhost-Not-Ported' docs/ENVIRONMENT.md` prints `1`. Commit `1630 step 6`.

7. Run section 6, write the report (section 9) and commit it as `1630 report`.

## 5. Do not touch

`go/internal/hostweb/`, `go/cmd/`, the other Go packages, `go/go.mod`, `go/go.sum`, `App/`, `deploy/lightsail/docker-compose.yml`, `deploy/lightsail/scripts/`, `.github/`, `docs/context/*` (read-only), `.env` files. Do not add `/apartments` or `/entities` to any env default.

## 6. Commands

From the repo root:

- `cd go && go build ./... 2>&1 | tail -30` prints nothing.
- `cd go && go vet ./internal/web/properties/... 2>&1 | tail -30` prints nothing.
- `cd go && go test -count=1 ./internal/web/properties/... 2>&1 | tail -30` prints only `ok` lines. The golden tests need `UBYHOST_TEST_DATABASE_URL` (they skip without it; CI runs them). Start a throwaway PostgreSQL on a port nobody else uses, data dir under `/var/tmp`, set the variable, and report the SKIP count: `go test -count=1 -v ./internal/web/properties/... 2>&1 | grep -c -- '--- SKIP'` must print `0`.
- Step 5 validate loop: four `Valid configuration`, or "not run" stated in the report.
- `git status --short | tail -5` prints nothing after the last commit.

Test-map: no row covers Go packages or the Caddyfiles beyond CI's Caddy job; the commands above are this brief's tests.

## 7. Acceptance

- [ ] `git log --oneline --grep='^1630 step'` lists steps 1, 2, 3, 4, 6 and `--grep='^1630 report'` the report.
- [ ] `grep -c 'X-Ubyhost-Not-Ported' go/internal/web/properties/lists.go` prints `2` or more, and `grep -c 'handle_response @not_ported' deploy/lightsail/caddy/Caddyfile.cloudflare deploy/lightsail/caddy/Caddyfile.acme` prints `...cloudflare:1` and `...acme:1`.
- [ ] `grep -c 'header_up CF-Connecting-IP' deploy/lightsail/caddy/Caddyfile.cloudflare` prints `4` and the same for `Caddyfile.acme` prints `4` (every upstream block overwrites the header).
- [ ] `grep -n 'method GET HEAD' deploy/lightsail/caddy/Caddyfile.cloudflare deploy/lightsail/caddy/Caddyfile.acme` prints one line each.
- [ ] `TestNotPortedHeader` passes and the properties golden test passes with 0 skipped (or the PostgreSQL gap is named in the report).
- [ ] `for c in $(git log --format=%h --grep='^1630 '); do git show --name-only --format= $c; done | sort -u` lists only the files of section 3 plus `docs/tasks/1630-go-not-ported-fallback.md`.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor is missing or has another count (say which);
- `caddy validate` reports an error for the new block (paste the error; do not guess a different syntax more than once);
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (report as `blocked`);
- a new dependency seems needed, or a file outside section 3 needs a change;
- you need push, merge, secrets, SSH or deploy (hand it to the owner with the exact command).

## 9. Report

Write `docs/tasks/1630-report.md` (600 tokens at most) and set `Status: review`. The report has: 1. files changed; 2. each command with the last 5 lines of output (including whether caddy validate ran); 3. section 7 ticked; 4. deviations; 5. questions; 6. owner steps left.

## Risk list (for the reviewer)

- `deploy/lightsail/caddy/Caddyfile.cloudflare` and `Caddyfile.acme`: the new `@go_read` block must come before `handle @go`; both nested `header_up CF-Connecting-IP` lines must be present (spoofing); the matcher must require BOTH status 501 and the header; only GET and HEAD.
- `go/internal/web/properties/lists.go`: only the header line is new; the 501 and body are unchanged.
- A POST to a listed path is not rescued (by design).

## Owner steps

Do step 1 NOW, before any deploy; it is the only urgent one.

1. URGENT, production, check today. On the production server run `cd /opt/ubyhost/deploy/lightsail && grep -n '^UBYHOST_GO_PATHS' .env`. If the line contains `/apartments` or `/entities` (exactly these, with nothing after them; `/entities/...` forms are separate), remove only those words: `nano .env`, delete them from inside the quotes, keep every other path, never leave the value empty (use `/__go_off__` if nothing else is left), save with Ctrl+O, Enter, Ctrl+X. Then `./scripts/caddy-validate.sh` (must end without an error) and `docker compose up -d caddy`. Why: Go cannot yet show those two pages for a host with a property or an open alert; the host would see a bare error. Tell the orchestrator what the line was before and after.
2. After this brief is merged and deployed (the normal deploy; Caddyfile files come with it), on the production server: `cd /opt/ubyhost/deploy/lightsail && ./scripts/caddy-validate.sh` (must end without an error), then `docker compose up -d caddy`.
3. Only if you want to test the fallback, on STAGING (never production first): add `/apartments` to `UBYHOST_GO_PATHS` as described in brief 1412, `./scripts/caddy-validate.sh`, `docker compose up -d caddy`, sign in as a host whose workspace has a live property, open `/apartments`. Expected: the normal page loads (200), not the words "not served by Go yet". Then remove the path again and repeat the validate and `up -d caddy` commands.
4. Remember: do not use the "add" forms of Entities and Apartments while those paths are on Go; the fallback covers only viewing pages, not saving forms.
