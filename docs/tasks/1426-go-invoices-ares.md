# 1426: Go invoice pages: the ARES register lookup for the buyer

Status: todo
Depends on: 1422 (merged or on this branch: `ares.go` uses `isDigits` from 1422's `store.go`; brief 1427 uses this one) | Base commit: the working branch head (no fixed commit) | Branch: the current branch (one big PR)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B

> **One big PR mode.** Work on the current branch: never create a branch, never push, never open a PR. Commit `1426 step k` after each step that changes a file. The owner opens one pull request for all briefs.

## 1. Objective

Port the Czech business register lookup behind the form's "fill from register" button (`App/app/ares.py` and `_buyer_ares_fill`): one HTTPS request with the IČO, a 24-hour cache, 20 lookups an hour per host, the payload mapping. Tests use a local `httptest` server; no real network.

## 2. Context

Rules (AGENTS.md): 1 filing is untouched (nothing here reads or writes UbyPort data); 2 no new personal-data field and no new outbound request (one outbound request, the one Python already makes: see below); 3 fixtures are made up (`@example.test`, no real names); 4 no new dependency (stdlib, pgx and packages already in go.mod); 5 plain PostgreSQL SQL, no schema change; 7 and 10 (screenshots, UX gate) do not apply yet: the pages are not served, no path is in `UBYHOST_GO_PATHS`, and the UX gate is the owner step at the switch (brief 1427, Owner steps).

**All code is pre-written, compiled and tested** by the brief writer in a scratch worktree, in brief order 1420 to 1427. Sidecars live under `docs/tasks/1426-files/<repo path>.txt`; step 1 copies them byte for byte. You write no application code. Never retype or edit a copied file. A sha256 mismatch: STOP (§8).

| sha256 | file (repo path; sidecar = `docs/tasks/1426-files/<path>.txt`) |
|---|---|
| `13b7a9710e0150afaf005db09a94e7835b4b064417f3c4f10c7872b62e118c91` | `go/internal/web/invoices/ares.go` |
| `e2e4c5f313d5dd96588ecfc0e835502b7e9c7f9c1dc6097db008f1b9b1f329b0` | `go/internal/web/invoices/ares_test.go` |

**Parity (Python -> Go `ares.go`):**

| Python | Go |
|---|---|
| ares.lookup, _API_URL, _TIMEOUT_SECONDS=4, _USER_AGENT="UbyHost", cache 24 h, at most 1000 entries (ares.py 124-152) | `aresLookup`, `aresURL`, `aresClient`, `aresCache` |
| _map_payload, _street, _registry_entry, format_registry_mark (ares.py 52-121) | `mapAresPayload`, `aresStreet`, `formatRegistryMark` |
| validation.ico_ok (validation.py 231-240) | `icoOK` |
| ares.rate_limited, record_lookup (scope `ares`, key = owner id, 20 an hour) | `rateBlocked`, `rateRecord` |
| _buyer_ares_fill, routes/invoices.py 642-680, _BUYER_ARES_MAP | `buyerAresFill`, `buyerAresMap` |

**Outbound request (hard rule 2, reason for the PR):** the request is the one Python already makes today for this button: `GET https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/<IČO>`, only the eight-digit IČO the host typed, 4 seconds, `User-Agent: UbyHost`, no cookies, no body. Go makes it when the form is served by Go. The Go standard library `net/http` is used: no dependency.

**Behaviours the tests pin:** an invalid IČO (length, digits, mod 11) never leaves the server and is not counted; a 404 is cached as "absent" for 24 hours; any other failure is not cached; the result is cached for 24 hours; `psc` is padded to five digits, the street is `name house/orientation+letter` or `name house`, the registry entry is the first `vr` source mark rewritten for the known courts; blank buyer fields only are filled, in the order name, street, city, zip, country, DIČ; the note lists the filled field labels (`ares.field.*`); the 21st lookup within an hour is refused with `ares.rate_limited`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/invoices/ares.go` | create | register lookup, mapping, rate limit helpers, `buyerAresFill` |
| `go/internal/web/invoices/ares_test.go` | create | IČO check, mapping, cache and failure behaviour with a local server |

No other file may change.

## 4. Steps

0. Checks (repo root): `ls go/internal/web/invoices/handlers.go go/internal/web/invoices/dec.go | tail -3` lists both; `ls go/internal/web/invoices/ares.go 2>&1 | tail -2` says "No such file"; `grep -cF 'def _map_payload(' App/app/ares.py` and `grep -cF 'def _buyer_ares_fill(' App/app/routes/invoices.py` each print 1 or more; `find docs/tasks/1426-files -name '*.txt' | wc -l` prints `2`.

1. Copy and check (one call, repo root):

   ```bash
   cd docs/tasks/1426-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")"; cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum go/internal/web/invoices/ares.go go/internal/web/invoices/ares_test.go | tail -30
   ```

   All 2 hashes must equal §2. Commit "1426 step 1".

2. Build and test (repo root, one call per line; each ends with `2>&1 | tail -30`). No database is needed: this brief's tests do not use one.

   ```bash
   cd go && gofmt -l internal/web/invoices cmd/ubyhost-web 2>&1 | tail -30
   cd go && go build ./... 2>&1 | tail -30
   cd go && go vet ./internal/web/invoices/... ./cmd/... 2>&1 | tail -30
   cd go && UBYHOST_TEST_DATABASE_URL=<url> go test -count=1 ./internal/web/invoices/... ./cmd/ubyhost-web/... 2>&1 | tail -30
   ```

   Expected: the first three print nothing; the last prints `ok  \tgithub.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/invoices\t<time>` and `ok  \t...go/cmd/ubyhost-web\t<time>`. A `FAIL`, a `[build failed]` or a vet line: read the last 30 lines once, then STOP (§8).

3. Write the report (§9) and commit "1426 step 3".

## 5. Do not touch

Everything outside §3. In particular: `go/internal/hostweb/` (layout, `i18n.json`), `go/internal/session/`, `go/internal/jobs/`, `go/cmd/ubyhost-web/main.go`, `go/internal/pdf/`, `go/internal/billingjob/`, `go/internal/mail/`, `App/tests/conftest.py`, every Python file under `App/app/`, `docs/context/status.md`, `test-map.md`, `decisions.md`, `known-issues.md`, `docs/ENVIRONMENT.md`. Never set `UBYHOST_GO_PATHS`, edit Caddy or compose, push, merge or deploy. Never edit a copied file to make a test pass: a failing sidecar test is a STOP (§8). Hard rules 2, 3, 4, 5 as in §2.

## 6. Commands

Step 3 only, plus from the repo root `python3 scripts/context_lint.py 2>&1 | tail -30` (prints `context lint: OK`). Never the full suite, never `pytest tests`.

## 7. Acceptance

- [ ] The 2 sha256 values match §2.
- [ ] `gofmt -l` prints nothing; `go build ./...` and `go vet` print nothing.
- [ ] `go test` prints `ok` for `internal/web/invoices` and `cmd/ubyhost-web`; with PostgreSQL there is no `--- SKIP` line in `go test -v` (without it the report says "CI only").
- [ ] `cd go && go test -count=1 -v -run 'TestICOOK|TestMapAres|TestAres' ./internal/web/invoices/ 2>&1 | grep -c '^--- PASS'` prints 3.
- [ ] `grep -n 'http.Client\|ares.gov.cz' go/internal/web/invoices/ares.go | head -5` shows one client with a 4-second timeout and the one URL.
- [ ] `git log --oneline --grep='^1426 step' | tail -5` shows the step commits, and `git show --stat --format=%s $(git log --format=%h --grep='^1426 step') | tail -30` lists only §3 paths.
- [ ] Nothing pushed, no branch created.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor or a check in step 0 is not as written;
- a sha256 in step 1 does not match;
- `gofmt -l` prints a file, `go build` or `go vet` prints anything, or a test fails twice (read the last 30 lines once; never edit a copied file);
- you reach 25 tool calls or about 50k tokens (report as `blocked`, see executor.md);
- a new dependency seems needed, or a file outside §3 needs a change;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1426-report.md` (600 tokens at most) and set this brief's `Status: review`: diff stat, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left (none).

## Risk list (for the reviewer)

`ares.go`: the URL is built only from a validated IČO (`icoOK` first), nothing else of the host's data is sent; the timeout; the rate limit key (owner id) and that a failed lookup still counts once it was recorded (as Python); the mapping against ares.py 52-121.

## Owner steps

None: nothing is switched on. The pages stay dormant until the owner adds paths to `UBYHOST_GO_PATHS` (listed in brief 1427, Owner steps).
