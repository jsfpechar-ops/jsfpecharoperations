# 2018: `/reservations` + `/reservations/{id}/guests/new` residual DOM parity

Status: todo | Depends on: 2011; check `git log --oneline | grep -i 1856` — if 1855/1856 are not merged, run them first | Branch: task/2018-go-parity-reservations
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier: B

## 1. Objective — failing audit rows

| Persona | Path | py/go | Note |
|---|---|---|---|
| host | `/reservations` | 200/200 | len 2611 vs 2123, sim 0.89 |
| host | `/reservations/1/guests/new` | 200/200 | len 10269 vs **9**, sim 0.00 — Go stub |

## 2. Context

- Python (read-only): `App/app/templates/reservations.html` (1856 brief quotes anchors), `guest_form_admin.html`.
- Go: `go/internal/web/stays/` (`register_web_stays_test.go`, `register_web_stays_guest_edit_test.go`).
- DOM to match: chips, filter form, rows, `stays-pager ph-hide`, `list stays-more` with `rel="next"` (1856 §1); the full guests/new form (currently 9 chars).

## 3. Files

- `go/internal/web/stays/` list + guest-new handlers/templates; tests.

## 4. Steps

0. `grep -n 'stays-pager\|stays-more\|data-filter-summary' go/internal/web/stays/templates/stays_list.tmpl | head`; find the guests/new handler.
1. Close the remaining list drift; port guests/new fully (field semantics per UBYPORT_CORE).
2. Goldens vs the Python render.

## 5. Do not touch

`App/`, POST routes under `/reservations`, Caddy, `UBYHOST_GO_PATHS`, `go/internal/hostweb/layout` (1858 owns it).

## 6. Commands

```bash
cd go && go test ./internal/web/stays/... ./cmd/ubyhost-web/... 2>&1 | tail -30
cd App && .venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py tests/test_guest_*.py tests/test_guest_browser_e2e.py tests/test_design_guardrails_browser.py -q --tb=short -x 2>&1 | tail -30
cd App && UBYHOST_E2E_PG=postgresql://postgres@127.0.0.1:5433 .venv/bin/python ../scripts/e2e/page_parity_audit.py 2>&1 | tail -5
# filter rows path == '/reservations' or startswith('/reservations/')
```

## 7. Acceptance

0 fail rows for both paths; rows green 0 skipped; 1820 §6 screenshots 390/768/1280.

## 8. Stop and ask

At the 25-call / 50k-token checkpoint; if 1856 is unmerged and conflicts — STOP and report.

## 9. Report

`docs/tasks/2018-report.md`, <=600 tokens.
