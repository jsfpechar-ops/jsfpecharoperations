# 2012: `/` landing + dashboard to exact Python DOM

Status: todo | Depends on: 2011 | Branch: task/2012-go-parity-landing-dashboard
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier: B

## 1. Objective — failing audit rows

| Persona | Path | py/go | Note |
|---|---|---|---|
| anon | `/` | 200/200 | len 2428 vs 1215, sim 0.49 |
| host | `/` | 200/200 | len 658 vs 319, sim 0.05 |
| admin | `/` | 200/200 | len 502 vs 258, sim 0.05 |

## 2. Context

- Python (read-only): `App/app/templates/landing.html` (+`_public_header.html`, `_public_footer.html`, `_posthog.html` — PostHog only on public pages named in `App/app/analytics.py`, rule 2), `dashboard.html`, `admin_home.html`.
- Go: `go/internal/web/public/templates/pages/landing.tmpl`, `hostweb.DashboardHandler` (`go/cmd/ubyhost-web/register_web_hostweb_dashboard.go`).
- DOM to match: all landing sections, footer legal links, privacy line; dashboard cards/chips; admin home blocks — normalised DOM equal to Python.

## 3. Files

- Go landing template + hostweb dashboard/admin-home rendering; matching tests.

## 4. Steps

0. `grep -n 'posthog\|section\|footer' App/app/templates/landing.html | head -20`; find the Go dashboard template.
1. Port missing sections/cards; keep classes/ids byte-for-byte.
2. Golden test per persona comparing normalised DOM.

## 5. Do not touch

`App/`, analytics config, other pages, Caddy, `UBYHOST_GO_PATHS`.

## 6. Commands

```bash
cd go && go test ./internal/web/hostweb/... ./internal/web/public/... ./cmd/ubyhost-web/... 2>&1 | tail -30
cd App && .venv/bin/python -m pytest tests/test_public_*.py tests/test_landing_*.py tests/test_legal_*.py tests/test_host_*.py tests/test_host_geometry.py tests/test_posthog_*.py tests/test_umami_guard.py -q --tb=short -x 2>&1 | tail -30
cd App && UBYHOST_E2E_PG=postgresql://postgres@127.0.0.1:5433 .venv/bin/python ../scripts/e2e/page_parity_audit.py 2>&1 | tail -5
# then the same python filter as in 2011 with path == '/'
```

## 7. Acceptance

0 fail rows for `/` in the audit; test-map rows green, 0 skipped; 1820 §6 screenshots 390/768/1280.

## 8. Stop and ask

At the 25-call / 50k-token checkpoint; if a Python section has no Go public-template equivalent.

## 9. Report

`docs/tasks/2012-report.md`, <=600 tokens.
