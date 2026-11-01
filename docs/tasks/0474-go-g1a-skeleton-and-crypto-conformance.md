# 0474: Go G1a: service skeleton (healthz, metrics, goose check) and crypto conformance with the Python app
Status: blocked
Depends on: 0465 (goose, merged) | Base commit: main | Branch: task/0474-go-g1a
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 80k tokens
## 1. Objective
Start the Go port (plan v4 step 13, G1). Add a Go module in `go/` with a web binary that serves `/healthz` and `/metrics` and refuses to start while a goose file is pending. Add a package that reproduces, byte for byte, the three secrets the Python app writes: Fernet/MultiFernet data encryption, itsdangerous `URLSafeTimedSerializer` cookies, and the HMAC-SHA256 digests. Python generates the fixtures, and Go must decrypt and verify them and produce identical bytes. A wrong derivation would lock every user out, so this conformance comes before any route moves. Nothing is deployed in this brief: no Dockerfile, no compose service, no Caddy line (that is G1b).
## 2. Context
- Python oracle, read only:
  - `App/app/db.py` lines 2192–2260 (`_legacy_fernet`: key = urlsafe-b64(SHA-256(secret)); MultiFernet order = every `UBYHOST_DATA_KEYS` key, then the legacy key; the first encrypts).
  - `App/app/auth.py` lines 56–62 and 828 (`URLSafeTimedSerializer(secret, salt=...)` with salts `ubyhost-session`, `ubyhost-2fa-pending`, `ubyhost-guest-pin`), line 88 (`recovery_code_hash`) and line 843 (`pin_fingerprint`).
  - `App/app/invoice_links.py` line 20 (salt `ubyhost-invoice-download`).
  - `App/app/main.py` line 486 (`/healthz` JSON: `status` ok|degraded, `version`, `data_dir_writable`, `database_ok`).
  - `App/app/db.py` lines 1507 and 1547–1625 (goose file name `NNNNN_name.sql`, applied = newest `goose_db_version` row per `version_id` with `is_applied`, version 0 ignored).
- itsdangerous 2.2 (installed in `App/.venv`; read `itsdangerous/signer.py`, `timed.py`, `url_safe.py`, `_json.py`, `encoding.py` there if anything below is unclear):
  - Signer key = SHA-1(salt + "signer" + secret) (`django-concat`), MAC = HMAC-SHA1, separator `.`.
  - Payload = compact JSON (`separators=(",", ":")`, `ensure_ascii=False`, keys in insertion order). If `zlib.compress(json)` is shorter than `len(json) - 1`, the payload is the compressed bytes, prefixed with `.` after encoding.
  - Encoding = URL-safe base64 without padding.
  - Timestamp = base64 of the big-endian minimal bytes of `int(time)`.
  - Token = `payload.timestamp.signature`.
  - `loads` with `max_age` refuses an age above max_age.
