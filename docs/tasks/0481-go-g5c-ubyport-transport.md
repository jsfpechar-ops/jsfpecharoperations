# 0481: Go G5c: UbyPort NTLM transport, Submit and the submission claim in Go
Status: todo
Depends on: 0480 (#635) | Base commit: main | Branch: claude/project-thread-n5om1z
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 90k tokens
## 1. Objective
Plan v4 step 17 (G5), third slice, rule 1 (filing correctness). Go can post a SOAP envelope to UbyPort with NTLM, map every failure to the same error kind as Python, run one `ZapisUbytovane` end to end (build, post, parse, count check), and take and release the `submission_claim` lease exactly as Python does. Nothing calls this code yet: no wiring into `go/cmd/`, no job kind, nothing changes in production. Recording outcomes in `guest`/`submission` is G5d.
## 2. Context
- Python source of truth: `App/app/ubyport/client.py` (whole file, 246 lines) and `App/app/reporting.py` lines 1329-1377 (`claim_sendable`, `release_sendable_claim`), `SUBMISSION_CLAIM_TTL_SECONDS = 5 * 60` (line 59), `db.lock_key` = `SELECT pg_advisory_xact_lock(hashtext($1), $2)` (App/app/db.py line 957). Go must take the same advisory key (`'guest'`, guest id as int32) so Python and Go writers serialise against each other.
- Go to reuse: `go/internal/ubyport/request.go` (`BuildZapisUbytovane`), `response.go` (`ParseFault`, `ParseZapisResponse`, `ZapisResult`). DB test pattern: `testPool` in `go/internal/payments/sweep_test.go` (skips without `UBYHOST_TEST_DATABASE_URL`; CI sets it).
- New dependency `github.com/Azure/go-ntlmssp v0.1.1` (MIT, no dependencies of its own; decision line 2026-11-01 in decisions.md). Use `ntlmssp.Negotiator{RoundTripper: inner}` with `req.SetBasicAuth(user, password)`; leave `AllowBasicAuth` false so the password is never sent as Basic.
- **Traps:**
  - The Negotiator hides transport errors: when a later handshake round trip fails it returns the first 401 response and no error. That 401 must **not** become an auth error, because the final request carried the envelope and may have been filed. Wrap `inner` in a small RoundTripper that records every error it sees. After the call: any recorded error that is not a failed dial (`*net.OpError` with `Op == "dial"`, or a dial timeout) is `ErrOutcomeUnknown`, whatever response came back; only dial errors with nothing else is `ErrTransport` ("Could not reach UbyPort at ..."). This mirrors `_definitely_not_sent`; a TLS error after connect is outcome unknown.
  - No NTLM when `useNTLM` is false or the username is empty (plain POST). Login form: `DOMAIN\user`; add `domain + "\\"` only when the username has no backslash. Default domain `EXRESORTMV`.
  - No redirects followed (`CheckRedirect` returns `http.ErrUseLastResponse`). Headers exactly: `Content-Type: text/xml; charset=utf-8`, `SOAPAction: <ACTION_PREFIX><method>` (copy the prefix from `App/app/ubyport/soap.py`), `Accept: text/xml`. Timeouts: dial 60 s, response header 60 s, whole client 180 s (three handshake legs). `verifyTLS=false` sets `InsecureSkipVerify`; default true.
  - Status mapping in Python order: 401 auth error; 3xx transport error; SOAP fault (`ParseFault`) transport error; >=500 outcome unknown; >=400 transport error; else the body. Error texts as in Python (body cut to 400 characters).
  - `Submit`: empty guest list is a plain error before any network call; outcome-unknown errors carry the request XML; an unparseable answer and a record count different from the guest count are outcome unknown with the request XML. Log only element names and sizes, never values (copy the Python log line).
  - WSA header flag is read per call from `UBYHOST_SOAP_WSA_HEADER` (`"0"`, `"false"`, `"no"` or unset mean off).
  - Claim: one transaction; delete claims older than the TTL; lock guest ids ascending; per pair re-read `submit_state, archived_at, manual_filed_at` and skip the pair when the row is gone, archived, filed by hand or its state differs from the state the caller read; `INSERT ... ON CONFLICT (guest_id) DO NOTHING`; claimed = rows affected 1. Token: 18 random bytes, URL-safe base64 without padding (same as `secrets.token_urlsafe(18)`). Keep input order in the result.
## 3. Files
New: `go/internal/ubyport/client.go` (+ `client_test.go`), `go/internal/ubyport/claim.go` (+ `claim_test.go`). Changed: `go/go.mod`, `go/go.sum` (only the ntlmssp lines). Write `docs/tasks/0481-report.md`.
## 4. Steps
1. `cd go && go get github.com/Azure/go-ntlmssp@v0.1.1 && go mod tidy`; `git diff go/go.mod` must add only that one line.
2. `client.go`: `type Client struct` (Endpoint, Username, Password, Domain, AuthCode, UseNTLM, VerifyTLS, HTTP *http.Client for tests), `NewClient(...)`, error values `ErrTransport`, `ErrOutcomeUnknown`, `ErrAuth` (`errors.Is` works; outcome-unknown error type exposes `RequestXML`), `Post(ctx, method, envelope) ([]byte, error)`, `Submit(ctx, header, guests) (SubmitResult, error)` with the Python `SubmissionResult` fields.
3. `client_test.go` with `httptest`: plain 200 ok; 401 auth; 302 not followed; SOAP fault 200 and 500; 500 outcome unknown; 404 transport; dial to a closed port is transport; server that hangs after reading the body (short client timeout) is outcome unknown; NTLM: a fake server that answers 401 `WWW-Authenticate: NTLM`, then a type-2 challenge, then checks a type-3 `Authorization` and the body arrive and answers 200 (build the challenge bytes by hand or take them from the ntlmssp tests); same server but it closes the connection on the type-3 leg: must be outcome unknown, not auth; `Submit` with a canned accepted response gives the parsed result; a response with one record for two guests is outcome unknown carrying the request XML; empty guests errors without a request.
4. `claim.go`: `ClaimSendable(ctx, pool, pairs []ClaimPair) (token string, claimed []ClaimPair, err error)` where `ClaimPair` has `GuestID int64`, `SubmitState string` (plus an opaque field the caller keeps); `ReleaseSendableClaim(ctx, pool, token) error`.
5. `claim_test.go` (DB, via a `testPool` copy): claims a pending guest; second claim of the same guest gets nothing; stale claim older than 300 s is replaced; guest whose state changed, archived, or `manual_filed_at` set is skipped; release frees the guest. Insert only the columns the baseline marks `NOT NULL` without defaults.
## 5. Do not touch
Every file under `App/`, `go/cmd/`, `go/internal/jobs`, `go/internal/ubyport/request*.go`, `response*.go`, `codes*.go`, golden files, compose, CI.
## 6. Commands
- From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/ubyport/ -count=1 2>&1 | tail -30`. The claim tests skip locally without `UBYHOST_TEST_DATABASE_URL`; CI runs them. Say which ran in the report.
- From the repo root: `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
All tests pass; the NTLM test proves a type-3 message and the body reached the server; the closed-connection test proves a late failure is outcome unknown. `git diff --stat origin/main` lists only section 3 files, this brief, `docs/context/decisions.md` and `docs/context/status.md`.
## 8. Stop and ask
Stop if ntlmssp cannot complete the fake handshake, or if matching Python needs a change under `App/`; report what failed.
## 9. Report
`docs/tasks/0481-report.md`: command tails, the diff stat, and any Python/Go difference you handled beyond section 2.
