# 2035: Use the branded 404 for missing property pages and copy sources

Status: todo
Depends on: none | Base commit: bd961426570f07a214f9840bf165a0bca397b450 | Branch: task/2035-go-property-branded-404
Executor: Haiku 5.5 | Tier: C | One session, hand off at 25 calls or about 50k tokens

## 1. Objective

Use Go's standard HTML 404 for missing property detail and missing copy sources. Keep tenant checks and existing successful forms.

## 2. Context

The audit reached valid property, new-property and list pages. The unknown numeric property had no heading or return link. The base has three local plain 404 branches. The standard helper already negotiates HTML on browser visits and an empty 404 for clients requesting other formats. [2025](2025-apartment-pages-chrome.md) covers separate valid-page layout issues. The 2029 property fallback work is already on the base. Apply this brief after it. If 2029 is reopened, finish one change before starting the other.

Exact anchors: `if a == nil {` and `if src == nil {` in `go/internal/web/properties/apartment_detail.go` followed immediately by `w.WriteHeader(http.StatusNotFound)` and `_, _ = w.Write([]byte("Not found."))`. In `go/internal/web/properties/apartment_new.go` the branch begins `if !found {` followed by `// Python: Response("Not found.", status_code=404).` and those statements. Routing, ID parsing, and scoping already precede these branches.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/properties/apartment_detail.go` | edit | Two plain missing/foreign branches. |
| `go/internal/web/properties/apartment_new.go` | edit | One missing/foreign copy-source branch. |
| `go/internal/web/properties/apartment_detail_test.go` | edit | Exact branded body and non-disclosure assertions. |
| `go/internal/web/properties/apartment_new_test.go` | edit | Exact branded body and existing copy-source non-disclosure assertions. |

Read only: `go/internal/hostweb/notfound.go`, `docs/design/design-system.md` and `docs/context/test-map.md`.

## 4. Steps

1. In `apartment_detail.go` replace each adjacent `w.WriteHeader(http.StatusNotFound)` and `_, _ = w.Write([]byte("Not found."))` pair at the two anchored branches with `hostweb.NotFoundPage(w, r)`. Remove the inline comment on the source-copy case. Keep each `return`. Run `gofmt -w go/internal/web/properties/apartment_detail.go 2>&1 | tail -30`.
2. In `apartment_new.go` replace the anchored comment and both write statements with `hostweb.NotFoundPage(w, r)`. Keep the `return`. Run `gofmt -w go/internal/web/properties/apartment_new.go 2>&1 | tail -30`.
3. In `TestApartmentDetailAccess` replace each body expectation ``[]string{`Not found.`}`` with ``[]string{`<h1 class="big">Page not found</h1>`, `href="/"`}``. Leave other rows as they are. Run `gofmt -w go/internal/web/properties/apartment_detail_test.go 2>&1 | tail -30`.
4. In `TestApartmentNewPage` apply that same body expectation substitution in its EN 404 rows. Delete the obsolete fallback assertion:

   ```go
   case 404:
       if len(c.has) == 0 && body != "Not found." {
           t.Errorf("%s: 404 body %q", c.name, body)
       }
   ```

   Keep the foreign-source property name exclusion. Run `gofmt -w go/internal/web/properties/apartment_new_test.go 2>&1 | tail -30`, then `6. Each formatting command should produce no output.

## 5. Do not touch

Ownership checks, query parsing, redirects for signed-out users, ordinary detail/new/list/create behavior, property POSTs, guest routes, Python or shared error CSS.

## 6. Commands

- From `go/`, with the disposable Postgres test setup configured, `go test ./internal/web/properties/... ./internal/hostweb/... 2>&1 | tail -30`. Expect okay, with the affected database tests executed.
- From `App/`, `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30`. Expect green, 0 skipped. Capture and open the touched browser pages at 390, 768 and 1280 px.

## 7. Acceptance

- [ ] EN/CS browser 404 has the UbyHost title, one localized heading and a working home control for unknown numeric property, unknown copy source and inaccessible copy source. Both unavailable cases have the same public presentation.
- [ ] Normal property/list/new views open and valid property creation still redirects to setup. A JSON client requesting the missing path gets an empty 404.
- [ ] Negative cross-workspace tests pass and screenshots expose no private property data.

## 8. Stop and ask

Stop if logic changes would be needed to identify a missing or denied record, or if styling would require shared CSS. Also stop on a missing anchor, two failures of the same check, a new dependency, out-of-scope files, or the session cap. Return the next exact action to the owner for credentials, SSH, merge or deploy.

## 9. Report

Write `docs/tasks/2035-report.md` (600 tokens max). Include files, commands and last five lines, acceptance, deviations, questions and owner steps. Use `Status: review` only with completed executor checks. Record any staging checks still pending. Use `Status: blocked` for an unmet dependency or missing acceptance evidence.

## Risk list (for the reviewer)

Three response branches, four test/prod files, and the unchanged scope checks before each rendered result.

## Owner steps

1. Open the draft PR and verify the screenshot and cross-workspace evidence.
2. Deploy its SHA to staging as part of the acceptance candidate and open the three documented 404 examples.