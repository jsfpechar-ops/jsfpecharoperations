# 1068b: No Bank QR without a bank account, same on the Go path

Status: todo
Depends on: 1068a (copy keys, `fix` codes and the PNG body text are defined there) | Base commit: origin/main after 1068a | Branch: `claude/1068-errors-link-fix` (same branch, after 1068a)
Executor: Opus (owner override) | Fits one session: 7 steps. Queue item 1.4, Tier B.

## 1. Objective

The Go service is live in production for `/payments/requests/new`, `/payments/requests/*/send`, `/payments/qr/*.png` and `/pay/*/*.png` (`UBYHOST_GO_PATHS`, docs/context/status.md). It must answer exactly as the Python routes changed in 1068a: no Bank QR request without a bank account, the same flash with `fix=`, and the same plain 404 body on the QR PNG routes.

## 2. Context

Rules: AGENTS.md 8 (never push to main), 9 (copy). No new dependency, no new outbound request. Go strings come from `App/app/host_i18n.py` through `python3 scripts/go_host_i18n.py` (from `App/`); never hand-edit `go/internal/payments/i18n.json`.

Anchors (verbatim):

`go/internal/payments/qrpng.go`, the handler `QRPNGHandler`:
```go
		payload, err := qrPayload(ctx, pool, rowOwner, amount, vs)
		if errors.Is(err, errQRAccount) {
			w.WriteHeader(http.StatusNotFound)
			return
		}
```
`go/internal/payments/paylink_routes.go`, `GuestQRPNGHandler`:
```go
		payload, err := qrPayload(r.Context(), pool, owner, amount, vs)
		if errors.Is(err, errQRAccount) {
			w.WriteHeader(http.StatusNotFound)
			return
		}
```
`go/internal/payments/requests.go`, `RequestNewHandler`:
```go
		rail := strings.TrimSpace(rawRail)
		if !requestRails[rail] {
			invalid()
			return
		}
		stamp := stampAt(at)
```
`go/internal/payments/requests.go:253` `flashErr("payments.err.not_ready")` inside `RequestSendHandler` (`flashErr := func(key string) {` at ~204).
`go/internal/hostweb/hostweb.go`: `type Flash struct { Text string; Key string; Count int }` (line 34) and `func Back(w http.ResponseWriter, r *http.Request, path string, msg, err Flash)` (line 92), which appends `err=` from `err.Text`.
`go/internal/payments/qrpng.go`: `qrEntitySQL = SELECT iban, bank_account FROM legal_entity WHERE owner_user_id = $1` and `qrPayload` (line 176-210) returning `errQRAccount` when both are empty.
`go/internal/payments/i18n_keys.txt` lists `payments.err.not_ready` and not `payments.err.no_iban`.

The constant body (from 1068a): `No bank account is set up for this payment request.` plus `\n`, `Content-Type: text/plain; charset=utf-8`, status 404. Every other refusal stays an empty 404 (existing tests assert `Body.Len() == 0`).

The fix codes are `bank` and `stripe`. Go only appends `fix=<code>` to the redirect; Python's allowlist decides whether a link shows. Go hands over the code, never a URL.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/hostweb/hostweb.go` | edit | `Flash.Fix`, `Back` appends `fix=` |
| `go/internal/payments/qrpng.go` | edit | `qrNoAccount(w)` helper, host PNG body, account check helper |
| `go/internal/payments/paylink_routes.go` | edit | guest PNG body |
| `go/internal/payments/requests.go` | edit | block `qr` without account; `fix=stripe` on not_ready |
| `go/internal/payments/i18n_keys.txt` | edit | add `payments.err.no_iban` |
| `go/internal/payments/i18n.json` | regenerate | by the script only |
| `go/internal/payments/qrpng_test.go`, `requests_test.go`, `paylink_routes_test.go`, `go/internal/hostweb/hostweb_test.go` | edit | tests |

No other file may change. Never edit `App/` in this brief.

## 4. Steps

Work from the repo root unless a command says `cd`.

1. **Flash fix field.** In `hostweb.go` add `Fix string` to `type Flash struct` (after `Count int`). In `Back`, directly after
```go
	if err.Text != "" {
		query = append(query, "err="+pyQuote(err.Text))
	}
```
add
```go
	if err.Fix != "" {
		query = append(query, "fix="+pyQuote(err.Fix))
	}
```
(order matches Python: `err` then `fix`). Add a case to `hostweb_test.go` asserting `Back` with `Flash{Text: "x", Fix: "bank"}` redirects to `/payments?err=x&fix=bank`. Command: `cd go && go test ./internal/hostweb/ 2>&1 | tail -30`. Expect `ok`.

