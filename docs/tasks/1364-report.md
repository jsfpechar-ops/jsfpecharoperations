# 1364 report

Status: review. Steps 1-6 done.

Start commit (HEAD before step 1): `cd3a498 1361 step 7`

## Commits

- `79f840f 1364 step 2`: detail keys appended to `i18n_keys.txt`, `i18n.json` regenerated.
- `01e1176 1364 step 3`: routes, test mux and golden cases patched.
- `022ad2c 1364 step 4`: `admin_customer.tmpl` and `detail.go` created.
- `4cb33b8 1364 step 5`: detail golden regenerated (23 list cases).
- Step 6: this report and the brief `Status:` line.

## Files changed (`git diff --stat cd3a498`)

- `go/internal/web/customers/templates/i18n_keys.txt` (append)
- `go/internal/web/customers/templates/i18n.json` (generated)
- `App/scripts/go_customers_pages_golden.py` (14 detail cases)
- `go/cmd/ubyhost-web/register_web_customers.go` (registers `GET /admin/customers/{user_id}`)
- `go/internal/web/customers/pages_test.go` (detail route in `pagesMux`)
- `go/internal/web/customers/templates/admin_customer.tmpl` (create)
- `go/internal/web/customers/detail.go` (create)
- `go/internal/web/customers/testdata/customers_pages_golden.json` (generated)
- `docs/tasks/1364-go-customer-admin-detail.md` (Status line)
- `docs/tasks/1364-report.md` (this file)

## Commands (last lines of output)

Step 1 (skipped, Postgres already up):

```
127.0.0.1:55436 - accepting connections
```

Step 2:

```
sha256sum go/internal/web/customers/templates/i18n_keys.txt
0db15e06bf076493216036b0ba7a03a6db3971a49cbcc2d6b6f70ea7a58f76a2  go/internal/web/customers/templates/i18n_keys.txt
(cd App && .venv/bin/python scripts/go_host_i18n.py)
wrote /home/user/jsfpecharoperations/go/internal/web/customers/templates/i18n.json
sha256sum go/internal/web/customers/templates/i18n.json
e4b9ef43aadd546823909e7ec8035905b1f63def898ba882e6342d7849a5b137  go/internal/web/customers/templates/i18n.json
```

Step 3:

```
git apply --check /tmp/1364.patch && git apply /tmp/1364.patch   (exit 0)
git status --short
 M App/scripts/go_customers_pages_golden.py
 M go/cmd/ubyhost-web/register_web_customers.go
 M go/internal/web/customers/pages_test.go
ec0647b918ca7ff2a517e120789b7c2d4d5f56f816ded0277741fec62573ae00  App/scripts/go_customers_pages_golden.py
7a7d109926b3f2895c2167b634e19da4a93a6baf7c933d59435936ddc8756da5  go/cmd/ubyhost-web/register_web_customers.go
9f276a8e3f5fd34b7db3f74fc89dc46466c2421e59b4382435cd49e59272c1a4  go/internal/web/customers/pages_test.go
```

All sha256 values match section 4 of the brief.

## Steps 4-6

Step 4 sha256: `admin_customer.tmpl` e2003e0fab0c9c071f3350a61c1697bed6a77594dc7d49c4f097e4f1f3ba2d33; `detail.go` e6a4c9a4b27ce78b4c99a40cdab6d6db587935799659c91c8020e2fada06f07c (both match). `go vet ./internal/web/... ./cmd/...`: no output, exit 0.

Step 5 golden sha256 d88d9f1338fcd9ad1d0e2ff4ea78a995c4bff102d934417b0efb28fe30ffa6f0 (match). Generator run twice; the golden JSON is identical to the §4 hash after the run.

Section 6 results:

- gofmt, `go vet ./...`, `go test ./internal/web/customers/ ./cmd/ubyhost-web/`: `ok` for both packages.
- SKIP count (`grep -E -c 'SKIP'`): 0.
- `go test -run TestPagesMatchPython -v`: PASS, golden has 23 cases (9 list, 14 detail).
- pytest (3 files): `4 passed in 4.92s`.
- `python3 scripts/context_lint.py`: `context lint: OK`.
- `grep -c 'mux.Handle' go/cmd/ubyhost-web/register_web_customers.go`: 4.

## Acceptance (§7)

- [x] Every file in §3 has the sha256 given in §4.
- [x] `TestPagesMatchPython` passes; customers and cmd/ubyhost-web tests pass; SKIP count 0.
- [x] `mux.Handle` count is 4.
- [x] §6 commands 3 and 4 as expected.

## Deviations

Done: steps 1 to 6. Nothing was pushed.

Step 1 (Postgres) was skipped because it was already up.

## Questions

None.

## Owner steps left

None. Push and the draft PR are left to the coordinator.
