# 2037 report

Status: review (Python prompt/UI and golden parity blocked per owner go-first).

## Files

- `go/internal/web/ai/leon_prompt.txt` — ACCESS CODES paragraph
- `go/internal/web/ai/leon_core.go` — `LeonValidate` sets `reason: entry_code` when `AsksForCode(guestText)` and `host_summary` is exactly `Guest asked for an entry code` (not in brief §3; owner decision)
- `go/internal/web/ai/leon_entry_code_test.go` — `TestLeonPromptNeverHoldsEntryCodes`, `TestLeonValidateEntryCodeReason`

## Blocked (not edited)

- `App/app/leon.py` — guest Leon still served from Python; owner: implement Go, do not edit Python now
- `App/tests/test_leon_entry_code_prompt.py` — twin test waits on Python prompt
- Guest fixed copy for `reason: entry_code` (i18n + `guest_leon.py`) — out of brief §3
- `leon_try_golden` / `TestLeonSchemaPromptAndConstantsMatchPython` — prompt SHA drift until Python CHARACTER matches Go

## §7

- [x] Paragraph in `leon_prompt.txt`; Python twin not updated (blocked)
- [x] Test fails if a code appears in Leon blocks (seed proves absence; host card case documents host text)
- [x] No other prompt text changed besides the new paragraph

## Commands (last 5 lines)

`gofmt -l internal/web/ai/`: (empty)

`go vet ./internal/web/ai/`: (empty)

`go test ./internal/web/ai/ -run Leon`: `FAIL` — `TestLeonSchemaPromptAndConstantsMatchPython`, `TestLeonGuestCardsAndPromptMatchPython`, `TestLeonTryReplyMatchesPython` (prompt SHA / block 0 vs Python). New tests pass; `TestLeonValidateMatchesPython` passes.

`go test … TestLeonPromptNeverHoldsEntryCodes|TestLeonValidateEntryCodeReason`: all PASS

`context_lint.py`: `context lint: OK`

Python §6: `test_leon_entry_code_prompt.py` missing; not run.

## Deviations

- Edited `leon_core.go` (owner: verdict `entry_code`).
- Skipped step 2 golden sync (would copy Python prompt and undo Go paragraph).
- Assert `Your entry codes are on your stay page.` omitted; brief step 1 text has no such sentence — used `ACCESS CODES` / host summary checks instead.
- No PR (executor: no push).

## Final commit

`c882ab67921dce5afad17063c28dc5b9393e1688` (includes `a5ab62738` step 1).