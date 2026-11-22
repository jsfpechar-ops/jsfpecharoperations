# 2017 report — booking /thanks page to exact Python DOM

Status: review (three rows closed: anon, host, admin)

## Files changed

- `go/internal/web/booking/templates/shell.tmpl` — the booking shell now carries the command
  palette and the shortcuts dialogs, which `base.html` renders on every page; the thanks page was
  missing them (len 543 vs 309).
- `go/internal/web/booking/i18n.json` — the keys those blocks need. Commit `1fc9c81c3`.

## Commands

```
cd go && go build ./... && gofmt -l ./internal ./cmd          # clean
cd App && UBYHOST_E2E_PG=postgresql://postgres@127.0.0.1:5433 .venv/bin/python ../scripts/e2e/page_parity_audit.py
```

All three `/p/{slug}/thanks` rows are `pass DOM match` in the final audit reported in the index
report.

## Acceptance

0 fail rows for `/p/{slug}/thanks` for anon, host and admin.
