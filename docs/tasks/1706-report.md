# 1706 report: Go TTLock client

Status: review

## Commits

- Implementation on `main` (`027ed0cc1`), file hashes match brief §2 table.
- **`1706 step 0`:** anchor checks (empty).
- **`1706 step 1`:** `sha256sum` on live `go/internal/ttlock/*.go` OK; MANIFEST lists `*.txt` under `go/` (paths stale) — verified via direct sums (empty).
- **`1706 step 2`:** this report.

## Files (§3)

| Path | Note |
|---|---|
| `go/internal/ttlock/api.go` | CreateAccount, CheckLocks, passcodes |
| `go/internal/ttlock/budget.go` | PGBudget 30k/month guard |
| `go/internal/ttlock/budget_test.go` | |
| `go/internal/ttlock/client.go` | HTTP client, errors |
| `go/internal/ttlock/client_test.go` | httptest fake server |
| `go/internal/ttlock/tokens.go` | OAuth exchange/refresh |
| `docs/tasks/1706-files/**` | sidecars (unchanged) |
| `docs/tasks/1706-report.md` | this file |

No routes; dead code until 1707 / 1771.

## Commands (last lines)

Step 0: anchors `1`×5, sidecars `6`, no `testdata` dir.

```
sha256sum go/internal/ttlock/*.go
77cafb37… api.go
15284fe4… budget.go
7f155fb4… budget_test.go
b022ea28… client.go
812fc403… client_test.go
29a1faf1… tokens.go
```

```
cd go && gofmt -l .
(empty)
```

```
cd go && go vet ./internal/ttlock/... ./cmd/...
(silent)
```

```
cd go && go test ./internal/ttlock/... ./cmd/ubyhost-web/... -count=1
ok  	.../go/internal/ttlock	0.032s
ok  	.../go/cmd/ubyhost-web	1.684s
```

```
python3 scripts/context_lint.py
context lint: OK
```

Host pages / layout lint: N/A (no template changes).

## Section 7

- [x] `ttlock.py` parity covered by `client_test.go` / httptest (OAuth, locks, passcodes, budget).
- [x] Tokens via existing `secure` package; tests assert no token logging.
- [x] Outbound host: same TTLock API as `App/app/ttlock.py` only.
- [ ] Route goldens — N/A (brief §2: no route golden).
- [x] Step commits; diff on branch is report (+ step empties) only vs pre-report `main`.

## Accepted differences

- `MANIFEST.sha256` paths name `go/internal/ttlock/*.go.txt`; live checksums use `*.go` (hashes match brief table).
- Client landed on `main` in combined commit `027ed0cc1` (includes unrelated `mailjob/holds`).

## Deviations

None.

## Questions

None.

## Owner steps

None.

## PR note (outbound)

Future door-code jobs call the TTLock OAuth/API endpoints already used by `ttlock.py` (`euopen.ttlock.com`); no new third-party host.