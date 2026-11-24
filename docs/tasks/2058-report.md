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
- 9c8f440 `2058 step 1b` (Topic moved out of LeonCard into GuideCard; fixes leon_try_test)
- 070179a `2058 step 2`
- 62b9413 `2058 step 2` (guide_page.go: GuestGuideCards, groupCards on GuideCard, Leon gate)
- 83fc074 `2058 step 3`

Continuation 2 stopped at the 25-call checkpoint after step 2 (the step 3 one-line change is not yet applied; the step 2 commit is 62b9413 and builds).

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
- `go test ./internal/web/ai/...` (after 1b): ok, `leon_try_test.go` and fixtures unchanged. `Topic` is no longer in `LeonCard`; `LeonStore.GuestGuideCards` returns `GuideCard{Card, Topic}`, and `GuestCards` is a wrapper that drops the topic.
- After step 2 (`UBYHOST_TEST_DATABASE_URL` set): `go test ./internal/web/guest/... ./internal/web/ai/... -count=1` ok for both packages. `go build ./...` not re-run after step 2 (guest package builds).
- Skips: not counted (no `-rs` / `-v` run).

## Deviations

- `Done: steps 1 to 3. Left: steps 4 to 8.`
- The `ai` test failure above is an unplanned regression from step 1.

## Owner steps left

- None. The orchestrator should decide how to fix `leon_try_test.go` before the executor resumes at step 4.
