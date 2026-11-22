# 2039 report

Status: review

## §7

- [x] 4 routes on Go (`leon_chat.go` + `leon_questions.go`), JSON gates and POST via `leon_reply.go`
- [x] `Reason: entry_code` → `leon_entry_code_pointer` in all 6 guest languages (Go-only i18n file)
- [x] Leon parity tests green; Python Leon untouched; `leon_prompt.txt` restored from Python bytes
- [x] `guest_handoff.on_new_question` ported (`guesthandoff.OnNewQuestion` after `openLeonQuestion`; alerts + batched host mail)
- [x] DB integration: stay + QR entry-code POST, one host mail, no code in messages/system blocks
- [x] Production paths: owner step (no repo `UBYHOST_GO_PATHS` list)

## Files

- `go/internal/web/ai/leon_prompt.txt` — restored from Python via `leon_try_golden.py`
- `go/internal/web/ai/leon_prompt_access.txt` — ACCESS CODES paragraph (new)
- `go/internal/web/ai/leon_core.go` — `leonCharacterLive`, entry-code i18n embed
- `go/internal/web/ai/leon_reply.go` — `leon.reply` port + handoff hook; NULL-safe chat RETURNING
- `go/internal/web/ai/leon_try.go` — `GuestCards(..., level)`
- `go/internal/web/ai/leon_guest_entry_code_i18n.json` — pointer strings (new)
- `go/internal/web/ai/leon_try_test.go`, `leon_entry_code_test.go` — parity / ACCESS CODES assertions
- `go/internal/web/guest/leon_chat.go`, `leon_chat_test.go` — gates + POST wiring
- `go/internal/web/guest/leon_questions.go` — stay/QR JSON handlers; `handoffRefreshAlert` → `guesthandoff`
- `go/internal/web/guest/leon_entry_code_integration_test.go` — stay/QR + outbox (new)
- `go/internal/guesthandoff/notify.go` — `OnNewQuestion`, `RefreshAlert`, `OpenCounts` (new)
- `go/internal/mail/guest_question_host.go`, `guest_question_host_test.go` — host mail bytes vs Python (new)
- `go/internal/web/guest/guide_page.go`, `guide_photo.go` — `GuestCards` level arg
- `docs/plans/go-full-move-remaining.md`, `entry-code-external-guide.md`
- `docs/tasks/2039-go-guest-leon.md` — lint sections

## Commands (last lines)

`gofmt -l .`: (empty after `gofmt -w .`)

`go vet ./internal/web/... ./internal/mail/... ./cmd/ubyhost-web/`: (empty)

`go test ./internal/web/... ./internal/mail/... ./cmd/ubyhost-web/ -count=1`: all PASS (as `postgres`, `UBYHOST_TEST_DATABASE_URL=postgresql:///ubyhost_c9?host=/var/run/postgresql`)

`pytest tests/test_go_ai_leon_try.py tests/test_go_leon_questions_golden.py`: 2 passed

`context_lint.py`: OK

DB: `UBYHOST_TEST_DATABASE_URL=postgresql:///ubyhost_c9?host=/var/run/postgresql` as `postgres` user.

## Deviations

- Entry-code guest copy in `leon_guest_entry_code_i18n.json`, not Python `leon_guest_i18n.json` (golden parity).
- Brief `test_guest_cookie*.py`: no matching files; privacy cookie tests unchanged.
- `leon_reply.go` omits some `leon.py` log lines; behaviour matches JSON contract.

## Owner steps (production)

1. On the server, add these four entries to `UBYHOST_GO_PATHS` (same style as other guest ports):  
   `/l/*/guide/leon`  
   `/l/*/guide/leon/*`  
   `/g/*/leon`  
   `/g/*/leon/*`  
   (Caddy prefix rules — match how guide view paths were added.)
2. Redeploy Go web after merge; smoke one stay Leon POST and one QR Leon POST on staging.
3. Run `scripts/go_switch_preflight.sh` with the new path fragment before enabling on production.

## Go paths in repo

None (dormant registration only; cutover is owner env).