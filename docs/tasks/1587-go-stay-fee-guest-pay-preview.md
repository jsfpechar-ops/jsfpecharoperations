# 1587: Go stay fees: the guest-pay preview (live sample QR) for `POST /stay-fees/{apartment_id}/guest-pay-preview`

Status: review
Depends on: 1330 | Base commit: current tip of the working branch | Branch: task/1587-go-stay-fee-guest-pay-preview
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1587 step k` (`k` is the step number). Never create a branch, never push, never open a PR (the line `Branch:` above is only the name the owner may use later). Acceptance checks use `git log --oneline --grep='^1587 step'` and `git show --stat <commit>`, never a fixed base commit.

## 1. Objective

Add `POST /stay-fees/{apartment_id}/guest-pay-preview` (`guest_pay_preview`) to `go/internal/web/stayfees`: the JSON answer `{ok, invalid, account, qr}` the host form uses to show a sample QR of the account the host is typing. Nothing is saved. Dormant until the owner routes the path.

## 2. Context

Rules (AGENTS.md): 1 filing correctness is not touched (the sample QR is never a filing); 2 privacy: no new personal-data field, no new retention line, no outbound request (the QR is drawn locally); 3 fixtures are made up (`example` data, public sample IBANs); 4 no new dependency (`github.com/skip2/go-qrcode` is already in `go.mod`, used by `go/internal/payments`); 5 plain PostgreSQL through `pgxpool`, the Python SQL with `$n` placeholders, no schema change; 6 light mode (no page here, JSON only); 11 Go first (this brief is the Go port; no file under `App/app/` changes).

**PR text (hard rule 2):** no new outbound request, no new personal-data field. The answer holds only what the host typed and the account already on file for the host's own operator.

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1587-files/<repo path>.txt`. Step 1 copies them; never retype or edit them.

| sha256 | file | action | lines |
|---|---|---|---|
| `dfefe2c6dc03af099800bc1528102008436df8f1b5f2edb3e1da8e4ba2708fa2` | `go/cmd/ubyhost-web/register_web_stayfees_guestpay.go` | create | 23 |
| `b0397adcbc81ddfab66ddc64710c7cd13bf4de691b51eff2839affb9eef09ddb` | `go/cmd/ubyhost-web/register_web_stayfees_guestpay_test.go` | create | 16 |
| `d18412c75558326a1cac5e898a060c17741b54307de03258c01b827bf5c0f02f` | `go/internal/web/stayfees/guestpay_preview.go` | create | 233 |
| `9f75f99c485513c0ec651dd7cb2558c5d6134c953fe8455ab67ec4c0abc59c64` | `go/internal/web/stayfees/guestpay_preview_test.go` | create | 269 |

**How the code is built.** `guestpay_preview.go` holds `GuestPayPreviewHandler` and the helpers. It reuses `deps.enter` (CSRF, then login, exactly like the other Go stay-fee POSTs) and `pathID` from `handlers.go`, and `NormaliseAccount`, `FormatIBAN` and `SPAYD` from `go/internal/stayfee`. It is registered from a new `register_web_stayfees_guestpay.go` (not from `Routes`, so the shared files stay untouched). The test file builds its own mux with the handler and uses the helpers of `actions_test.go` (`testPool`, `seed`, `loadGolden`, `csrfPair`, `sessionFor`, `goldenEnv`).

**Parity notes (Python `App/app/routes/stay_fees.py` unless named):**

| Python | Go |
|---|---|
| `guest_pay_preview` 134-163 | `GuestPayPreviewHandler` |
| `stay_fee_guest_pay_on` 262-264 (reads `UBYHOST_STAY_FEE_GUEST_PAY`, "on" after trim and lower) | `guestPayOn` (through `getenv`) |
| `_entity_payment_account` 419-429 | `guestpayEntityAccount` |
| `_resolved_operator_account` 486-506 | `guestpayResolve` |
| `guest_pay_operator_context` 509-569 | `guestpayContext`, `guestpaySampleAmount` |
| `payments.qr_data_uri`, `qr_png_bytes` (App/app/payments.py 153-163) | `guestpayQRDataURI`, `guestpayPNG` |
| `access.apartment` (App/app/access.py 66-70) | `guestpayLoad` (owner scoped) |

