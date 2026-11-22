# 2013: Admin + dev pages to exact Python DOM (/booking-sites, /admin/fakturace/export, /dev/ui, /api/command-palette)

Status: todo | Depends on: 2011 | Branch: task/2013-go-parity-admin-dev
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier: B

## 1. Objective — failing audit rows

| Persona | Path | py/go | Note |
|---|---|---|---|
| admin | `/booking-sites` | 200/200 | len 86 vs 73, sim 0.92 |
| admin | `/admin/fakturace/export` | 500/500 | error body len 956 vs 21, sim 0.03 |
| admin | `/dev/ui` | 200/200 | len 2152 vs 31, sim 0.03 — Go stub |
| host | `/api/command-palette` | 200/200 | JSON len 3422 vs 3322, sim 0.91 |

## 2. Context

- Python (read-only): `App/app/templates/booking_sites.html`, `dev_ui.html`, `error.html`; export handler in `App/app/routes/admin_billing.py`; palette JSON in `App/app/routes/api.py`.
- Go: `go/internal/web/booking/booking_sites_list.go`, `go/internal/web/billing/admin*.go` + `go/internal/web/exports/`, `go/internal/web/public/dev_ui.go`, palette: `grep -rn 'package palette' go/internal | head -2` (wired at `go/cmd/ubyhost-web/register_web.go:32`).
- DOM to match: booking-sites rows/links; the **500 error body** must render Python's `error.html` content (not a 21-char stub) with status 500; full dev-ui catalog; palette JSON with identical keys/commands/order.

## 3. Files

- The Go files above + tests.

## 4. Steps

0. Anchors: `grep -n 'Handle' go/cmd/ubyhost-web/register_web_booking_host_booking_sites.go`; `grep -rn 'fakturace/export' go/internal --include='*.go' | head`.
1. booking-sites: port row markup byte-for-byte.
2. fakturace/export: keep Python's 500, render the full error template.
3. dev/ui: port the whole catalog from `dev_ui.html`.
4. command-palette: diff JSON keys against `App/app/routes/api.py`; match ordering and labels (translated, not raw keys — see #1231).

## 5. Do not touch

`App/`, billing logic, Caddy, `UBYHOST_GO_PATHS`.

## 6. Commands

```bash
cd go && go test ./internal/web/booking/... ./internal/web/billing/... ./internal/web/exports/... ./internal/web/public/... ./cmd/ubyhost-web/... 2>&1 | tail -30
cd App && .venv/bin/python -m pytest tests/test_admin_customers.py tests/test_host_*.py tests/test_design_guardrails_browser.py tests/test_invoice_*.py tests/test_stay_fee*.py tests/test_design_*.py tests/test_dev_ui*.py tests/test_admin_funnel.py -q --tb=short -x 2>&1 | tail -30
cd App && UBYHOST_E2E_PG=postgresql://postgres@127.0.0.1:5433 .venv/bin/python ../scripts/e2e/page_parity_audit.py 2>&1 | tail -5
# filter rows for the four paths as in 2011
```

## 7. Acceptance

0 fail rows for the four paths; rows green 0 skipped; 1820 §6 screenshots for `/dev/ui`, `/booking-sites`.

## 8. Stop and ask

At the 25-call / 50k-token checkpoint; if the Python 500 on export is intentional and Go must instead return a different status — STOP, that is a parity decision for the owner.

## 9. Report

`docs/tasks/2013-report.md`, <=600 tokens.
