# 1605 report

Status: review

## Files changed

```
fab7ea4e2 1605 step 1
```

```
fab7ea4e2 1605 step 1
 App/scripts/registration_form_golden.py                  | ...
 App/tests/test_go_registration_form.py                   | ...
 go/cmd/ubyhost-web/register_web_exports_test.go          | ...
 go/internal/web/exports/form_pdf.go                     | ...
 go/internal/web/exports/form_pdf_test.go                | ...
 go/internal/web/exports/i18n.json                        | ...
 go/internal/web/exports/i18n_keys.txt                    | ...
 go/internal/web/exports/more_env_test.go                 | ...
 go/internal/web/exports/routes.go                        | ...
 go/internal/web/exports/routes_inventory_test.go         | ...
 go/internal/web/exports/testdata/registration_form_golden.json | ...
```

## Commands (last 5 lines each)

Step 0: both sha256 `: OK`; form_pdf.go missing; housebook anchor `1`; 11 sidecars.

Step 1: 11× `: OK`.

Step 2: (no output).

Step 4 Go:
```
ok  	.../go/internal/web/exports	1.021s
ok  	.../go/cmd/ubyhost-web	0.083s
```
Named: 5× `--- PASS`, 2× `ok`, SKIP **0**.

Python: **CI only** (`App/.venv` absent; brief §4 does not create one).

Step 5: `server stopped`.

`python3 scripts/context_lint.py`: `context lint: OK`.

## §7 Acceptance

- [x] sha256 step 1: 11 OK
- [x] Step 2: no output
- [x] Step 4: 2 ok, 5 PASS, SKIP 0; Python CI only
- [x] Commits list step 1; stat paths §3 only
- [x] No UBYHOST_GO_PATHS / deploy / push (executor pushes `wt-1605` per coordinator)
- [x] UI N/A

## Deviations

Installed `postgresql-16` apt package; throwaway PG on 55705 (no pre-existing PG16).

## Questions

None.

## Owner steps left

After thread merge: add `/guests/*/form.pdf` to `UBYHOST_GO_PATHS` (see brief 1609 list).

Known differences: E1–E10 per brief §2 (unchanged).