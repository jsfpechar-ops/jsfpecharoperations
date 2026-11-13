# 1364 report (steps 1-3)

Status: partial. Steps 1-3 done, steps 4-6 left.

Start commit (HEAD before step 1): `cd3a498 1361 step 7`

## Commits

- `79f840f 1364 step 2`: detail keys appended to `i18n_keys.txt`, `i18n.json` regenerated.
- `01e1176 1364 step 3`: routes, test mux and golden cases patched.

## Files changed (`git diff --stat cd3a498`)

- `go/internal/web/customers/templates/i18n_keys.txt` (append)
- `go/internal/web/customers/templates/i18n.json` (generated)
- `App/scripts/go_customers_pages_golden.py` (14 detail cases)
- `go/cmd/ubyhost-web/register_web_customers.go` (registers `GET /admin/customers/{user_id}`)
- `go/internal/web/customers/pages_test.go` (detail route in `pagesMux`)
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

## Acceptance (§7)

- [x] Files of steps 2-3 have the sha256 given in §4 (step 4 files not yet created).
- [ ] Not yet: steps 4-6 (Go build and tests, DetailHandler, template, SKIP count).

## Deviations

Done: steps 1 to 3. Left: steps 4 to 6.

The build fails until step 4 adds `DetailHandler` (expected per brief §4 step 3). Nothing was pushed.

## Questions

None.

## Owner steps left

None yet. Steps 4-6 remain for the next session.
