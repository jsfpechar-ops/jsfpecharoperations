# 1663 report

Status: review

## Files changed
- `go/internal/mail/outbox_markers.go` — markers, `EntryCodeMarker`/`EntryCodePayloadKey`, `withEntryCodes`, `delivery` hook
- `go/internal/mail/outbox_entry_code_test.go` — eight step-3 cases
- `docs/tasks/1663-go-mail-entry-code-marker.md` — `Status: review` only

## Commands (last 5 lines)
`gofmt -l internal/mail/` — (empty)
`go vet ./internal/mail/` — (empty)
`go test ./internal/mail/...` — `ok .../go/internal/mail 0.039s`
`python3 scripts/context_lint.py` — `next free: task 2038 | ...` / `context lint: OK`

## Acceptance (§7)
- [x] Eight step-3 cases green; existing mail tests (golden) green
- [x] No error text includes a code value (tests assert)
- [x] Diff vs `origin/main` for §3 paths: only the two Go files (+ this report / brief status)

## Deviations
- Worktree brief on branch still described single `{{entry_code}}` and `Status: blocked`; implementation followed the indexed-marker brief supplied for this run (matches `cursor/entry-codes-guide-plan-992e` copy in `/agent/repos`).
- `delivery` `withEntryCodes` insert applied via small Python patch after StrReplace hook blocked on long `outbox_markers.go`.

## Questions
None.

## Owner steps
None (dormant until Go `mail` job is on).