- Fernet spec: version byte 0x80, 8-byte big-endian time, 16-byte IV, AES-128-CBC with PKCS7 (key bytes 16–31), HMAC-SHA256 (key bytes 0–15) over everything before it, URL-safe base64 with padding. In Python, `Fernet(key)._encrypt_from_parts(data, current_time, iv)` gives a deterministic token for the fixtures.
- Go 1.24 is installed locally (`go version`). The module proxy works. In CI the runner's preinstalled Go downloads the pinned toolchain through `toolchain go1.24.7` in `go.mod` (checksums verified by sum.golang.org), so no setup action is needed.
- Dependencies: the Go standard library plus `github.com/jackc/pgx/v5` v5.7.6 (PostgreSQL driver), nothing else. The decision line is in §4 step 9.
## 3. Files
New: `go/go.mod`, `go/go.sum`, `go/cmd/ubyhost-web/main.go`, `go/internal/secure/fernet.go`, `go/internal/secure/signer.go`, `go/internal/secure/digest.go`, `go/internal/secure/secure_test.go`, `go/internal/secure/testdata/fixtures.json`, `go/internal/schema/goose.go`, `go/internal/schema/goose_test.go`, `App/scripts/crypto_fixtures.py`, `App/tests/test_crypto_fixtures.py`. Edit: `.github/workflows/ci.yml` (one new job `go`), `docs/context/decisions.md` (one line), `docs/context/architecture.md` (one line, where code lives). Write `docs/tasks/0474-report.md`.
## 4. Steps
1. `go/go.mod`: `module github.com/jsfpechar-ops/jsfpecharoperations/go`, `go 1.24`, `toolchain go1.24.7`, require pgx v5.7.6 (`go get`, then `go mod tidy`).
2. `App/scripts/crypto_fixtures.py`: deterministic, test keys only, never reads `.env` or config. Inputs: secret `"fixture-secret-0123456789abcdef0123456789"` and two data keys from `Fernet.generate_key()` written once as literals in the script. Write `go/internal/secure/testdata/fixtures.json` (sorted keys, indent 2) with:
   - (a) `fernet`: for plaintexts `""`, `"Jana Nováková"`, 1,000 × `"x"` and bytes 0–255 (hex in JSON): token from key 1, from key 2, and from the legacy key of the secret, each with `current_time=1767225600` and IV = bytes 0..15.
   - (b) `multifernet`: the key list `[key1, key2, legacy]` and one token per key that MultiFernet must decrypt.
   - (c) `signer`: for each of the four salts, tokens of `{"uid":7,"rm":1}`, of a payload long enough to be compressed (a list of 200 small ints), and of a non-ASCII string. Each is signed at timestamp 1767225600 (monkeypatch `time.time`), stored with its expected loads result.
   - (d) `digest`: `recovery_code_hash("abcd-ef12")` and `pin_fingerprint("tok123", "4821")`. Compute them with the same `hmac.new` expressions inline. Do not import `app.auth`: it needs the app config.
   The script prints `fixtures written: N`. It is a dev tool and not run in production.
3. `App/tests/test_crypto_fixtures.py`: regenerate into a temp path and assert it equals the committed file, so the fixtures cannot drift from Python. Then decrypt and loads every committed token with the real `cryptography` and `itsdangerous` (`max_age=None`).
4. `go/internal/secure`:
   - `fernet.go`: `Fernet` encrypt (with injectable time and IV for tests), decrypt (TTL optional), `MultiFernet` (decrypt tries keys in order, encrypt uses the first), `LegacyKey(secret string) []byte`.
   - `signer.go`: `TimedSerializer{Secret, Salt}` with `Dumps(v any, now time.Time) (string, error)` and `Loads(token string, maxAge time.Duration, now time.Time, out any) error`, using exact itsdangerous semantics. JSON must match Python's compact output: marshal with `json.Encoder`, `SetEscapeHTML(false)`, then strip the trailing newline. Python dict order is insertion order, so tests use structs whose field order equals the fixture key order.
   - `digest.go`: `RecoveryCodeHash(secret, code)` (strip `-` and spaces, upper-case, as Python does) and `PinFingerprint(secret, token, pin)`.
   - Use the standard library only (`crypto/aes`, `crypto/cipher`, `crypto/hmac`, `crypto/sha1`, `crypto/sha256`, `compress/zlib`, `encoding/base64`). Compare MACs with `hmac.Equal`.
