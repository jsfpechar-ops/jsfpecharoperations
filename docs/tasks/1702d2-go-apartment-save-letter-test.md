# 1702d2: Go property settings 3d2: the police-letter connection test on save

Status: ready (exact-diff pass 2026-11-17: sidecars applied to a clean worktree of cce51d3 plus the 1702d-files sidecars (the post-1702d1 state), gofmt/build/vet clean, Go tests green on PostgreSQL 16 incl. `./internal/ubyport/...`, 0 skips; catalog regenerated with a stubbed `fastapi` import (no App/.venv in the scratch worktree); no Python file changes)
Decision 2026-11-17 (orchestrator, rule 2): **new outbound request on Go.** The Go UbyPort login test calls the same host Python already calls (the police UbyPort endpoint of `ubyport.EndpointFor`, through `ubyport.ClientFor`); no new destination. The PR must state that reason.
Depends on: 1702d1 (its step 7 committed) | Base commit: current tip of the working branch | Branch: task/1702d2-go-apartment-save-letter-test
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (this brief needs about 12)
Tier: A (fresh review of the full diff before merge, see the risk list at the end)

> **Outbound requests (rule 2):** this brief adds the Go connection test: TestDostupnosti, MaximalniDelkaSeznamu and DejMiCiselnik, read-only, to the same UbyPort host the filing path and Python use. Write that reason in the report (the PR copies it).

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1702d2 step k` (`k` is the step number) and `git add` only the paths the step names (never `-A`, never `.`). Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1702d2 step'`.

## 1. Objective

Replace the 1702d1 seam `"the police-letter connection test (brief 1702d2)"` in `apartmentUpdateNotPorted`: police-letter values saved with `uby_ws_password` typed in the same save run Python's `_run_connection_test` (`App/app/routes/admin.py` 3506-3549) once, then `onboarding.MarkTested` on `ok`, and answer `flash.apartments.letter_test_ok` / `flash.error.letter_test_failed` (`auth`) / `flash.error.letter_test_unreachable` at `path#ubyport` (admin.py 2585-2600). Python's "typed in this save" rule is kept exactly: a new login with an old password could lock the police account.

## 2. Context

Rules (AGENTS.md): 1 filing correctness: no existing filing code path changes (`client.go`, `request.go`, `response.go`, `sweep.go`, `submit.go` untouched; the new calls live in a new file and reuse `Post`, `buildEnvelope`, `xmlEscaper`, `ParseScalarResponse`, `ParseCiselnikResponse`, `ClientFor`); 2 privacy: no new field; the one new outbound request is above; 4 no new dependency; 5 every query owner-scoped where the row has an owner; 7/10 UX gate: **pending until 1705** (no template change; the route is dormant); 8 dormant (not in `UBYHOST_GO_PATHS`).

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1702d2-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Four files are replaced (step 0 checks their post-1702d1 hashes), three are created.

| sha256 after | file | action | lines |
|---|---|---|---|
| `574c38c956d42edcfa7b3777e263134b618dfc78e95e26b238b036c0ddb5b597` | `go/internal/web/properties/apartment_update.go` | replace | 849 |
| `aabbcfaf3f347877eeaf47992782c1f8742ae394dec382d2539869e312f173bf` | `go/internal/web/properties/apartment_update_test.go` | replace | 580 |
| `c4d112ad3737f2d1059c3aec5ece3b8a95a4d031a576b7ff4197533b22f6c04b` | `go/internal/web/properties/apartment_update_letter_test.go` | create | 187 |
| `7650448a6173154451f617650657cda5452dc4ceadd8657c768a10d87b7e3105` | `go/internal/web/properties/apartmentupdate/i18n.json` | replace | 32 |
| `21053750fb25b6e56c60966cc1779fbfbb7ae74116036757ecb51e439dfb0a16` | `go/internal/web/properties/apartmentupdate/i18n_keys.txt` | replace | 10 |
| `760090d73a288375fd680145b593b2b18844158414e8cf74f8f37bae81c5c2ff` | `go/internal/ubyport/readonly.go` | create | 157 |
| `e6fc80a89b2a4f7b3813b06e1400ad56daa18abfe15f0099b295747591ab4af4` | `go/internal/ubyport/readonly_test.go` | create | 161 |

**What changed (for the reviewer; the executor reads no Go file).**

