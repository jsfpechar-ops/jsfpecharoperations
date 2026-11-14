# 1510 report

Status: review

## Unblocked

1607 on go-wave3 (`exports.BuildWorkspaceZip`). Sidecar `docs/tasks/1510-files/` written with sha256 sums.

## Files

- `go/internal/web/auth/export.go`, `export_test.go`, `testdata/workspace_export.json`
- `App/scripts/auth_export_golden.py`
- `go/internal/web/auth/auth.go`, `auth_test.go` (route row + count 27)
- `go/internal/web/auth/i18n_keys.txt`, `i18n.json`
- `docs/tasks/1510-go-auth-export.md` (Status review, Depends 1607)

## Commands (last lines)

```text
go test ./internal/web/auth/... ./cmd/ubyhost-web/... -count=1 → ok (0 SKIP)
pytest tests/test_go_auth_routes.py → 2 passed
```

PostgreSQL: port 55520, data `/var/tmp/pg55520`.

## §7

- [x] Go builder exists; Depends on 1607; sidecar sha256 written.

## Deviations

- `scripts/edit_routes_1510.py` (not in brief table; same role as 1509 `edit_routes.py`).
- Golden does not record `Content-Length` (DEFLATE/PDF size differs); zip entry names + manifest compared.

## Owner

After merge: add `/admin/users/*/export` to `UBYHOST_GO_PATHS` with 1504/1509 routes (brief §Owner).