5. `secure_test.go`: load `testdata/fixtures.json`. For every case, Go decrypts or loads the Python token and gets the expected value. Go then encrypts or dumps the same input at the same time and IV and gets the identical token string. Python's zlib output must match byte for byte, so compress with `zlib.NewWriterLevel(w, zlib.DefaultCompression)`. If the compressed signer token differs only in its compressed bytes, stop (§8). Negative tests: one flipped byte fails, a wrong salt fails, and an expired max_age fails.
6. `go/internal/schema/goose.go`: `Files(dir string) ([]int, error)` (name rule `^(\d{5})_([a-z0-9_]+)\.sql$`; a bad name or duplicate version is an error) and `Pending(ctx, conn *pgx.Conn, dir string) ([]int, error)` with the same SQL as Python `goose_applied`; a missing table means everything is pending. `goose_test.go`: `Files` on a temp dir with good and bad names. `Pending` runs against `UBYHOST_TEST_DATABASE_URL` and skips when it is unset; it creates the goose table in a schema named `go_goose_test`, inserts rows, asserts the result, and drops the schema.
7. `go/cmd/ubyhost-web/main.go`:
   - Environment: `UBYHOST_DATABASE_URL` (required), `UBYHOST_GO_ADDR` (default `127.0.0.1:8081`), `UBYHOST_MIGRATIONS_DIR` (default `App/migrations_pg`).
   - On start, connect with a 10 s timeout and call `schema.Pending`. If it is not empty, log `goose files pending: [..]` and exit 1.
   - `GET /healthz` returns the same JSON keys as Python, with `version` set to `go-dev` and `data_dir_writable` true, and runs `SELECT 1` through a `pgxpool` with a 2 s timeout. It answers 200 when healthy and 503 otherwise.
   - `GET /metrics` returns `text/plain; version=0.0.4; charset=utf-8` with `ubyhost_go_up 1` and `ubyhost_go_http_requests_total{route="<pattern>",code="<n>"}` counters (a `sync.Mutex` map; route patterns only, never raw paths).
   - Any other path returns 404.
   - On SIGTERM, shut down gracefully within 10 s.
   - Log with `log/slog` to stdout and never log the database URL.
8. `.github/workflows/ci.yml`, new job `go` (runs-on like the others; Postgres service the same as `test-postgres`), with steps:
   - `actions/checkout` at the same pinned SHA as the other jobs.
   - `go version`.
   - In `go/`: `test -z "$(gofmt -l .)"`, `go vet ./...`, `go test ./... -count=1` with `UBYHOST_TEST_DATABASE_URL` set to the service.
   - `go build ./cmd/ubyhost-web`.
   Add `go` to whatever list makes jobs required, if ci.yml has one. Otherwise just add the job.
9. `docs/context/decisions.md`, append: `- 2026-11-01 | Go port G1: module go/, standard library plus jackc/pgx v5 only; crypto reimplemented on the standard library and proven byte-identical by Python-generated fixtures | owner (approvals waived 2026-10-31, plan v4 D-Go) | 0474`. In `architecture.md`, add one line for `go/`.
## 5. Do not touch
`App/app/`, `deploy/`, the Caddyfile, compose files, `App/migrations_pg/`, any existing CI job.
## 6. Commands
From `go/`: `gofmt -l . ; go vet ./... 2>&1 | tail -10; UBYHOST_TEST_DATABASE_URL=postgresql://postgres:ubyhost@127.0.0.1:5432/ubyhost_test go test ./... -count=1 2>&1 | tail -20; go build ./cmd/ubyhost-web && rm -f ubyhost-web`.
From `App/`: `.venv/bin/python scripts/crypto_fixtures.py && .venv/bin/python -m pytest tests/test_crypto_fixtures.py -q --tb=short 2>&1 | tail -5`.
Smoke: `UBYHOST_DATABASE_URL=postgresql://postgres:ubyhost@127.0.0.1:5432/ubyhost_test UBYHOST_MIGRATIONS_DIR=App/migrations_pg go run ./go/cmd/ubyhost-web &`, then `curl -s 127.0.0.1:8081/healthz; curl -s 127.0.0.1:8081/metrics | head -5`, then kill it. Run the apply first if goose files are pending: `cd App && UBYHOST_DATABASE_URL=... .venv/bin/python scripts/pg_schema.py apply --expect-database ubyhost_test`.
From the repo root: `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
Every Python fixture is decrypted or verified by Go, and every Go-made token equals the Python token string. Negative tests fail as they should. The pytest drift test passes. `gofmt` prints nothing. The `go` CI job is green. `/healthz` answers 200 on a current schema, and the binary exits 1 with a goose file pending.
## 8. Stop and ask
Stop if: Go cannot reproduce a Python token byte for byte (report which case and the first differing byte); a step needs a dependency other than pgx; a step needs a change in `App/app/`.
## 9. Report
`docs/tasks/0474-report.md`: the command tails, the fixture case count, the smoke curl output, and `git diff --stat origin/main`.
