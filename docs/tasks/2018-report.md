# 2018 report — reservations pages to exact Python DOM

Status: review (both rows closed, character-for-character)

## Files changed

- `/reservations/1/guests/new` — `go/internal/web/stays/templates/guest_form_admin.tmpl` (new),
  `guest_form_page.go` (new), `guest_edit.go`, `i18n.json`/`i18n_keys.txt`/`tpl.go`: Python's
  guest form block for block (country list from `codelists.nationality_options`, purposes, doc
  types, `display_birth_date`, `mask_identifier`, passport-photo/PDF checks, signature display).
  Commits `0d74e7a5f`, `a4d9ba0c3`.
- `/reservations` — `go/internal/web/stays/overdue.go`: Go dropped a past stay from the default
  view once `date_to` was more than three days before today (unless the report had failed).
  Python has no such cutoff — `reporting.dashboard_rows` only ages out *finished* stays and
  `_overdue_unfinished_ids` already excludes those — so a stay with a guest still unfiled stays
  in Upcoming however long ago the guests left. Two demo stays (overdue by 38 days) and their rows
  were missing. Commit `50c1d08aa`.

## Commands

```
cd go && go build ./... && gofmt -l ./internal ./cmd          # clean
cd App && UBYHOST_E2E_PG=postgresql://postgres@127.0.0.1:5433 .venv/bin/python ../scripts/e2e/page_parity_audit.py
```

Probe with the audit's own servers and seed DB (script kept outside the repo), normalised DOM:

```
host /reservations              py=200 go=200  before 2611/2123  after 2599/2599  IDENTICAL
host /reservations/1/guests/new py=200 go=200  before 10269/9    after 10269/10269 IDENTICAL
```

(The `/reservations` length moves from 2123 to 2599 on the Go side; Python's own length for the
run is 2599 — the brief's 2611 was the first audit's persona.)

## Acceptance

0 fail rows for both paths; no access rule changed.