2. **Helpers.** In `qrpng.go` add (below `qrPNGBytes`):
```go
// qrNoAccountBody is payment_request.NO_ACCOUNT_BODY in Python.
const qrNoAccountBody = "No bank account is set up for this payment request.\n"

func qrNoAccount(w http.ResponseWriter) {
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	w.WriteHeader(http.StatusNotFound)
	_, _ = io.WriteString(w, qrNoAccountBody)
}

// hasBankAccount is payment_request.has_bank_account.
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
Add `"io"` to the imports if missing. Command: `cd go && go build ./... 2>&1 | tail -30`. Expect no output.

3. **PNG routes.** In both anchors for `errors.Is(err, errQRAccount)` replace `w.WriteHeader(http.StatusNotFound)` with `qrNoAccount(w)`. Command: `grep -n "qrNoAccount(w)" go/internal/payments/qrpng.go go/internal/payments/paylink_routes.go`. Expect one line in each file.

4. **Block the create.** In `requests.go`, directly after the `requestRails[rail]` check (anchor above) and before `stamp := stampAt(at)` add:
```go
		if rail == "qr" {
			ok, err := hasBankAccount(ctx, pool, owner)
			if err != nil {
				requestFail(w, err)
				return
			}
			if !ok {
				f := requestFlash(lang, "payments.err.no_iban")
				f.Fix = "bank"
				hostweb.Back(w, r, "/payments/new", hostweb.Flash{}, f)
				return
			}
		}
```
Note the redirect target is `/payments/new`, as in Python (the Go handler's other errors go to `/payments`, unchanged). In `flashErr` (~line 204) keep its signature; for the `not_ready` case at ~253 replace `flashErr("payments.err.not_ready")` with
```go
				f := requestFlash(lang, "payments.err.not_ready")
				f.Fix = "stripe"
				hostweb.Back(w, r, "/payments", hostweb.Flash{}, f)
```
Command: `cd go && go build ./... 2>&1 | tail -30`. Expect no output.

5. **Copy.** Add `payments.err.no_iban` to `go/internal/payments/i18n_keys.txt` (after `payments.err.not_ready`). From `App/`: `python3 scripts/go_host_i18n.py 2>&1 | tail -5`, then `python3 scripts/go_host_i18n.py --check 2>&1 | tail -5`. Expect the check to exit 0. Run `.venv/bin/python -m pytest tests/test_go_host_i18n.py -q --tb=short -x 2>&1 | tail -30`. Expect green.

6. **Go tests.** Extend the existing database tests (they need the test pool like `TestQRPNGDatabase`; if `testPool` skips without a database, run with the same env CI uses and report whether it ran; a skip is not a pass):
 - `qrpng_test.go` `TestQRPNGDatabase`: in the final block (iban and bank_account NULL) assert 404, `Content-Type` `text/plain; charset=utf-8`, body equals `qrNoAccountBody`; the existing empty-404 cases stay.
 - `paylink_routes_test.go` `TestGuestQRPNGDatabase`: same for a valid token with no account; wrong token stays an empty 404.
 - `requests_test.go`: POST `/payments/requests/new` with `rail=qr` and an owner with no account redirects (303) to a Location starting `/payments/new?err=` and containing `&fix=bank`, and inserts no row; with an account it still inserts. `rail=card` with no account still inserts.
Command: `cd go && go test ./internal/payments/ ./internal/hostweb/ 2>&1 | tail -30`. Then `cd go && go vet ./internal/payments/ ./internal/hostweb/ 2>&1 | tail -30` and `cd go && go test ./... 2>&1 | tail -30` (the owner asked for the touched package; `./...` here is the package set of `go/`, run it once, expect `ok` on every line).

7. **Parity check against Python.** From `App/`: `.venv/bin/python -m pytest tests/test_payment_rails.py -q --tb=short -x 2>&1 | tail -30` (1068a tests). Confirm by eye the body string in `qrpng.go` equals `payment_request.NO_ACCOUNT_BODY`: `grep -n "No bank account is set up" ../go/internal/payments/qrpng.go app/payment_request.py`. Expect the same sentence in both.

## 5. Do not touch

`App/`, Caddy and `UBYHOST_GO_PATHS`, `go.mod`/`go.sum` (no dependency), webhook, Connect and push code, the guest QR path logic beyond the one status line. AGENTS.md rules 4, 8.

## 6. Commands

As in the steps. Go: `cd go && go test ./internal/payments/ ./internal/hostweb/`, then once `go test ./...`.

## 7. Acceptance

- [ ] `go test ./...` green; the database tests ran (not skipped) or the report says exactly why they could not.
- [ ] Go no-account PNG (host and guest): 404, `text/plain; charset=utf-8`, body equals the Python body byte for byte.
- [ ] Go POST `rail=qr` without account: 303 to `/payments/new?err=...&fix=bank`, no row; Python does the same (1068a test).
- [ ] `python3 scripts/go_host_i18n.py --check` exits 0.
- [ ] Other 404 refusals still have an empty body.

## 8. Stop and ask

Stop and report `blocked` if an anchor is missing, `go build` fails twice, the database tests cannot run and the owner has not said CI is enough, a new dependency seems needed, a file outside §3 needs a change, or you reach 25 tool calls.

## 9. Report

`docs/tasks/1068b-report.md` (600 tokens at most), `Status: review`: files changed, each command with its last 5 lines, §7 ticked, deviations.

## Risk list (for the reviewer)

`go/internal/payments/requests.go` (production create route), `hostweb.go` `Back` (used by every Go host route; the new `fix=` only appears when `Fix` is set), `qrpng.go`, `paylink_routes.go` (public guest PNG).

## Owner steps

1. After both PRs merge, deploy once (the owner does production deploys). The Go change takes effect with the Go container; no Caddy or `UBYHOST_GO_PATHS` change.
2. Check on production: open `/payments/new` with a test owner that has no bank account and confirm the Bank QR option is disabled with "Add bank account (1 min)".