- `ubyport/readonly.go` (new): `BuildSimpleCall` / `BuildDejMiCiselnik` (soap.py 134-151), `(*Client).TestAvailability` / `MaxBatchSize` / `CodeList` (client.py 190-210, each one `Post` with its own SOAPAction and `wsaHeaderOn()`, as `Submit`), `CodeListErrors = "Chyby"`, and `StoreErrorCodelist` = `codelists.store(KIND_ERRORS, rows)` (codelists.py 29-86: `_code_and_texts` and `_extra` for the error list only; DELETE then upserts in one transaction; rows without a code skipped).
- `apartment_update.go`: the seam and its header comment line are gone. `apartmentSaved` (after the save, the fee return and the `?saved=1` path, as Python): letter values without a password keep `letter_saved_untested`; with one, `apartmentConnectionTest` (new, 783-849): `ClientFor` on the reloaded owner-scoped row (`detailLoad`) with the data-key decrypt of `db.decrypt_secret`; TestAvailability then MaxBatchSize; on error audit `ubyport_connection_failed` (`apartment= endpoint= error=`), `ErrAuth` gives `auth`, every other error `unreachable`; on success audit `ubyport_connection_ok` with Python's `True`/`False`/`None` spelling, `apartmentVerifiedSQL` (mark_verified, owner-scoped), `privacy.ResolveAlert("ubyport_auth_failed:{id}")`, then the error code list stored best effort (`ubyport_codebook_refresh_failed` on failure). Then `onboarding.MarkTested` on `ok` and the three flash keys.
- `apartmentupdate/i18n_keys.txt` + `i18n.json`: three keys added (`flash.apartments.letter_test_ok`, `flash.error.letter_test_failed`, `flash.error.letter_test_unreachable`), generated by `App/scripts/go_host_i18n.py` from `host_i18n.py`/`host_vi_i18n.py` (cs/en/vi); no new copy.
- `apartment_update_test.go`: `TestApartmentUpdateNotPorted` drops the "letter connection test" case (now ported); gofmt realigned that map. New `apartment_update_letter_test.go` `TestApartmentUpdateLetterTest` (hand-written Locations and audit rows, httptest server via `UBYHOST_UBYPORT_ENV=mock` + `UBYHOST_MOCK_URL`, no NTLM, no network): ok (three SOAPActions in order, audit, verified set, setup tested, `ERR_CZE_112` stored), code list HTTP 400 after a passed test (still ok, audit row, a set verified time kept), 401 (one call, `auth`, nothing verified), closed port (`unreachable`), no password / no listed field (nothing sent). New `ubyport/readonly_test.go`: the four envelopes byte for byte as Python's builders print them, each call's SOAPAction and body, MaxBatchSize nil for `""`/`many`/`12.5`, 401 stays `ErrAuth`, `StoreErrorCodelist` on six rows (hand-derived from `_code_and_texts`/`_extra`; the `staty` list untouched).
- Accepted differences (put in the report): an unreadable XML answer to TestDostupnosti/MaximalniDelkaSeznamu is a 500 in Python (`ET.ParseError` is not caught) and `unreachable` in Go; `MaxBatchSize` reads with `strconv.Atoi`, so `1_0` or non-ASCII digits give `None` in the audit text where Python's `int()` reads them (audit text only); `errorSeverity` takes one Unicode `Nd` digit, Python's `isdigit` also takes a superscript digit; the verified/fetched time is the request time (`stamp(q.at)`), Python's `utcnow()` a moment later.

## 3. Files

