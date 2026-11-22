# 2014: Property pages to exact Python DOM (/apartments/{id}/booking-site, /apartments/{id}/guide/questions)

Status: todo | Depends on: 2011 | Branch: task/2014-go-parity-property-pages
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier: B

## 1. Objective — failing audit rows

| Persona | Path | py/go | Note |
|---|---|---|---|
| host | `/apartments/2/booking-site` | 200/200 | len 90 vs 77, sim 0.89 |
| host | `/apartments/2/guide/questions` | 200/200 | len 83 vs 112, sim 0.73 |

## 2. Context

- Python (read-only): `App/app/templates/booking_site_setup.html`, `guest_questions.html`, `guest_question.html`, `guide.html`.
- Go: `go/cmd/ubyhost-web/register_web_booking_host_site_setup.go`; `go/internal/web/properties/templates/guide.tmpl` + `go/internal/web/guest/leon_questions.go` (`register_web_guest_leon_questions_test.go`).
- DOM to match: booking-site setup fields/links; questions list rows (Go currently has extra/missing rows — len 112 vs 83).

## 3. Files

- Go property/booking-site + questions handlers and templates; tests.

## 4. Steps

0. Anchors: `grep -n 'booking-site\|guide/questions' go/cmd/ubyhost-web/register_web_booking_host_site_setup.go go/cmd/ubyhost-web/register_web_guest_leon_questions_test.go`.
1. Port both templates block-by-block, byte-for-byte classes/ids/names.
2. Golden tests per page against the Python render from the audit seed DB.

## 5. Do not touch

`App/`, booking POST logic, Caddy, `UBYHOST_GO_PATHS`.

## 6. Commands

```bash
cd go && go test ./internal/web/properties/... ./internal/web/booking/... ./internal/web/guest/... ./cmd/ubyhost-web/... 2>&1 | tail -30
cd App && .venv/bin/python -m pytest tests/test_onboarding*.py tests/test_property_*.py tests/test_first_*.py tests/test_booking_site.py tests/test_guide*.py tests/test_host_*.py -q --tb=short -x 2>&1 | tail -30
cd App && UBYHOST_E2E_PG=postgresql://postgres@127.0.0.1:5433 .venv/bin/python ../scripts/e2e/page_parity_audit.py 2>&1 | tail -5
# filter rows for the two paths as in 2011
```

## 7. Acceptance

0 fail rows for both paths; rows green 0 skipped; 1820 §6 screenshots.

## 8. Stop and ask

At the 25-call / 50k-token checkpoint; if a Python questions row depends on data the Go query does not fetch.

## 9. Report

`docs/tasks/2014-report.md`, <=600 tokens.
