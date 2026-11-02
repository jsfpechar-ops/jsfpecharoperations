# 0684: Go payment QR PNG
Status: todo
Depends on: owner decision 2026-11-02 (go-qrcode) | Base commit: origin/main | Branch: task/0684-go-payment-qr
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 70k tokens
## 1. Objective
Port `GET /payments/qr/{id}.png` (`App/app/routes/payments.py` `payment_request_qr_png`, ~222-236) to Go in `go/internal/payments` and register it in `go/cmd/ubyhost-web/main.go`. Off in production (Go container off).
## 2. Context
Python: `payment_request_qr_png`; `App/app/payment_request.py` `get` (93), `qr_payload` (158-175); `App/app/payments.py` `normalise_account` (109-125, with `_IBAN_RE`, `_ACCOUNT_RE`, `_iban_ok`, `_mod11_ok` above it), `ascii_upper` (132), `spayd` (140-150), `qr_png_bytes` (153-159); `access.owner_id`, `auth.require_login`.
Go to reuse: `go/internal/hostweb` `Login` (pass the real `w`; a nil host means the guard already wrote the redirect), the owner id the same way `go/internal/payments/requests.go` gets it. If `normalise_account` or SPAYD helpers already exist in Go (grep `mod11`, `IBAN`, `SPD*` in `go/internal`), reuse them.
QR: `github.com/skip2/go-qrcode` at exactly `v0.0.0-20200617195104-da1b6568686e` (owner decision in docs/context/decisions.md). `qrcode.New(payload, qrcode.Medium)`, `PNG(-6)` (negative size = 6 px per module, 4-module border built in) gives the same 270x270 image size as Python for a version 5 code. The bits differ from Python's (different mask/segmentation); that is accepted, both decode to the payload.
Rules: 404 with empty body when the row is missing, belongs to another owner (compare as Python does), rail is not `qr`, or `qr_payload` would raise (no legal_entity row, no iban and no bank_account, bad bank_account). `Content-Type: image/png`. `Decimal(amount):.2f` formatting: amount_czk is stored how? Check the column type and format with two decimals exactly as Python. `ascii_upper`: NFKD, drop combining marks, upper, then check lines 132-138 for the rest (character filter, limit) and port exactly; use `golang.org/x/text/unicode/norm` only if it is already in go.sum (it is an indirect dep: check), otherwise stop and ask.
## 3. Files
Create `go/internal/payments/qrpng.go`, `qrpng_test.go`. Edit `go/cmd/ubyhost-web/main.go` (one route `GET /payments/qr/{id}`: Go 1.22 mux cannot match `{id}.png`; register `GET /payments/qr/{file}` and accept only `<digits>.png`, anything else 404, because Python's other route `/payments/qr/{request_id}` (HTML page) stays in Python and Caddy decides which paths go to Go), `go/go.mod`, `go/go.sum`. Write `docs/tasks/0684-report.md`.
## 4. Steps
1. `go get github.com/skip2/go-qrcode@v0.0.0-20200617195104-da1b6568686e` from `go/`. 2. Port. 3. Unit tests (no DB): SPAYD string for an IBAN and for a Czech `prefix-number/bank` account (expected strings computed with Python: `cd App && .venv/bin/python -I -c "import sys; sys.path.insert(0,'.'); from app import payments; ..."` and hardcoded); `ascii_upper` with Czech diacritics and the 60 limit; PNG is 270x270 for a typical payload and starts with the PNG signature. 4. DB tests (skip without `UBYHOST_TEST_DATABASE_URL`; they run in CI, the local Postgres password cannot be reset here, do not try): signed out 303; other owner 404; rail `card` 404; no legal_entity 404; good row 200 image/png. 5. Commit `0684: Go payment QR PNG` with the trailers you were given.
## 5. Do not touch
`App/`, templates, CI, compose, Caddy, other Go packages except main.go.
## 6. Commands
Own worktree: `git worktree add -b task/0684-go-payment-qr /tmp/wt0684 origin/main` (copy this brief and docs/context/decisions.md's last line are already on the thread branch; you only need the brief path /home/claude/jsfpecharoperations/docs/tasks/0684-go-payment-qr-png.md). From `/tmp/wt0684/go`: `test -z "$(gofmt -l .)" && go vet ./... && go build ./... && go test ./internal/payments/ ./cmd/... -count=1 2>&1 | tail -20`. Root: `python3 scripts/context_lint.py | tail -1`.
## 7. Acceptance
Unit tests pass; DB tests compile; vet/gofmt/build clean; go.mod adds only go-qrcode.
## 8. Stop and ask
If any other new module would be needed.
## 9. Report
`docs/tasks/0684-report.md`: test tail, `git diff --stat origin/main`, known differences.