| Path | Action |
|---|---|
| the seven files of the table above | replace (4) / create (3) |
| `docs/tasks/1702d2-files/**` | keep (sidecars, committed with this brief; do not edit) |
| `docs/tasks/1702d2-report.md` | create (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints the branch you were started on (not `main`).
   - `git log --oneline --grep='^1702d1 step 7' | wc -l | tail -1` prints `1`.
   - `find docs/tasks/1702d2-files -name '*.txt' | wc -l | tail -1` prints `7`.
   - `ls go/internal/ubyport/readonly.go go/internal/ubyport/readonly_test.go go/internal/web/properties/apartment_update_letter_test.go 2>&1 | grep -c 'No such file' | tail -1` prints `3`.
   - The four replaced files are exactly the ones the sidecars were built on (one call):

     ```bash
     sha256sum -c - <<'EOF0' 2>&1 | tail -5
     c0bee747d02e77cc3f8a315df5bc8fddd7aa6951f6ee9586f5f1887d655404cc  go/internal/web/properties/apartment_update.go
     fc4ace89bce70bbb44327aae1311b3d299ae586125fd27b15c7b6c57e2d3ced1  go/internal/web/properties/apartment_update_test.go
     e2406856a039c6c3ccc9fd02554b3d9751b2c07b6e1e6a90e5240e9135286594  go/internal/web/properties/apartmentupdate/i18n.json
     3e2dfa001a44cfe707fca4bb20e86af4f158d5d256cb677f327338981a5b1a6d  go/internal/web/properties/apartmentupdate/i18n_keys.txt
     EOF0
     ```

     Four lines ending `: OK`. A `FAILED` line: STOP, the orchestrator re-bases the sidecars.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1702d2-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF1' 2>&1 | tail -8
   574c38c956d42edcfa7b3777e263134b618dfc78e95e26b238b036c0ddb5b597  go/internal/web/properties/apartment_update.go
   aabbcfaf3f347877eeaf47992782c1f8742ae394dec382d2539869e312f173bf  go/internal/web/properties/apartment_update_test.go
   c4d112ad3737f2d1059c3aec5ece3b8a95a4d031a576b7ff4197533b22f6c04b  go/internal/web/properties/apartment_update_letter_test.go
   7650448a6173154451f617650657cda5452dc4ceadd8657c768a10d87b7e3105  go/internal/web/properties/apartmentupdate/i18n.json
   21053750fb25b6e56c60966cc1779fbfbb7ae74116036757ecb51e439dfb0a16  go/internal/web/properties/apartmentupdate/i18n_keys.txt
   760090d73a288375fd680145b593b2b18844158414e8cf74f8f37bae81c5c2ff  go/internal/ubyport/readonly.go
   e6fc80a89b2a4f7b3813b06e1400ad56daa18abfe15f0099b295747591ab4af4  go/internal/ubyport/readonly_test.go
   EOF1
   ```

   Seven lines ending `: OK`. Then commit (one call):

   ```bash
   git add go/internal/web/properties/apartment_update.go go/internal/web/properties/apartment_update_test.go go/internal/web/properties/apartment_update_letter_test.go go/internal/web/properties/apartmentupdate/i18n.json go/internal/web/properties/apartmentupdate/i18n_keys.txt go/internal/ubyport/readonly.go go/internal/ubyport/readonly_test.go && git commit -m "1702d2 step 1" 2>&1 | tail -2
   ```

2. Format, build and vet (one call, repo root):

   ```bash
   cd go && gofmt -l internal/web/properties internal/ubyport internal/palette cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/properties/... ./internal/ubyport/... ./internal/palette/... ./cmd/ubyhost-web/... 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (§8).

3. Python checks (repo root). No Python file changes; the catalog must be fresh and the 1702c1 golden too. If `App/.venv/bin/python` does not exist, write "Python checks: CI only (no App/.venv)" in the report and go to step 4. Else (one call):

   ```bash
   cd App && .venv/bin/python scripts/go_host_i18n.py --check 2>&1 | tail -3; echo "i18n exit $?"; .venv/bin/python -m pytest tests/test_go_apartment_update_golden.py tests/test_go_apartment_create_golden.py -q --tb=short -rs 2>&1 | tail -5
   ```

   Expected: no stale-file line, `i18n exit 0`, then `passed` with no `skipped`. A `stale` line: STOP (§8).

4. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (skip the start if `su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg56331/data status' | head -1` says `server is running`):

   ```bash
   mkdir -p /var/tmp/pg56331 && chown postgres /var/tmp/pg56331 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg56331/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg56331/data -o "-p 56331 -k /var/tmp/pg56331" -l /var/tmp/pg56331/log start' 2>&1 | tail -3
   ```

   Expected: `server started`. No PostgreSQL 16 binaries at that path: write "CI only" in the report and STOP before step 5.

5. Go tests on PostgreSQL (two calls, repo root; the ubyport package takes about 70 s, so give each call a 300 s timeout). First:

   ```bash
   cd go && export UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:56331/postgres && go test ./internal/web/properties/... ./internal/palette/... ./cmd/ubyhost-web/... ./internal/ubyport/... -count=1 2>&1 | tail -30; go test ./internal/web/properties/ ./internal/ubyport/ -count=1 -v -run '^(TestApartmentUpdate|TestReadOnly|TestStoreErrorCodelist)' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -16
   ```

   Expected: four `ok` lines; then `--- PASS` for `TestApartmentUpdateMatchesPython`, `TestApartmentUpdateNotPorted`, `TestApartmentUpdateRefusedDraft`, `TestApartmentUpdateSignatureFeeLetter`, `TestApartmentUpdateFeeReturn`, `TestApartmentUpdateHelpers`, `TestApartmentUpdateRegisterDoesNotTouchThePool`, `TestApartmentUpdateLetterTest`, `TestReadOnlyEnvelopesMatchPython`, `TestReadOnlyCallsSendTheirAction`, `TestReadOnlyCallsKeepTheErrorKinds`, `TestStoreErrorCodelist`, and two `ok`. Second (SKIP count):

   ```bash
   cd go && export UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:56331/postgres && go test ./internal/web/properties/... ./internal/palette/... ./internal/ubyport/... -count=1 -v 2>&1 | grep -c -- '--- SKIP' | tail -1
   ```

   Expected: `0`. A failure: run once more; a second failure: STOP (§8). Then stop the server if you started it: `su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg56331/data stop' 2>&1 | tail -2 && rm -rf /var/tmp/pg56331`.

6. UX gate: **pending until 1705.** No template changed; the route is dormant. Write in the report: "UX: no template change; the redirects land on the property page already ported (1701); screenshots in 1705". Nothing to commit.

7. Write the report (§9), set `Status: review` in this file, and commit (one call): `git add docs/tasks/1702d2-report.md docs/tasks/1702d2-go-apartment-save-letter-test.md && git commit -m "1702d2 step 7" 2>&1 | tail -2`.

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file; `App/app/`; every other file under `go/` (in particular `go/internal/ubyport/client.go`, `request.go`, `response.go`, `sweep.go`, `submit.go`: the filing path); no template, no other catalog; never regenerate `apartment_update_golden.json`.

## 6. Commands

Exactly the commands of §4 (steps 2, 3, 5). Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (no finding about this brief's files).

## 7. Acceptance

- [ ] Step 0: `1`, `7`, `3`, four `: OK`; step 1: seven `: OK`.
- [ ] Step 2 printed nothing.
- [ ] Step 3: `i18n exit 0`, `passed`, no `skipped`, or "CI only (no App/.venv)" in the report.
- [ ] Step 5: four `ok` lines, the twelve named tests `--- PASS`, SKIP count `0`.
- [ ] `git log --oneline --grep='^1702d2 step' | tail -5` lists steps 1 and 7; `git show --stat --format=%s $(git log --format=%h --grep='^1702d2 step') | tail -20` lists only the paths of §3.
- [ ] Nothing in `App/`, `UBYHOST_GO_PATHS` or the existing `go/internal/ubyport/*.go` files changed.

## 8. Stop and ask

An anchor, hash or count of steps 0-1 not as stated; a test fails twice (fix nothing in the sidecars: report); a stale catalog or golden; 25 tool calls or about 50k tokens (report as `blocked`); a file outside §3 needs a change; push, merge, secrets, SSH or deploy.

## 9. Report

`docs/tasks/1702d2-report.md` (500 tokens at most): the files (`git show --stat` as in §7); each command with its last 5 lines and the SKIP count; §7 ticked; deviations; the accepted differences of §2; the rule-2 reason ("the Go connection test sends three read-only calls to the UbyPort host Python and the Go filing path already use; no new destination"); "UX pending until 1705"; "1702e (wizard posts) is next".

## Risk list (for the reviewer)

Line numbers are of the sidecar files under `docs/tasks/1702d2-files/` (`go/internal/web/properties/apartment_update.go.txt` unless named).

- SOAP envelopes and host: `go/internal/ubyport/readonly.go.txt` 25-36 (`BuildSimpleCall`, `BuildDejMiCiselnik`: `nsMethod`, `xmlEscaper`, `buildEnvelope` reused) and 39-75 (each call one `Post` with `ActionPrefix+method`, `wsaHeaderOn()`); goldens `readonly_test.go.txt` 18-35 are Python's builder output pasted by hand. The host is only `ubyport.ClientFor` 802-803 (`EndpointFor`: mock / test / prod, the filing host; NTLM unless mock; `UBYHOST_UBYPORT_TIMEOUT`). No ZapisUbytovane is reachable from this code.
- Seam: the letter-with-password refusal (old 224-226) is gone; every other `notPorted` branch unchanged and still answers before anything is written. The test runs only after the save, the fee return and the `?saved=1` path (702-728), only with a listed letter field and a typed `uby_ws_password` (Python's rule; test "no password / no listed field" sends nothing).
- Queries and scoping: the row is the owner-scoped `detailLoad` of `apartmentSaved` (639); `apartmentVerifiedSQL` 778-781 adds `owner_user_id IS NOT DISTINCT FROM` the workspace and keeps `ubyport_verified_at IS NULL` (mark_verified fills once; test "kept"). `ResolveAlert` 834 is the key the save already resolves. Audits through `s.audit` (actor, owner, impersonator as every audit of this route).
- `codelists.store` write: `readonly.go.txt` 134-157 replaces the global `chyby` list (no owner column; Python does the same) in one transaction; other kinds untouched (test `staty` row). Called only after a passed test, best effort (843-847: a failure audits `ubyport_codebook_refresh_failed` and still answers ok).
- Password: decrypted in memory only (792-801, `secure.LoadDataKeys`, a bad token gives ""), never logged; audit details carry only apartment id, endpoint and the client's error text (the same `Error.Msg` the filing path already audits).
- `_csrf` and login: unchanged, only through `server.enter` (1702c1); the test runs after the save, so after it.
- Flash keys: three added to the 1702c1 `apartmentupdate` catalog by the generator from `host_i18n.py`; no other catalog.

## Rollout wave and rollback

- **Rollout:** Dormant; the switch is brief 1705, after 1702e and 1703.
- **Rollback:** Revert the commits.

## Owner steps

None.
