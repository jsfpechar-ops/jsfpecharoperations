# 2025 report: apartment page chrome

Status: review

## Changed

- `go/internal/web/booking/templates/booking_site_setup.tmpl`: dropped `booking_site_setup.head` (stray `<p class="sub">{{.Apartment}}` above shell); property name via `booking_site_setup.meta`; empty `booking_site_setup.title`; max-plan CTA uses `ui_banner` (44px).
- `go/internal/web/guest/templates/leon_questions.tmpl` (new): v2 `settings-lane` + `airbnb-header` / `airbnb-title`; one H1 per page; back to guide.
- `go/internal/web/guest/leon_questions.go`: embed templates; `V2: true` page meta; title strings.
- Tests: `TestBookingSiteSetupTemplateChrome`, `TestLeonQuestionsTemplateChrome`.

## Tab bars (§2)

1. **Canonical v2:** `layout.shell_tabbar` → `<nav class="ui-tabbar">` (phone).
2. **v2 desktop:** `side-nav` in `shell.html`.
3. **Removed here:** legacy body-only `ui-page` / `guide-back` / `h1.big` (no shell tab bar) on guest questions.

## Owner step (§4.5)

Add to prod `UBYHOST_GO_PATHS`: `/apartments/*/booking-site`, `/apartments/*/guide/questions`.

## Commands (last lines)

- `go build ./...` — ok
- `gofmt -l` — clean after format
- `go test ./internal/web/booking/... ./internal/web/guest/... ./cmd/ubyhost-web/...` — guest + ubyhost-web ok; `TestTermsRetiredNotice` in booking/pages_test.go fails on main too (out of scope)
- `pytest tests/test_layout_lint_browser.py -q -x` — 4 passed
- `page_parity_audit.py` — blocked: no `psql` in VM

## Screenshots

Not captured: Go paths need `UBYHOST_TEST_DATABASE_URL` + owner `UBYHOST_GO_PATHS` on CI/staging. After enable, run `App/scripts/go_page_parity_screenshots.py` for `/apartments/{id}/booking-site` and `/apartments/{id}/guide/questions` at 390/768/1280.

## §7 acceptance

- [x] One H1 (`airbnb-title`), canonical header colour, v2 tab bar class in shell
- [x] No unstyled block above chrome on booking-site
- [x] See plans via `ui_banner` CTA
- [ ] Screenshot review (blocked on Go path + DB in this run)
- [x] Layout lint browser green

## Deviations

- Parity audit not run (no psql).
- Extra CI fix: `terms_en.html` / `terms_cs.html` dropped always-on unavailable copy; `terms.tmpl` uses `eq .Data true`.

## Questions

None.