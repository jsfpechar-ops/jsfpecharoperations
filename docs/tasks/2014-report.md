# 2014 report — property pages to exact Python DOM

Status: review (both rows closed, text identical)

## Files changed

- `/apartments/{id}/booking-site` — `go/internal/web/booking/templates/booking_site_setup.tmpl`:
  the back link is `payments.page.title` ("Public page") with the apartment name as the meta
  line, as Python's `booking_site_setup.html` renders it. Commit `d4896283e`.
- `/apartments/{id}/guide/questions` — `go/internal/web/guest/leon_questions.go`: one
  `Guest questions` header (not two), no "nothing waiting" line when the list is empty, and the
  empty state's `Guest guide` action. Same commit.

## Commands

```
cd go && go build ./... && gofmt -l ./internal ./cmd          # clean
cd App && UBYHOST_E2E_PG=postgresql://postgres@127.0.0.1:5433 .venv/bin/python ../scripts/e2e/page_parity_audit.py
```

Both rows were `fail` at the start of this branch (len 90 vs 77 and 83 vs 112) and are green in
the final audit reported in the index report.

## Acceptance

0 fail rows for the two paths; no access rule or route touched (markup and labels only).
