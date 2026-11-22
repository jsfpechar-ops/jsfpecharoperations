# 2017: Public booking thanks `/p/{slug}/thanks` to exact Python DOM

Status: todo | Depends on: 2011 | Branch: task/2017-go-parity-booking-thanks
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier: C (public page)

## 1. Objective — failing audit rows

| Personas | Path | py/go | Note |
|---|---|---|---|
| admin, anon, host | `/p/{slug}/thanks` | 200/200 | len 543 vs 309, sim 0.73 |

## 2. Context

- Python (read-only): template rendered for `/p/{slug}/thanks` — confirm with `grep -rn 'thanks' App/app/routes/*.py | head` (expected `App/app/templates/property_page_booked.html`).
- Go: `go/internal/web/booking/pages.go` `ThanksHandler` (test `pages_test.go` already requires back link + h1 + `X-Robots-Tag`).
- DOM to match: full thanks content — h1, back link, summary block; keep `X-Robots-Tag`.

## 3. Files

- `go/internal/web/booking/pages.go` + template; tests.

## 4. Steps

0. Anchor: `grep -n 'Thanks\|thanks' go/internal/web/booking/pages.go | head`.
1. Port the missing blocks byte-for-byte.
2. Golden test vs the Python render.

## 5. Do not touch

`App/`, booking POST/checkout logic, Caddy, `UBYHOST_GO_PATHS`.

## 6. Commands

```bash
cd go && go test ./internal/web/booking/... ./cmd/ubyhost-web/... 2>&1 | tail -30
cd App && .venv/bin/python -m pytest tests/test_property_slug.py tests/test_property_page.py tests/test_property_page_photos.py tests/test_property_page_meta.py tests/test_property_page_rules.py tests/test_booking_site.py tests/test_public_*.py -q --tb=short -x 2>&1 | tail -30
cd App && UBYHOST_E2E_PG=postgresql://postgres@127.0.0.1:5433 .venv/bin/python ../scripts/e2e/page_parity_audit.py 2>&1 | tail -5
# filter rows path == '/p/FZgxhwx4OGY3GVgm/thanks'
```

## 7. Acceptance

0 fail rows for the thanks path; rows green 0 skipped; 1820 §6 screenshots.

## 8. Stop and ask

At the 25-call / 50k-token checkpoint.

## 9. Report

`docs/tasks/2017-report.md`, <=600 tokens.
