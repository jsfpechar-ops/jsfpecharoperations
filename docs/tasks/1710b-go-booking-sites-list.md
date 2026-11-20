# 1710b: Go booking sites list (host)

Status: todo — ready for executor (exact-diff pass, 2026-11-20).
Depends on: 1710a | Base commit: `cursor/1710a-property-page-dff7` | Branch: `cursor/1710b-booking-sites-dff7`
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: B. Part of [1710](1710-go-property-page-host.md) split a→d.

> Work on the current branch. Commit `1710b step k`. Push when §6 passes.

## 1. Objective

Port `GET /booking-sites` (`payments.booking_sites`, `App/app/routes/payments.py` 530-551). Go: `booking_sites_list.go`, template `booking_sites.tmpl`. Routes dormant (no `UBYHOST_GO_PATHS`).

## 2. Context

Python lists active apartments with publish flag; one apartment → 303 to setup. `SiteAllowed` for Max gate banner. Sidecars: `docs/tasks/1710b-files/<path>.txt`.

## 3. Files

| Path | Action |
|---|---|
| `go/internal/web/booking/booking_sites_list.go` | create |
| `go/internal/web/booking/booking_sites_list_test.go` | create |
| `go/internal/web/booking/booking_sites_list_i18n.json` | create |
| `go/internal/web/booking/booking_sites_list_i18n_keys.txt` | create |
| `go/internal/web/booking/templates/booking_sites.tmpl` | create |
| `go/internal/web/booking/testdata/booking_sites_list_golden.json` | create |
| `go/cmd/ubyhost-web/register_web_booking_host_booking_sites.go` | create |
| `go/cmd/ubyhost-web/register_web_booking_host_booking_sites_test.go` | create |
| `App/scripts/go_booking_sites_list_golden.py` | create |
| `App/tests/test_go_booking_sites_list_golden.py` | create |
| `docs/tasks/1710b-files/**` | keep |
| `docs/tasks/1710b-report.md` | create |

## 4. Steps

0. `grep -cF 'def booking_sites(request: Request):' App/app/routes/payments.py` → `1`; `ls go/internal/web/booking/booking_sites_list.go` → missing on base.
1. Copy sidecars; `sha256sum -c docs/tasks/1710b-files/MANIFEST.sha256`.
2. `gofmt`, `go vet`, `go test` (§6).
3. Golden script `--check` when `.venv` exists.
4. Write report.

## 6. Commands

- `cd go && gofmt -l . | tail -5` empty
- `cd go && go vet ./internal/web/booking/... ./cmd/ubyhost-web/... 2>&1 | tail -20` silent
- `cd go && go test ./internal/web/booking/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30` pass
- `cd App && .venv/bin/python -m pytest tests/test_go_booking_sites_list_golden.py -q --tb=short -x 2>&1 | tail -30` pass
- `python3 scripts/context_lint.py 2>&1 | tail -10` clean

## 8. Stop and ask

Anchor missing; file outside §3; 25 tool calls.

## 9. Report

`docs/tasks/1710b-report.md`.