Details that are easy to get wrong and are tested: the order is login/CSRF, then the property; a property that is not the host's, a missing one, an id outside int64, and the switch off all answer `404 {"ok":false}`; the answer is compact JSON in the order `ok, invalid, account, qr` (Starlette writes no spaces; HTML characters are not escaped); a typed account (trimmed) wins over the operator's; a typed account that does not validate gives `ok:false, invalid:true, account:"", qr:""` even when the operator has an account; nothing typed and no account on file gives `ok:false, invalid:false`; the operator's stored IBAN wins over its Czech account, and a stored IBAN is shown and used as stored (not validated), while a stored Czech account that does not validate is shown and used raw (as Python does); the sample amount is the typed `rate`, else the property's `stay_fee_rate_czk`, `0` or empty meaning 50, then clamped to 1..50 (a text, decimal or zero rate counts as no rate; `1_0` is 10 and `+10` is 10 as in Python's `int()`; a negative rate becomes 1; a huge rate becomes 50); the SPAYD message is `Stay fee sample` (uppercased by `ASCIIUpper`) and the variable symbol is `1234567890`.

**The QR image.** Python builds `preview_qr` with `qrcode` (error correction M, `box_size=6`, `border=4`, `fit=True`); Go uses `qrcode.New(payload, qrcode.Medium)` and `PNG(-6)` (6 px modules, 4-module border), the same settings as `go/internal/payments/qrpng.go`. The PNG **bytes differ** from Python's (the two libraries choose a different mask and compress differently), but the picture has the same size (246 x 246 px for these payloads, version 4) and a scanner reads the same SPAYD text from both. The brief writer checked this with OpenCV's QR reader on Python's and Go's PNGs of three payloads (a Czech IBAN, a second Czech IBAN, a foreign IBAN): the decoded text was identical, e.g. `SPD*1.0*ACC:CZ6508000000192000145399*AM:50.00*CC:CZK*X-VS:1234567890*MSG:STAY FEE SAMPLE`. The test therefore checks the data-URI prefix, that the PNG decodes and is 246 x 246, not equal bytes.

**Known differences from Python, shared by every Go web area (not fixed here):** a non-integer `apartment_id` answers `422 {"detail":"Unprocessable Entity"}` (as FastAPI) but after the login check, as in the other Go stay-fee POSTs; `HEAD`/other methods are answered by the mux (405). Python's `int()` also accepts non-ASCII digits in `rate` (Arabic-Indic and the like); Go reads only ASCII, a rate in other digits counts as no rate. Python escapes nothing in JSON; Go matches that for HTML characters, but writes U+2028 and U+2029 escaped (cannot occur in a bank account).

**Paths that become fully served by Go:** `/stay-fees/*/guest-pay-preview` (POST). **Goes live on deploy if** that path is already routed to Go (assumed not). The page that calls it (`/stay-fees/{id}` and the property form) stays on Python.

**Anchors that must exist verbatim** (step 0).

**Verified by the brief writer** (in a throwaway worktree of `go-wave3` with only this brief applied, sidecars copied as step 1 does): see section 10.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/cmd/ubyhost-web/register_web_stayfees_guestpay.go` | create | registers the route |
| `go/cmd/ubyhost-web/register_web_stayfees_guestpay_test.go` | create | route registration test |
| `go/internal/web/stayfees/guestpay_preview.go` | create | handler and helpers |
| `go/internal/web/stayfees/guestpay_preview_test.go` | create | route tests on PostgreSQL |
| `docs/tasks/1587-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1587-report.md` | create | the report (section 9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (section 8).
   - `git branch --show-current | tail -1` prints the branch you were started on (not `main`).
   - `grep -cF "async def guest_pay_preview(apartment_id: int, request: Request):" App/app/routes/stay_fees.py | tail -1` prints `1`.
   - `grep -cF "def guest_pay_operator_context(" App/app/routes/stay_fees.py | tail -1` prints `1`.
   - `grep -cF "def _resolved_operator_account(entity, draft_account: str = \"\") -> tuple[str, str]:" App/app/routes/stay_fees.py | tail -1` prints `1`.
   - `grep -cF "def qr_data_uri(payload: str) -> str:" App/app/payments.py | tail -1` prints `1`.
   - `grep -cF "func (d deps) enter(" go/internal/web/stayfees/handlers.go | tail -1` prints `1`.
   - `grep -cF "func pathID(" go/internal/web/stayfees/handlers.go | tail -1` prints `1`.
   - `grep -cF "func testPool(" go/internal/web/stayfees/actions_test.go | tail -1` prints `1`.
   - `grep -cF "func csrfPair(" go/internal/web/stayfees/actions_test.go | tail -1` prints `1`.
   - `grep -cF "func NormaliseAccount(" go/internal/stayfee/report.go | tail -1` prints `1`.
   - `grep -cF "skip2/go-qrcode" go/go.mod | tail -1` prints `1`.
   - `ls go/internal/web/stayfees/guestpay_preview.go 2>&1 | tail -1` says "No such file" (nothing of this brief exists yet).
   - `find docs/tasks/1587-files -name '*.txt' | wc -l | tail -1` prints `4`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1587-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -5
   dfefe2c6dc03af099800bc1528102008436df8f1b5f2edb3e1da8e4ba2708fa2  go/cmd/ubyhost-web/register_web_stayfees_guestpay.go
   b0397adcbc81ddfab66ddc64710c7cd13bf4de691b51eff2839affb9eef09ddb  go/cmd/ubyhost-web/register_web_stayfees_guestpay_test.go
   d18412c75558326a1cac5e898a060c17741b54307de03258c01b827bf5c0f02f  go/internal/web/stayfees/guestpay_preview.go
   9f75f99c485513c0ec651dd7cb2558c5d6134c953fe8455ab67ec4c0abc59c64  go/internal/web/stayfees/guestpay_preview_test.go
   EOF
   ```

   Every line must end with `: OK`. Then commit "1587 step 1".

2. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/web/stayfees cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/stayfees/... ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (section 8). Nothing changed, so no commit.

3. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one on port 55587 (as root; `pg_ctl` refuses root, so it runs as `postgres`). Skip the start if it is running (`su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55587/data status' | tail -1` says `server is running`):

   ```bash
   mkdir -p /var/tmp/pg55587 && chown postgres /var/tmp/pg55587 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg55587/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55587/data -o "-p 55587 -k /var/tmp/pg55587" -l /var/tmp/pg55587/log start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Then use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55587/postgres`. No PostgreSQL 16 binaries at that path: write "CI only" in the report and STOP before step 4.

4. Run the tests of this brief on PostgreSQL (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55587/postgres go test ./internal/web/stayfees/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30
   ```

   Expected: two `ok` lines (packages `.../internal/web/stayfees` and `.../cmd/ubyhost-web`); the golden test of brief 1330 (`TestActionsMatchPython`) is part of the first and must stay green. Then show that the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55587/postgres go test ./internal/web/stayfees/ ./cmd/ubyhost-web/ -count=1 -v -run '^TestGuestPayPreview$|^TestGuestPayParseRate$|^TestStayFeesGuestPayRouteRegistered$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
   ```

   Expected: one `--- PASS` line for each of 3 tests and two final `ok` lines; no `--- SKIP`, no `--- FAIL`:

   --- PASS: TestGuestPayPreview (0.NNs)
   --- PASS: TestGuestPayParseRate (0.00s)
   --- PASS: TestStayFeesGuestPayRouteRegistered (0.00s)

5. Write the report (section 9), set `Status: review` in this file and commit "1587 step 5". Do not open a PR (one big PR mode).

## 5. Do not touch

`App/` (the Python route stays the live one), `go/internal/web/stayfees/handlers.go`, `i18n.json`, `register_web_stayfees.go` and every other existing file, `docs/ENVIRONMENT.md`, Caddy and compose files, `UBYHOST_GO_PATHS`. No secret or guest datum in a file or a log (the test data is made up), nothing pushed to `main`.

## 6. Commands

Exactly the commands of section 4 (steps 2 and 4). Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (it must print no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 4 files.
- [ ] The format, build and vet step printed nothing.
- [ ] The test step printed `ok` for both packages and each of the 3 named tests printed `--- PASS` (none `SKIP`, none `FAIL`) on PostgreSQL.
- [ ] `git show --stat --format=%s $(git log --format=%h --grep='^1587 step') | tail -40` lists only the paths of section 3.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or Python application file changed; nothing was pushed to `main`.
- [ ] UI: not applicable (JSON only, dormant; rules 7 and 10 do not apply). The page that calls the route stays on Python.

## 8. Stop and ask

Stop, and write the report, if: an anchor, a hash or a file count of step 0 or step 1 is not as stated; a test fails twice (read the last 30 lines, fix nothing in the sidecars yourself: report); you reach 25 tool calls or about 50k tokens (write the report as `blocked`); a new dependency seems needed; a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1587-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has: 1. the files changed (`git diff --stat`); 2. each command with the last 5 lines of its output; 3. section 7 ticked; 4. deviations; 5. questions; 6. owner steps left.

## 10. Verified by the brief writer

In a throwaway worktree of `go-wave3` with this brief's step 1 applied exactly: `gofmt -l` printed nothing, `go build ./...` and `go vet ./internal/web/stayfees/... ./cmd/...` were silent, and `go test ./internal/web/stayfees/... ./cmd/ubyhost-web/... -count=1` passed on PostgreSQL 16 (port 55587) with the golden test of 1330 green. The tests cover: a typed Czech account and a typed IBAN (spaced, lower case), the exact JSON text, a typed account that is invalid (also with an account on file) and a bad-checksum IBAN, an operator with only a Czech account, an operator with an IBAN and a different Czech account (IBAN wins), no operator, rate variants (text, decimal, `0`, `50`, huge, `1_0`, `+10`, `-3`, typed rate beats the property's), a foreign, missing and out-of-range property, the switch off, unset and ` ON `, another host, signed out (303 to `/login`), no CSRF token, a text id (422), and `GET` (405). The QR was compared with Python's `qrcode` 8.2 output as described in section 2: same size and same decoded SPAYD text, different PNG bytes.

## Risk list (for the reviewer)

Read the diff of `guestpay_preview.go`: `guestpayLoad` (owner scoped, the operator row is read by the property's own `legal_entity_id` as Python does), `guestpayResolve` (typed beats stored; stored IBAN used unvalidated as in Python), `guestpayParseRate` and `guestpaySampleAmount` (Python `int()` and the 1..50 clamp), the JSON writer (compact, no HTML escaping).

## Owner steps

None: nothing is switched on. The path switch is `/stay-fees/*/guest-pay-preview` (POST) in `UBYHOST_GO_PATHS`, together with the other stay-fee paths and only after the guest-pay switch `UBYHOST_STAY_FEE_GUEST_PAY` is decided.
