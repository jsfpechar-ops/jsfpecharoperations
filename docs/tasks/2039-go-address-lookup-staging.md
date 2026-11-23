# 2039: Restore useful address suggestions on the Go setup candidate

Status: todo
Depends on: staging SHA from 2037 step 1 | Base commit: bd961426570f07a214f9840bf165a0bca397b450 | Branch: task/2039-go-address-lookup-staging
Executor: Haiku 5.5 | Tier: B | One session, hand off at 25 calls or about 50k tokens

## 1. Objective

Let hosts pick a Czech address and fill the remaining address fields in one action. Preserve manual entry for unmatched and nonstandard addresses.

## 2. Context

At 390 px, the Add property form showed the street field and had a live lookup handler. Entering the public Prague street name Vinohradská generated a suggestion request returning 200 and zero results. That response can represent the flag, the query, throttling or unavailable reference rows. It does not yet justify a renderer or search rewrite. The Go app already serves lookup from local ČÚZK RÚIAN reference data.

Exact anchors: `data-ruian-suggest` and `/static/ruian_suggest.js` in `go/internal/web/properties/apartmentnew/apartment_new.tmpl`, and `func (s *Pages) ruianSuggest(w http.ResponseWriter, r *http.Request) {` in `go/internal/web/properties/ruian_suggest.go`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `docs/tasks/2039-report.md` | new | Fixture, effective conditions, match/result and focused follow-up. |

Read only: `go/internal/web/properties/apartment_new.go`, `go/internal/web/properties/apartmentnew/apartment_new.tmpl`, `go/internal/web/properties/ruian_suggest.go`, `go/internal/web/properties/ruian_suggest_test.go`, `go/cmd/ubyhost-web/register_web_properties_ruian.go`, `App/app/static/ruian_suggest.js` and `docs/design/design-system.md`.

## 4. Steps

1. In a fresh host Chromium session on the confirmed SHA, type a public Czech address known to be in the staged dataset. Wait for the ordinary suggestions then inspect the response status and result count. Repeat for a street prefix and a no-match query. Expected: a populated list for the known address and manual entry for no match. Use §6.
2. If the same known address returns an empty array, ask the owner to confirm the lookup is enabled, the importer has loaded reference rows on the intended database and the endpoint is owned by Go. Ask only for booleans, row counts and deployment revision. Reset the test session and retry once after the owner remedies an unmet stage prerequisite. Expected: a verified explanation for the empty response.
3. Select with keyboard and pointer. Confirm street, numbers, postcode, municipality and district fill from the chosen result when provided. Reopen the fields for manual editing and confirm the form can still submit with JavaScript off. Expected: the host never has to repeat values supplied by the result.
4. If reference data and lookup pass, report whether the plain Street label makes the feature discoverable. A design follow-up should make the existing search prominent, preserve editable fields and keep alternatives visually secondary. If a functioning configured candidate returns a reproducibly empty result or fails to fill fields, write the owning file, expected data and a failing fixture in the report for an exact-diff brief. Expected: no guesswork about whether to fix the dataset, Go lookup, or view.

## 5. Do not touch

Application code, staging config, real customer addresses, filing address validation, the existing manual form path, or any external geocoding service. Config and data recovery belong to the owner. No bulk address extraction or external calls.

## 6. Commands

- From `go/` with a disposable database, `go test ./internal/web/properties -run 'Test.*Ruian' -count=1 -v 2>&1 | tail -30`. Expect the applicable lookup tests to execute with no skips for the documented fixture.
- Chromium on staging, 390/768/1280 px. Use the normal form. Record status, count, chosen fields and visible fallback. Capture 390/1280 px screenshots for both locales.

## 7. Acceptance

- [ ] Known staged address returned a suggestion. Selecting it populated all reference fields supplied by the result.
- [ ] Manual entry remains clear when the lookup has no match or JavaScript is off.
- [ ] If still blocked, report the confirmed missing stage prerequisite or owning Go defect, with a reproducible fixture. Do not mark the setup gate ready on a 200 alone.

## 8. Stop and ask

Stop on missing stage data or fixture, missing anchor, two identical failures, or the session cap. Return the next owner action. Do not introduce a new geocoder.

## 9. Report

Write `docs/tasks/2039-report.md` (600 tokens max). Include files, commands and last five lines, acceptance, deviations, questions and owner steps. Record the exact SHA and masked image paths. Use `Status: blocked` when required evidence is missing.

## Risk list (for the reviewer)

For a later patch, review Go route mapping, lookup enablement, address field bindings, mandatory filing fields and form fallback at all viewport widths.

## Owner steps

1. Confirm the staging Go candidate serves the autocomplete route.
2. Confirm that the local RÚIAN data is loaded and give the auditor one public address from it.
3. Rerun lookup on the same candidate after correcting any staging-only prerequisite.