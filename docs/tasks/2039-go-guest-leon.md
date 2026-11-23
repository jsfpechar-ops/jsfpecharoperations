# 2039: Guest Leon chat in Go (4 routes), with the entry-code pointer

Report: docs/tasks/2039-go-guest-leon-report.md

Status: todo
Depends on: 2037 (branch base), 2035 | Base commit: tip of `cursor/2037-leon-entry-codes-992e` | Branch: cursor/2039-go-guest-leon-992e
Executor: Composer 2.5 (owner 2026-11-22: "composer instead of haiku", limit lifted) | Tier B (guest-facing AI)

## 1. Objective

Port the guest Leon chat (`App/app/routes/guest_leon.py`, 4 routes) to Go so the 2037 entry-code rule (Leon never knows codes; a code question goes to the host with a fixed pointer text) reaches guests without changing Python behaviour. Owner chose "port guest Leon to Go first" (2026-11-22). The Go-vs-Python Leon parity tests must pass again.

## 2. Context

- Routes (Python, behaviour to copy exactly, JSON responses): `GET/POST /l/{token}/{reservation_id}/guide/leon` (stay chat), `GET/POST /g/{token}/leon` (QR chat, cookie `LEON_COOKIE`, `leon.COOKIE_DAYS`). Read `App/app/routes/guest_leon.py` (117 lines) and the `App/app/leon.py` functions it calls (`switched_on`, `stay_chat`, `qr_chat`, `messages`, `answering`, `reply`, `cookie_id_ok`, `new_cookie_id`), plus the gates `_stay_gate`, `_qr_apartment`, `booked_level`, `HARDEN` in `App/app/routes/guest_guide_view.py` and the rate limit used.
- Go already has: Leon core (`go/internal/web/ai/leon_core.go`, `leon_try.go`, `leon_facts.go`, `LeonSystemBlocks`, `LeonValidate` with `Reason: "entry_code"` from 2037), the guest guide view and its gate (`go/internal/web/guest/guide_view.go`, `guide_gate_stub.go`, `guide_page.go`), guest Leon questions (`go/internal/web/guest/leon_questions.go`), guest cookies (`guest_cookie.go` + `guest_cookie_inventory.json`), route registration (`go/cmd/ubyhost-web/register_web_guest_*.go`). Reuse them; do not duplicate the gate.
- Go-first (`docs/context/go-first.md`): Python may change only for parity-test plumbing. Do NOT edit `App/app/leon.py`, `App/app/routes/guest_leon.py` or the Python prompt.
- Prompt drift: `go/internal/web/ai/leon_prompt.txt` is written byte-for-byte from Python `leon.CHARACTER` by `App/scripts/leon_try_golden.py`; 2037 added an ACCESS CODES paragraph to it, which breaks `test_go_ai_leon_try.py::test_leon_try_files_are_current` and Go tests `TestLeonSchemaPromptAndConstantsMatchPython`, `TestLeonGuestCardsAndPromptMatchPython`, `TestLeonTryReplyMatchesPython`. Fix: restore `leon_prompt.txt` to the Python bytes; move the paragraph to a new Go-only embedded file `leon_prompt_access.txt`; Go builds the character as base + "\n\n" + access paragraph. Parity tests compare Python against the Go base (or Go blocks with the access paragraph removed) and separately assert the access paragraph is present in Go's live system block. Comment in the test: the access paragraph is Go-only until Python Leon is removed.
- Fixed guest text for `Reason: "entry_code"` (2037 brief §1): en "For your safety I don't share entry codes. You'll find them in your registration confirmation email and on your stay page. If you can't find them, your host has your question and will reply." cs "Z bezpečnostních důvodů vstupní kódy nesděluji. Najdete je v potvrzovacím e-mailu z registrace a na stránce pobytu. Pokud je nenajdete, hostitel vaši otázku dostal a odpoví vám." Other guest languages: add to the guest Leon catalog (`leon_guest_i18n.json`) with faithful translations for every language the catalog has; the catalog check must pass.
- Production switch: Go serves a path only when listed in `UBYHOST_GO_PATHS` / the Caddy Go path list. Add the 4 paths wherever the repo keeps the Go path list (grep `go_path_entries`, `UBYHOST_GO_PATHS` in `deploy/`, `App/tests/go_stack.py`, `docs/ENVIRONMENT.md`) in the same way earlier guest ports did (look at how `guide_view` paths were added); if the live list is only the server `.env`, write the owner step in the report instead.

## 3. Files

New Go handler file(s) under `go/internal/web/guest/` (e.g. `leon_chat.go` + `leon_chat_test.go`), registration in `go/cmd/ubyhost-web/` (+ registration test), `go/internal/web/ai/leon_prompt.txt` (restore), `go/internal/web/ai/leon_prompt_access.txt` (new), `leon_core.go` (embed + join), the Go parity tests, `App/tests/test_go_ai_leon_try.py` only if needed for the split, `leon_guest_i18n.json` (+ keys file), Go path list files, `docs/plans/go-full-move-remaining.md` row for `guest_leon.py`, `docs/plans/entry-code-external-guide.md` rows 2037/2039, `docs/tasks/2039-go-guest-leon-report.md`. Nothing else.

## 4. Steps

1. Read the Python routes and helpers; list each response shape and status code (200 JSON, 404 `_gone`, 429 rate limit, cookie attributes).
2. Implement the Go handlers with the same JSON, statuses, gates, rate limit, cookie (name, max-age, HttpOnly, Secure, SameSite as Python), CSRF/form handling as the other Go guest POSTs. Leon reply through the existing Go Leon core (same model call path as Go try/stay code). On `Reason == "entry_code"` the guest message text is the fixed text in the guest's language.
3. Register routes; add to the Go path list as in §2.
4. Prompt split per §2; make all Leon parity tests green.
5. Tests: Go handler tests for every status and both chats (history GET, POST answer, POST entry-code question returns the fixed text and stores an open question for the host, gate closed returns 404, Leon off returns 404, cookie set on first QR POST). Keep 2037's tests green.

## 5. Do not touch

Python Leon (`App/app/leon.py`, `guest_leon.py`), production `UBYHOST_GO_PATHS` on the server.

## 6. Commands

From `go/`: `gofmt -l . | tail -5` (empty), `go vet ./... 2>&1 | tail -10`, `go test ./internal/web/... ./cmd/ubyhost-web/ -count=1 2>&1 | tail -30` (needs `UBYHOST_TEST_DATABASE_URL`).
From `App/`: `.venv/bin/python -m pytest tests/test_go_ai_leon_try.py tests/test_guest_cookie*.py -q --tb=short 2>&1 | tail -30` plus any test that lists Go paths (grep `go_path_entries` in tests). Repo root: `python3 scripts/context_lint.py | tail -5`.

## 7. Acceptance

- [ ] 4 routes served by Go, same JSON and statuses as Python (tests).
- [ ] Code question in the guest chat returns the fixed text in en and cs; no code value appears in Leon's system blocks.
- [ ] All Leon parity tests and `test_go_ai_leon_try.py` pass; Python Leon untouched.
- [ ] Go path list updated or owner step written.

## 9. Report

See `docs/tasks/2039-go-guest-leon-report.md`.

## 8. Stop and ask

If the Python behaviour needs a Python change, or the Go Leon core lacks the chat storage (`leon_chat`/messages tables) access and adding it needs a schema change, stop and report.
