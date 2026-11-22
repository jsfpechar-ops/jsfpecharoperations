# 2013 report — admin + dev pages to exact Python DOM

Status: review (all four rows closed, text identical)

## Files changed

- `/admin/fakturace/export` — `go/internal/web/auth/authpage/errorpage.go` (new) and
  `templates/error.html` (new): `ErrorPage(getenv, now, hostOf, next)` rewrites a 500 HTML
  response with Python's `error.html` (`error.server.title/body`, `error.home`) on the auth base
  shell, and passes every other response through. `authpage.RenderServerError` added;
  `i18n.json` + `i18n_keys.txt` gained the three error keys. Commit `9354032a5`.
  Both sides 500 because the audit fixture has no invoice data to export; the language follows
  the session (English for a signed-in admin, Czech for a visitor), as `templating.render` does.
- `/dev/ui` — `go/internal/web/public/dev_ui_page.go` + `templates/dev_ui/dev_ui.tmpl` (new) are
  Python's component catalog rendered on the host shell through the `ui_*` macros; `?kind=` is
  honoured and the default is `detail`. The old `dev_ui.go` stub is deleted. Commit `24a8b86c0`.
- `/api/command-palette` — stay labels use the dotted date Go's `api.py` counterpart renders.
  Commit `7b29b2cf0`.
- `/booking-sites` — `booking_sites.title` defined; Python's block title is the h1. Commit
  `d4896283e`.

## Commands

```
cd go && go build ./... && gofmt -l ./internal ./cmd          # clean
cd App && UBYHOST_E2E_PG=postgresql://postgres@127.0.0.1:5433 .venv/bin/python ../scripts/e2e/page_parity_audit.py
```

Probe with the audit's own servers and seed DB (script kept outside the repo), normalised DOM:

```
admin /dev/ui                  py=200 go=200 len 2152/2152   IDENTICAL
admin /admin/fakturace/export  py=500 go=500 len  956/956    IDENTICAL
```

## Acceptance

0 fail rows for these four paths (confirmed by the final audit in the index report).

## Notes for the owner

- `/admin/fakturace/export` failing is Python's behaviour too (a 500 with the error page). Go now
  fails the same way, with the same page and the same language rule — nothing is being hidden.
- No access rule was touched: `/dev/ui` still requires the admin the Go route already enforced.
