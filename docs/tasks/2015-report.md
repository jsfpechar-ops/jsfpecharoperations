# 2015 report — guest detail page to exact Python DOM

Status: review (row closed, character-for-character)

## Files changed

The page was a Go stub (68 chars of text against Python's 10851). It is now Python's
`guest_detail.html` on the host shell:

- `go/internal/web/stays/guest_edit.go` — `writeHostGuestForm` renders on the shell instead of the
  placeholder; `loadGuest` reads the encrypted identity columns and decrypts them the way
  `reporting.guest_dict` does (birth date, document, visa, residence, signature). Commit
  `0d74e7a5f`, refined by `a4d9ba0c3`.
- `go/internal/web/stays/guest_form_page.go` + `templates/guest_form_admin.tmpl` (new) — the
  page's data: banners, identity/residence/stay sections, verify panel, signature section, form
  actions, reveal-identity form, danger zone, signature script.
- `go/internal/web/stays/{i18n_keys.txt,i18n.json,tpl.go}` — the guest-form keys, generated with
  `App/scripts/go_host_i18n.py`.

## Commands

```
cd go && go build ./... && gofmt -l ./internal ./cmd                      # clean
cd go && go test ./internal/web/stays/ ./internal/web/public/ ./cmd/ubyhost-web/   # ok
```

Probe with the audit's own servers and seed DB (script kept outside the repo), normalised DOM:

```
host /guests/1   py=200 go=200   before 10851/68   after 10851/10851   IDENTICAL
```

## Known gap, deliberately not invented

`validation_message(...)` has no Go counterpart, so a non-English host would still see English
issue sentences on the Go form where Python localises them. Left as-is rather than inventing a
translator; the audit fixture is English-only, so this does not affect the rows.

## Acceptance

0 fail rows for `/guests/1`; no access rule changed (the ownership check the Go route already had
is untouched).
