# 2034: Show the booking-unavailable notice under the retirement flag

Status: todo
Depends on: none | Base commit: bd961426570f07a214f9840bf165a0bca397b450 | Branch: task/2034-go-retired-booking-terms
Executor: Haiku 5.5 | Tier: A | One session, hand off at 25 calls or about 50k tokens

## 1. Objective

Add the EN/CS availability notice to the existing Go booking terms when `UBYHOST_PAYMENTS_RETIRED=1`. Keep the existing terms readable for past bookings.

## 2. Context

Chromium returned 200 in both locales and displayed checkout terms without the availability note. The Go terms factory currently takes no environment lookup. The property page already calls `appconfig.PaymentsRetired(d.Getenv)`. The audit webhook POST returned the expected neutral 200. Adopt the existing switch for the terms page only. The exact proposed EN/CS strings for the user-requested notice are “Booking is currently unavailable.” and “Rezervace momentálně nejsou dostupné.”

Exact anchors: `func TermsHandler() http.HandlerFunc {` in `go/internal/web/booking/pages.go`, `booking.TermsHandler()` in `go/cmd/ubyhost-web/register_web_booking_pages.go`, and `<section class="pp-bk-card">` in `go/internal/web/booking/templates/terms.tmpl`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/booking/pages.go` | edit | Pass the retirement state to the existing terms view. |
| `go/cmd/ubyhost-web/register_web_booking_pages.go` | edit | Wire the production environment lookup. |
| `go/internal/web/booking/templates/terms.tmpl` | edit | Localized notice above document body. |
| `go/internal/web/booking/pages_test.go` | edit | Flag off/on, both locales. |

Read only: `go/internal/appconfig/payments_hidden.go`, `go/internal/web/booking/property.go` and `docs/context/test-map.md`.

## 4. Steps

1. In `pages.go` replace `import "net/http"` with:

   ```go
   import (
       "net/http"

       "github.com/jsfpechar-ops/jsfpecharoperations/go/internal/appconfig"
   )
   ```

   Change `func TermsHandler() http.HandlerFunc {` to `func TermsHandler(getenv func(string) string) http.HandlerFunc {` and change the existing terms render call to:

   ```go
   writeGuest(w, r, set, http.StatusOK, Guest{Lang: lang, Title: title, Data: appconfig.PaymentsRetired(getenv)}, nil)
   ```

   Run `gofmt -w go/internal/web/booking/pages.go 2>&1 | tail -30`. Expect empty output.
2. In `register_web_booking_pages.go` add `"os"` next to `"net/http"` and set the route's factory call to `booking.TermsHandler(os.Getenv)`. Run `gofmt -w go/cmd/ubyhost-web/register_web_booking_pages.go 2>&1 | tail -30`. Expect empty output.
3. Directly after `<section class="pp-bk-card">` in `terms.tmpl`, add:

   ```html
       {{if .Data}}
         <p role="note">{{if eq .Lang "en"}}Booking is currently unavailable.{{else}}Rezervace momentálně nejsou dostupné.{{end}}</p>
       {{end}}
   ```

   Run `git diff --check 2>&1 | tail -30`. Expect empty output.
4. In `pages_test.go`, replace `TermsHandler()` in `pageMux` with `TermsHandler(func(string) string { return "" })`. Add this test immediately before `func TestTermsIsAGuestPage(t *testing.T) {`:

   ```go
   func TestTermsRetiredNotice(t *testing.T) {
       cases := []struct {
           lang, notice, title string
       }{
           {"en", "Booking is currently unavailable.", "Booking terms"},
           {"cs", "Rezervace momentálně nejsou dostupné.", "Podmínky rezervace"},
       }
       for _, tc := range cases {
           for _, setting := range []string{"", "1"} {
               getenv := func(key string) string {
                   if key == "UBYHOST_PAYMENTS_RETIRED" {
                       return setting
                   }
                   return ""
               }
               rec := httptest.NewRecorder()
               TermsHandler(getenv).ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/terms/booking?lang="+tc.lang, nil))
               body := rec.Body.String()
               if rec.Code != http.StatusOK || !strings.Contains(body, "<h1>"+tc.title+"</h1>") {
                   t.Fatalf("terms did not render for %s, retired=%q", tc.lang, setting)
               }
               if strings.Contains(body, tc.notice) != (setting == "1") {
                   t.Errorf("unexpected availability notice for %s, retired=%q", tc.lang, setting)
               }
           }
       }
   }
   ```

   Run `gofmt -w go/internal/web/booking/pages_test.go 2>&1 | tail -30`, then §6.

## 5. Do not touch

Existing legal clauses, pricing, property publication, payment rails, webhook handling, analytics, the retired flag's default, production config or Python templates. Preserve noindex, language links, HTML response and the cookie policy.

## 6. Commands

- From `go/`, `go test ./internal/web/booking ./cmd/ubyhost-web -run 'TestTerms|TestHeadHasNoBody|TestPaymentsHidden|TestPaymentsRetired|TestPropertyPagePaymentsRetiredHidesBook' -count=1 -v 2>&1 | tail -30`. The new EN/CS on/off check must run.
- From `App/`, `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30`. Expect green, 0 skipped. Capture the Go terms page in Chromium on the staged candidate at 390/1280 px in both languages.

## 7. Acceptance

- [ ] Both localized notices appear with the flag set. With the flag clear, both terms pages still render without the notice.
- [ ] Existing card terms, language switch and noindex are present. No new cookies, links to checkout, or layout regressions.
- [ ] Together with the release gate, a seeded public listing hides booking and the dummy webhook still replies neutrally under retirement.

## 8. Stop and ask

Stop if published main now has the equivalent notice or a new legal-copy prerequisite. Also stop on a missing anchor, two failures of the same check, a new dependency, out-of-scope files, or the session cap. Return the next exact action to the owner for credentials, SSH, merge or deploy.

## 9. Report

Write `docs/tasks/2034-report.md` (600 tokens max). Include files, commands and last five lines, acceptance, deviations, questions and owner steps. Use `Status: review` only with completed executor checks. Record any staging checks still pending. Use `Status: blocked` for an unmet dependency or missing acceptance evidence.

## Risk list (for the reviewer)

The route factory, terms handler/template and tests. Review exact copy and ensure the retired flag is read at request time.

## Owner steps

1. Review the draft PR and the exact EN/CS notice.
2. Deploy its SHA to staging with retired payments selected. Send the staging URL and fixture for the screenshot and public booking checks.

