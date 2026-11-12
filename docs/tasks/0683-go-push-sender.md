# 0683: Go Web Push sender, push test button, push job
Status: done (code on main and live in production, server on #928, 2026-11-12; closed in bulk by the orchestrator)
Depends on: 0678 (pushweb, on main) | Base commit: origin/main | Branch: task/0683-go-push-sender
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 90k tokens
## 1. Objective
Port the Web Push sender to Go with the standard library only (no new module): `App/app/webpush.py` (RFC 8291 aes128gcm + RFC 8292 VAPID ES256) into `go/internal/webpush`, and `App/app/push.py` delivery (`vapid_key`, `public_key`, `_subject`, `message`, `drain`, `send_test`, `_deliver`, `_settle`, `_retry`, `_finish`, `_drop`, constants) into `go/internal/pushsend`. Add `POST /account/push/test` to `go/internal/pushweb` and job kind `push` (Python scheduler `_job_push`, interval 1 min) to `goHandlers` in `go/cmd/ubyhost-web/main.go`. Production unchanged: Go container off.
## 2. Context
Python source of truth: `App/app/webpush.py` (all, 153 lines); `App/app/push.py` lines 1-110 and 254-460; `App/app/routes/push.py` `push_test` (115-128) plus its helpers `own_account`, `_error`, `_answer`, `_text`, `_body`, `TEST_MAX_PER_HOUR`; `App/app/rate_limit.py` `blocked`, `record`; `App/app/db.py` `decrypt_secret`/`encrypt_secret`/`get_setting` (which key: check, it may differ from the guest data keys); `App/app/scheduler.py` `_job_push` (386-398).
Go to reuse: `go/internal/pushweb` (route shape, own_account, error/answer JSON, catalog), `go/internal/secure` (Fernet/MultiFernet, key loaders), `go/internal/ubyport` `QueuePush` (the push_outbox row contract: do not change columns or params shape), `go/internal/jobs` handler type and how other kinds are registered. Rate limit: if Go already has a rate_limit helper (grep `rate_limit` in `go/internal`), reuse it; otherwise write a small private one in pushweb on the same table and keys as Python.
Crypto (stdlib only): `crypto/ecdh` P-256 for the ECDH, `crypto/hkdf` + `crypto/sha256`, `crypto/aes` + `crypto/cipher` GCM, `crypto/ecdsa` + raw r||s (32+32 bytes) JWT signature, base64url no padding. Same JWT claims, header, `aud` derivation, `exp` (check Python), TTL, `Content-Encoding: aes128gcm`, `Urgency`, `Authorization: vapid t=...,k=...` exactly as Python. Same PUSH_HOST_SUFFIXES endpoint check. HTTP: `http.Client` with a timeout equal to Python's; a network error is the TransportError branch (retry). VAPID key: read `web_push_vapid_private` from settings and decrypt like Python; if missing create it with the same INSERT ... ON CONFLICT DO NOTHING then re-read; the unreadable-key branch (delete outbox, subscriptions, setting) exactly as Python. Payload JSON: `json.dumps(..., ensure_ascii=False)` default separators (`", "`, `": "`), key order message keys then url, tag, lang. `message(kind, lang, params)`: port with host catalog keys added to `go/internal/pushsend/i18n_keys.txt`, then `App/scripts/go_host_i18n.py`, embed (copy the pushweb pattern).
## 3. Files
Create: `go/internal/webpush/webpush.go`, `webpush_test.go`; `go/internal/pushsend/pushsend.go`, `pushsend_test.go`, `i18n_keys.txt`, `i18n.json`; `App/scripts/webpush_golden.py` (writes `go/internal/webpush/testdata/golden.json`: fixed private keys, salt, local key, payload -> Python ciphertext body and headers; inject the fixed values by monkeypatching `os.urandom`/key generation, read webpush.py to see where). Edit: `go/internal/pushweb/pushweb.go` (+ tests, i18n keys if needed), `go/cmd/ubyhost-web/main.go` (route + job kind). Write `docs/tasks/0683-report.md`.
## 4. Steps
1. `webpush`: Encrypt (with injectable salt and ephemeral key for tests), VAPID header, Send(endpoint, p256dh, auth, payload, key, subject, ttl) -> (status, error).
2. Tests: RFC 8291 Appendix A test vector (exact bytes); golden file equality with Python output; decrypt round trip with a receiver key; JWT verifies with the public key and has Python's claims; endpoint suffix refusal; httptest server sees all headers.
3. `pushsend` + DB tests (skip without `UBYHOST_TEST_DATABASE_URL`, then 0 skipped with it), push service = httptest server (allow its host in tests through an injectable check, never in prod code paths): 201 -> sent + failures reset + last_sent_at; 404/410 -> device and its outbox dropped; 429/500 -> retry with RETRY_MINUTES, past the last -> failed; 400 -> failed, failures+1, fifth -> dropped; daily cap 12 -> capped; claim race (second claim updates 0 rows); transport error -> retry; undecryptable keys -> gone; VAPID key created once and reused; unreadable VAPID key branch; send_test unknown endpoint -> gone.
4. pushweb `/account/push/test`: signed out 401, rate limited 429, failed 502, ok JSON message, exactly Python's JSON.
5. Job kind `push` in `goHandlers`/`parseGoKinds`; disabled when Python's `enabled()` env says off (check `config.WEB_PUSH`).
6. Commit: `0683: Go Web Push sender, push test, push job`.
## 5. Do not touch
`App/` except the new golden script; templates, JS, CSS, CI, compose, Caddy, `go.mod`/`go.sum` (stdlib only; if a stdlib package is missing in the toolchain, stop), other Go packages except those listed.
## 6. Commands
- Own worktree: `git worktree add -b task/0683-go-push-sender /tmp/wt0683 origin/main`; work only there.
- Local Postgres (once): `pg_ctlcluster 16 main start; su postgres -c "psql -c \"ALTER USER postgres PASSWORD 'ubyhost'\""`.
- From `App/` (create `.venv` if missing: `python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt`): `.venv/bin/python scripts/webpush_golden.py && .venv/bin/python scripts/go_host_i18n.py --check | tail -5`.
- From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go build ./... && UBYHOST_TEST_DATABASE_URL=postgres://postgres:ubyhost@127.0.0.1/postgres go test ./internal/webpush/ ./internal/pushsend/ ./internal/pushweb/ ./cmd/... -count=1 2>&1 | tail -30`.
- From the repo root: `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
All listed tests pass with the DB URL set, 0 skipped; RFC vector and Python golden match byte for byte; vet/gofmt/build clean; no go.mod change.
## 8. Stop and ask
Stop if the Python lines no longer match, or a schema change or new dependency seems needed.
## 9. Report
`docs/tasks/0683-report.md`: command tails, `git diff --stat origin/main`, decisions beyond section 2, known differences from Python.
