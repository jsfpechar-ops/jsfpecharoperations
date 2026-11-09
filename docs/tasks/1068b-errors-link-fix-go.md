# 1068b: No Bank QR without a bank account, same on the Go path

Status: todo
Depends on: 1068a and 1068a-cont-1 (copy keys, `fix` codes and the PNG body text are defined in 1068a) | Base commit: branch head after 1068a-cont-1 | Branch: `claude/1068-errors-link-fix` (same branch, after 1068a)
Executor: Opus (owner override) | Fits one session: 11 steps (several edits may share a tool call; commit per step). Queue item 1.4, Tier B.

## 1. Objective

The Go service is live in production for `/payments/requests/new`, `/payments/requests/*/send`, `/payments/requests/*/link`, `/payments/qr/*.png` and `/pay/*/*.png` (`UBYHOST_GO_PATHS`, docs/context/status.md). It must answer exactly as the Python routes changed in 1068a: no Bank QR request without a bank account, the same flashes with `fix=`, the same redirect targets, and the same plain 404 body on the QR PNG routes.

## 2. Context

Rules: AGENTS.md 8 (never push to main), 9 (copy). No new dependency, no new outbound request. Go strings come from `App/app/host_i18n.py` through `App/scripts/go_host_i18n.py`, run with **`App/.venv/bin/python`** (system `python3` lacks the app's imports); never hand-edit `go/internal/payments/i18n.json`.

**Python side, checked (1068a, `App/app/routes/payments.py`):** `payment_request_new` sends every error to `/payments/new` (`back = _back("/payments/new", err=_flash(request, "payments.err.invalid"))`, line ~179; amount error line ~185) and the no-account case to `/payments/new` with `fix="bank"`; `payment_request_link` (~249), `payment_request_share` (~273) and `payment_request_send` (~310) send `payments.err.not_ready` to `/payments` with `fix="stripe"` (lines ~264, ~286, ~334). Go has twins of create, link and send (share is a GET page, Python only).

**Go side, three gaps found in review:** (1) `RequestLinkHandler` (`paylink_routes.go:160`) has a second `payments.err.not_ready` besides `requests.go:253`; (2) Go sends the create errors `invalid` and `amount` to `/payments`, Python to `/payments/new` (`requests.go:102,112`); (3) the seed owner (user 1) has no IBAN, so the no-account block would break the existing "qr draft gets the variable symbol" test.

**Database tests:** every `*Database` test calls `testPool`, which does `t.Skip("UBYHOST_TEST_DATABASE_URL is not set")` without the variable, and `go test` then still prints `ok`. A skip is not a pass. `testPool` creates its own database and applies `App/migrations_pg/*.sql`, so an empty server is enough. CI (`.github/workflows/ci.yml`, job `go`, ~line 244) uses `UBYHOST_TEST_DATABASE_URL=postgresql://postgres:ubyhost@127.0.0.1:5432/ubyhost_test` against `postgres:17-alpine` with `POSTGRES_PASSWORD=ubyhost`, `POSTGRES_DB=ubyhost_test`. Start the same locally: `docker run -d --rm --name ubyhost-pg -e POSTGRES_PASSWORD=ubyhost -e POSTGRES_DB=ubyhost_test -p 5432:5432 postgres:17-alpine`, then `until docker exec ubyhost-pg pg_isready -U postgres; do sleep 1; done 2>&1 | tail -3`. Without Docker, `apt-get install -y postgresql` and `pg_ctlcluster` with a `postgres` user whose password is `ubyhost` and a database `ubyhost_test` give the same URL. If neither works, STOP (§8): do not report a skipped run as green.

**Anchors (verbatim from the branch head):**

`go/internal/hostweb/hostweb.go`:
```go
type Flash struct {
	Text  string
	Key   string
	Count int
}
```
```go
	if err.Text != "" {
		query = append(query, "err="+pyQuote(err.Text))
	}
```
`go/internal/payments/qrpng.go`, `QRPNGHandler` (~line 278), and `go/internal/payments/paylink_routes.go`, `GuestQRPNGHandler` (~line 75):
```go
		payload, err := qrPayload(ctx, pool, rowOwner, amount, vs)
		if errors.Is(err, errQRAccount) {
			w.WriteHeader(http.StatusNotFound)
			return
		}
```
```go
		payload, err := qrPayload(r.Context(), pool, owner, amount, vs)
		if errors.Is(err, errQRAccount) {
			w.WriteHeader(http.StatusNotFound)
			return
		}
```
`go/internal/payments/requests.go`, `RequestNewHandler`:
```go
		invalid := func() {
			hostweb.Back(w, r, "/payments", hostweb.Flash{}, requestFlash(lang, "payments.err.invalid"))
		}
```
```go
			hostweb.Back(w, r, "/payments", hostweb.Flash{}, requestFlash(lang, "payments.err.amount"))
```
```go
		rail := strings.TrimSpace(rawRail)
		if !requestRails[rail] {
			invalid()
			return
		}
		stamp := stampAt(at)
```
`requests.go`, `RequestSendHandler` (~line 252):
```go
			if link == "" {
				flashErr("payments.err.not_ready")
				return
			}
```
`go/internal/payments/paylink_routes.go`, `RequestLinkHandler` (~line 159):
```go
		if link == "" {
			flashErr("payments.err.not_ready")
			return
		}
```
`qrpng.go`: `qrEntitySQL = SELECT iban, bank_account FROM legal_entity WHERE owner_user_id = $1` (line 40), `func qrPNGBytes(payload string) ([]byte, error) {` (line 231), imports `"context"`, `"errors"`, `"net/http"` (lines 10-12). `go/internal/payments/i18n_keys.txt` lists `payments.err.not_ready` (line 9) and not `payments.err.no_iban`.

The constant body (from 1068a): `No bank account is set up for this payment request.` plus `\n`, `Content-Type: text/plain; charset=utf-8`, status 404. Every other refusal stays an empty 404 (existing tests assert `Body.Len() == 0`). **Out of scope:** Python `guest_qr_png` raises `HTTPException(status_code=404)` (a JSON body) for a bad token or missing row, while Go answers an empty 404 for the same cases; that difference exists today, is not changed by 1068a, and this brief does not touch it.

The fix codes are `bank` and `stripe`. Go only appends `fix=<code>` to the redirect; Python's allowlist decides whether a link shows. Go hands over the code, never a URL.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/hostweb/hostweb.go` | edit | `Flash.Fix`, `Back` appends `fix=` |
| `go/internal/hostweb/hostweb_test.go` | edit | one `TestBack` case |
| `go/internal/payments/qrpng.go` | edit | `qrNoAccount`, `hasBankAccount`, host PNG body |
| `go/internal/payments/paylink_routes.go` | edit | guest PNG body; `fix=stripe` on the link route |
| `go/internal/payments/requests.go` | edit | create errors to `/payments/new`; block `qr` without account; `fix=stripe` on send |
| `go/internal/payments/i18n_keys.txt` | edit | add `payments.err.no_iban` |
| `go/internal/payments/i18n.json` | regenerate | by the script only |
| `go/internal/payments/qrpng_test.go`, `paylink_routes_test.go`, `requests_test.go` | edit | tests |

No other file may change. Never edit `App/` in this brief.

## 4. Steps

Work from the repo root unless a command says `cd`. Commit after each step as `1068b step k`. Start with `cd go && go version 2>&1 | tail -2` and the database from §2 (`export UBYHOST_TEST_DATABASE_URL=postgresql://postgres:ubyhost@127.0.0.1:5432/ubyhost_test` for every Go command).

1. **Flash field.** In `go/internal/hostweb/hostweb.go` replace the `type Flash struct` anchor with
```go
type Flash struct {
	Text  string
	Key   string
	Count int
	Fix   string
}
```
Command: `cd go && gofmt -l internal/hostweb/ | head -3; go build ./internal/hostweb/ 2>&1 | tail -30`. Expect no output.

2. **Back appends fix.** In `hostweb.go`, directly after the `if err.Text != "" {` anchor block add
```go
	if err.Fix != "" {
		query = append(query, "fix="+pyQuote(err.Fix))
	}
```
(order matches Python `back`: `err`, then `fix`). In `hostweb_test.go`, in the `cases` table of `TestBack`, after the `"both"` line add
```go
		{"err with fix", "/a", Flash{}, Flash{Text: "Bad", Fix: "bank"}, "/a?err=Bad&fix=bank"},
```
Command: `cd go && go test ./internal/hostweb/ -count=1 2>&1 | tail -30`. Expect `ok`.

3. **PNG helper.** In `qrpng.go` add `"io"` to the imports (after `"errors"`), and directly below `qrPNGBytes` add
```go
// qrNoAccountBody is payment_request.NO_ACCOUNT_BODY in Python.
const qrNoAccountBody = "No bank account is set up for this payment request.\n"

// qrNoAccount answers the QR PNG routes when the host has no bank account.
func qrNoAccount(w http.ResponseWriter) {
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	w.WriteHeader(http.StatusNotFound)
	_, _ = io.WriteString(w, qrNoAccountBody)
}
```
Command: `cd go && go vet ./internal/payments/ 2>&1 | tail -30`. Expect no output (an unused-function warning does not exist in Go; the next steps use it).

4. **Account helper.** In `qrpng.go`, directly below `qrNoAccount`, add
```go
// hasBankAccount is payment_request.has_bank_account: the owner's legal
// entity carries an IBAN or a Czech account.
func hasBankAccount(ctx context.Context, pool *pgxpool.Pool, owner int64) (bool, error) {
	var iban, bank *string
	err := pool.QueryRow(ctx, qrEntitySQL, owner).Scan(&iban, &bank)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	return (iban != nil && *iban != "") || (bank != nil && *bank != ""), nil
}
```
Command: `cd go && go build ./internal/payments/ 2>&1 | tail -30`. Expect no output.

5. **Host PNG body.** In `qrpng.go`, in the first `errors.Is(err, errQRAccount)` anchor (`QRPNGHandler`) replace `w.WriteHeader(http.StatusNotFound)` with `qrNoAccount(w)`; change the doc comment above `QRPNGHandler` to `// refusal is a 404 with an empty body, as in Python, except a missing bank account (qrNoAccount).` keeping its first line. In `qrpng_test.go`, `TestQRPNGDatabase`, replace the last block
```go
	if rec := qrGet(t, mux, "/payments/qr/10.png", 1); rec.Code != http.StatusNotFound {
		t.Errorf("no bank account: %d, want 404", rec.Code)
	}
```
with
```go
	rec = qrGet(t, mux, "/payments/qr/10.png", 1)
	if rec.Code != http.StatusNotFound || rec.Header().Get("Content-Type") != "text/plain; charset=utf-8" || rec.Body.String() != qrNoAccountBody {
		t.Errorf("no bank account: %d %q %q, want the plain 404 body", rec.Code, rec.Header().Get("Content-Type"), rec.Body.String())
	}
```
Command: `cd go && go test -v -run TestQRPNGDatabase ./internal/payments/ -count=1 2>&1 | tail -8`. Expect `--- PASS: TestQRPNGDatabase` and `ok`, no `SKIP`.

6. **Guest PNG body.** In `paylink_routes.go`, in the `GuestQRPNGHandler` anchor replace `w.WriteHeader(http.StatusNotFound)` with `qrNoAccount(w)`. In `paylink_routes_test.go`, `TestGuestQRPNGDatabase`, directly before the block that starts `if _, err := pool.Exec(t.Context(), `UPDATE payment_request SET status = 'cancelled' WHERE id = 10`)` insert
```go
	if _, err := pool.Exec(t.Context(), `UPDATE legal_entity SET iban = NULL, bank_account = NULL WHERE owner_user_id = 1`); err != nil {
		t.Fatal(err)
	}
	rec = get(fmt.Sprintf("/pay/10/%s.png", good))
	if rec.Code != http.StatusNotFound || rec.Header().Get("Content-Type") != "text/plain; charset=utf-8" || rec.Body.String() != qrNoAccountBody {
		t.Errorf("no bank account: %d %q %q, want the plain 404 body", rec.Code, rec.Header().Get("Content-Type"), rec.Body.String())
	}
	if rec := get("/pay/10/" + strings.Repeat("0", 32) + ".png"); rec.Code != http.StatusNotFound || rec.Body.Len() != 0 {
		t.Errorf("wrong token without account: %d with %d body bytes, want empty 404", rec.Code, rec.Body.Len())
	}
	if _, err := pool.Exec(t.Context(), `UPDATE legal_entity SET iban = 'CZ6508000000192000145399' WHERE owner_user_id = 1`); err != nil {
		t.Fatal(err)
	}
```
Command: `cd go && go test -v -run TestGuestQRPNGDatabase ./internal/payments/ -count=1 2>&1 | tail -8`. Expect `--- PASS`, no `SKIP`.

7. **Create errors go to /payments/new.** In `requests.go`, `RequestNewHandler`: in the `invalid := func() {` anchor and in the `payments.err.amount` anchor change `"/payments"` to `"/payments/new"` (the draft-saved redirect `hostweb.Back(w, r, "/payments", requestFlash(lang, "payments.draft_saved"), hostweb.Flash{})` stays `/payments`). In `requests_test.go`, `TestRequestNewDatabase`, the table loop: replace
```go
			if rec.Code != http.StatusSeeOther || !strings.HasPrefix(loc, "/payments?err=") {
```
with
```go
			if rec.Code != http.StatusSeeOther || !strings.HasPrefix(loc, "/payments/new?err=") {
```
Command: `grep -c '"/payments/new"' go/internal/payments/requests.go`. Expect `2`. Then `cd go && go test -v -run TestRequestNewDatabase ./internal/payments/ -count=1 2>&1 | tail -12`. Expect `ok`, no `SKIP`.

8. **Block the Bank QR create.** In `requests.go`, directly after the `requestRails[rail]` anchor block (`invalid()` / `return` / `}`) and before `stamp := stampAt(at)` add
```go
		if rail == "qr" {
			has, err := hasBankAccount(ctx, pool, owner)
			if err != nil {
				requestFail(w, err)
				return
			}
			if !has {
				f := requestFlash(lang, "payments.err.no_iban")
				f.Fix = "bank"
				hostweb.Back(w, r, "/payments/new", hostweb.Flash{}, f)
				return
			}
		}
```
In `requests_test.go`, `TestRequestNewDatabase`: (a) directly after the table loop (`})` closing `for ... { t.Run(...) }`) and before `t.Run("card draft is saved with every column"`, add the no-account case; the seed owner has no IBAN, so it runs first, and the existing card test right after it proves a card draft still saves without an account:
```go
	t.Run("qr without a bank account flashes, links the fix and saves nothing", func(t *testing.T) {
		n := total()
		rec := requestCall(t, mux, path, 1, url.Values{"reason": {"repair"}, "amount_czk": {"110"}, "rail": {"qr"}})
		loc := rec.Header().Get("Location")
		if rec.Code != http.StatusSeeOther || !strings.HasPrefix(loc, "/payments/new?err=") || !strings.HasSuffix(loc, "&fix=bank") {
			t.Errorf("got %d %q, want /payments/new?err=...&fix=bank", rec.Code, loc)
		}
		if total() != n {
			t.Error("a row was saved")
		}
	})
```
(b) In the subtest `t.Run("qr draft gets the variable symbol", func(t *testing.T) {` add as its first statement (the owner needs an account now):
```go
		if _, err := pool.Exec(context.Background(), `UPDATE legal_entity SET iban = 'CZ6508000000192000145399' WHERE owner_user_id = 1`); err != nil {
			t.Fatal(err)
		}
```
Command: `cd go && go test -v -run TestRequestNewDatabase ./internal/payments/ -count=1 2>&1 | tail -15`. Expect `ok`, every subtest `PASS`, no `SKIP`.

9. **Send: not_ready links to Stripe setup.** In `requests.go`, `RequestSendHandler`, in the `link == ""` anchor replace `flashErr("payments.err.not_ready")` with
```go
				f := requestFlash(lang, "payments.err.not_ready")
				f.Fix = "stripe"
				hostweb.Back(w, r, "/payments", hostweb.Flash{}, f)
```
(`flashErr` keeps its signature; it still serves every other error.) In `requests_test.go`, `TestRequestSendDatabase`, replace the body of `t.Run("card not ready flashes", ...)` after `rec := send(11, 1)` with
```go
		loc := rec.Header().Get("Location")
		if !strings.HasPrefix(loc, "/payments?err=") || !strings.HasSuffix(loc, "&fix=stripe") || requestStatus(t, pool, 11) != "draft" {
			t.Errorf("got %q", loc)
		}
```
and in `t.Run("card with stripe off flashes and sends no mail", ...)` add after its existing `if` block: `if strings.Contains(rec.Header().Get("Location"), "fix=") { t.Error("stripe off carries a fix link") }` (the server switch is not fixable by the host). Command: `cd go && go test -v -run TestRequestSendDatabase ./internal/payments/ -count=1 2>&1 | tail -15`. Expect `ok`, no `SKIP`.

10. **Link route: not_ready links to Stripe setup.** In `paylink_routes.go`, `RequestLinkHandler`, in the `link == ""` anchor replace `flashErr("payments.err.not_ready")` with
```go
			f := requestFlash(lang, "payments.err.not_ready")
			f.Fix = "stripe"
			hostweb.Back(w, r, "/payments", hostweb.Flash{}, f)
```
In `paylink_routes_test.go`, `TestRequestLinkDatabase`, replace
```go
	if !strings.HasPrefix(rec.Header().Get("Location"), "/payments?err=") {
		t.Errorf("not ready: %q", rec.Header().Get("Location"))
	}
```
with
```go
	if loc := rec.Header().Get("Location"); !strings.HasPrefix(loc, "/payments?err=") || !strings.HasSuffix(loc, "&fix=stripe") {
		t.Errorf("not ready: %q", loc)
	}
```
Command: `cd go && go test -v -run TestRequestLinkDatabase ./internal/payments/ -count=1 2>&1 | tail -8`. Expect `ok`, no `SKIP`.

11. **Copy, then verify everything.**
 a. Add `payments.err.no_iban` to `go/internal/payments/i18n_keys.txt` directly after `payments.err.not_ready`. From `App/` (the venv from 1068a exists; otherwise `python3 -m venv .venv && .venv/bin/python -m pip install --quiet -r requirements.txt`): `.venv/bin/python scripts/go_host_i18n.py 2>&1 | tail -5`, then `.venv/bin/python scripts/go_host_i18n.py --check 2>&1 | tail -5; echo exit=$?`, then `.venv/bin/python -m pytest tests/test_go_host_i18n.py -q --tb=short -x 2>&1 | tail -30`. Expect check `exit=0` and the test green.
 b. Database tests must run, not skip. From `go/`, with the URL from the start of §4: `go test -v -run Database ./internal/payments/ -count=1 2>&1 | grep -c SKIP`. Expect `0`. Also `go test -v -run Database ./internal/payments/ -count=1 2>&1 | grep -c -- '--- PASS: Test.*Database'`; expect at least 7 (`TestConnectDatabase`, `TestGuestQRPNGDatabase`, `TestRequestLinkDatabase`, `TestQRPNGDatabase`, `TestRequestNewDatabase`, `TestRequestSendDatabase`, `TestWebhookDatabase`).
 c. As CI does (`ci.yml` job `go`), from `go/` with the URL: `test -z "$(gofmt -l .)"; echo gofmt=$?`, `go vet ./... 2>&1 | tail -30`, `go test ./... -count=1 2>&1 | tail -30`, `go build ./cmd/ubyhost-web 2>&1 | tail -5`. Expect `gofmt=0`, no vet output, `ok` on every line, no build output.
 d. Parity with Python: from `App/`, `.venv/bin/python -m pytest tests/test_payment_rails.py -q --tb=short -x 2>&1 | tail -30` (1068a tests, green), and `grep -n "No bank account is set up" ../go/internal/payments/qrpng.go app/payment_request.py`. Expect the same sentence in both.
 e. Stop the database if you started it: `docker stop ubyhost-pg 2>&1 | tail -1`.

## 5. Do not touch

`App/`, Caddy and `UBYHOST_GO_PATHS`, `go.mod`/`go.sum` (no dependency), webhook, Connect and push code, the guest QR path logic beyond the one status line. The Python `guest_qr_png` JSON 404 body versus Go's empty 404 for unrelated refusals. AGENTS.md rules 4, 8.

## 6. Commands

As in the steps. Go: the single-test commands per step, then once the CI trio in step 11c.

## 7. Acceptance

- [ ] Step 11b prints `0` skips and at least 7 passing `*Database` tests (a skipped run is not accepted; if no database can be started the report is `blocked`).
- [ ] Step 11c: `gofmt=0`, vet clean, `go test ./... -count=1` `ok` on every line.
- [ ] Go no-account PNG (host and guest): 404, `text/plain; charset=utf-8`, body equals the Python body byte for byte.
- [ ] Go POST `rail=qr` without account: 303 to `/payments/new?err=...&fix=bank`, no row; Python does the same (1068a test). Create errors (`invalid`, `amount`) go to `/payments/new` as in Python.
- [ ] `payments.err.not_ready` from Go send and Go link ends `&fix=stripe`; `stripe_off` carries no `fix`.
- [ ] `App/.venv/bin/python scripts/go_host_i18n.py --check` exits 0.
- [ ] Other 404 refusals still have an empty body.

## 8. Stop and ask

Stop and report `blocked` if an anchor is missing, `go build` fails twice, no test database can be started (do not call a skipped run a pass), a new dependency seems needed, a file outside §3 needs a change, or you reach 30 tool calls or about 50k tokens. Then write the report with `Done: steps 1 to k. Left: steps k+1 to 11.`

## 9. Report

`docs/tasks/1068b-report.md` (600 tokens at most), `Status: review`: files changed, each command with its last 5 lines, the SKIP count, §7 ticked, deviations.

## Risk list (for the reviewer)

`go/internal/payments/requests.go` (production create and send routes; the create redirect target changes to `/payments/new` for `invalid` and `amount`, matching Python), `paylink_routes.go` (production link route and public guest PNG), `hostweb.go` `Back` (used by every Go host route; `fix=` appears only when `Fix` is set), `qrpng.go`.

## Owner steps

1. After both PRs merge, deploy once (the owner does production deploys). The Go change takes effect with the Go container; no Caddy or `UBYHOST_GO_PATHS` change.
2. Check on production: open `/payments/new` with a test owner that has no bank account and confirm the Bank QR option is disabled with "Add bank account (1 min)".
