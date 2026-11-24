# 2058 report: Go guest guide parity port

Status: blocked
Executor: Haiku 5.5 (continuation run). Stopped at the 25-call checkpoint after step 3.

## Files changed

- `go/internal/web/ai/leon_core.go` (step 1): `LeonCard.Topic`; exported `LeonCardTitleIn`, `GuideTopicTitle`, `GuideTopicIndex`, `GuideTopics`, `LeonHostFirstName`.
- `go/internal/web/ai/leon_try.go` (step 1): sets `Topic` on the card.
- `go/internal/web/guest/guide_page.go` (step 2): `groupCards(cards, lang)` builds one group per topic in `TOPICS` order with page-language titles; Leon gate `guideLeonOn` (feature `leon` plus `SwitchedOn`); `LeonHost` on the view. Apartment-by-id (2(b)) was already in 4d43a5b.
- `go/internal/web/guest/guide_view.go` (step 3): QR door passes `/g/{token}/leon`.

## Commits

- c0ada26 `2058 step 1`
- 070179a `2058 step 2`
- 83fc074 `2058 step 3`

## Steps

- Step 1: done.
- Step 2 (a) titles and topic groups: done. (b) apartment by id: already in 4d43a5b. (c) Leon gate: done, not yet tested.
- Step 3 QR Leon URL: done.
- Step 4 Leon block in `guide.tmpl`: NOT done.
- Step 5 new tests: NOT done.
- Step 6 two 2056 tests: NOT done.
- Step 7 final checks: partial (see below).
- Step 8 (this report): done.

## Test results

- `go build ./...`: pass.
- `go test ./internal/web/guest/...`: ok.
- `go test ./internal/web/ai/...`: FAIL in `leon_try_test.go:274`. Step 1 added `Topic` to `LeonCard`, and the test compares whole cards against Python fixtures whose topic is empty. Go now sets `Topic` (e.g. `arrival`, `wifi`). Fix in the test file, or drop `Topic` from the comparison. Not in the brief's file list, so not edited.
- Skips: none observed in these runs. `-rs` not run.

## Deviations

- `Done: steps 1 to 3. Left: steps 4 to 8.`
- The `ai` test failure above is an unplanned regression from step 1.

## Owner steps left

- None. The orchestrator should decide how to fix `leon_try_test.go` before the executor resumes at step 4.
