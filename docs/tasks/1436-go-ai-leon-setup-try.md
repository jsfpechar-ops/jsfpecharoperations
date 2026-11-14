# 1436: Go port of Leon's setup test message: POST /apartments/{id}/leon/setup/try

Status: todo
Depends on: 1435 | Base commit: the current head of the working branch | Branch: the current branch (one big PR)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B (privacy-relevant outbound request: the assistant's model calls)

**One big PR mode.** Work on the current branch. After each step that changes a file, commit it as `1436 step k` (k is the step number). Never create a branch, never push, never open a PR. Acceptance checks below use `git log --oneline --grep='^1436 step'` and `git show --stat`, not a fixed base commit.

## 1. Objective

Add Leon's guardrails, prompt blocks and `try_reply` to `go/internal/web/ai` and the route `POST /apartments/{id}/leon/setup/try`, compared with the real Python through a generated golden (27 end-to-end runs, the model request checked exactly) and tested on PostgreSQL with a fake model. Not registered yet (brief 1437).

## 2. Context

Rules (AGENTS.md): **2 privacy first: this brief is where Leon's test message reaches the model; see "PR text"**; 4 no new dependency (`golang.org/x/text/cases` is in the module already: `git diff` shows no change to `go/go.mod` or `go/go.sum`); 5 plain PostgreSQL; nothing is stored but the usage ledger of `go/internal/anthropic` and the `rate_limit_event` rows (Python stores the same; no new personal-data field).

**All code is pre-written, compiled and tested** over 1435. Sidecars: `docs/tasks/1436-files/<repo path>.txt`. `leon_extra.go` **replaces** the empty file of brief 1435 (step 0 checks its hash).

| Go | Python | What it does |
|---|---|---|
| `POST /apartments/{id}/leon/setup/try` | `setup_try` 122-149 | 404 unless Leon is switched on with the current terms and the guide is live; one test message, answered as a booked guest would be (`leon.try_reply`); JSON when `Accept` holds `application/json` (keys kind, text, would_ask, blocked, note, cap; compact, UTF-8; `Cache-Control: no-store`), else the try step page with the answer and the question (cut to 500 characters) |

**What it ports:** `App/app/leon.py` 31-290 (redact, fold, smalltalk, noise, guide block, user turn, `validate`), 433-510 (`_fixed`, `_named`, `host_first_name`, `emergency_text`), 667-724 (`try_left`, `try_reply`), `plan_multiplier` 171-181; `guide_facts.for_guest` and `lines`/`answers` (guide_facts.py 100-153). The golden has 18 redaction texts, 14 fold cases, 15 noise cases, 12 names, 34 validation cases, 3 guide scenarios and 27 `try_reply` runs (limits, cap, paused plan, every verdict kind, model failures), compared field by field and the model request (system block hashes, user turn, schema, key, max tokens) exactly.

**Why the helpers:** Python's `re` is Unicode-aware with look-around; the phone and long-ID patterns are loops over `havelFold`'s ASCII mapping (brief 1430), and `leonFold` uses `cases.Fold()` for `str.casefold()`. Known difference (list it in the PR): a non-ASCII decimal digit counts as an ASCII digit in the phone and ID matchers, and a card id such as `c٣` is not matched (Python reads it as 3).

**PR text (outbound request, hard rule 2).** `POST .../leon/setup/try` makes at most one model request per test message, through `anthropic.Service.Call` (feature `leon`, key = the property id): it is refused when `UBYHOST_AI_FEATURES` omits `leon`, the key is unset, the owner is off `UBYHOST_AI_TEST_EMAILS`, the plan is paused, the host has used its 5 test messages in 24 hours, or a spend cap (month, day, key) is spent; greetings, thanks, symbols and over-long text never reach it. The reason: so the host can try Leon on their own guide before guests meet it. The content is the constant character text, the guide cards a booked guest may read (host-only cards and the text of unconfirmed drafts are left out; only their quick-answer lines go) and the host's test message with e-mail addresses, phone numbers and ID-like runs replaced by `[email]`, `[phone]`, `[number]`: **no guest data, no door code unless the host wrote it into a card visible to guests, no host or account e-mail**. The reply is checked by `LeonValidate` and shown as fixed copy except for a validated answer. Nothing is stored. No new recipient; the same request Python makes today. `TestLeonTryRoute` and the golden prove the redaction and the key.


## 3. Files

| Path | Action | What |
|---|---|---|
| `App/scripts/leon_try_golden.py` | create | writes the test-message data files and golden cases from the real Python |
| `App/tests/test_go_ai_leon_try.py` | create | pytest: the Go files are current with the Python |
| `go/internal/web/ai/leon_core.go` | create | redaction, folding, fixed replies, prompt blocks, user turn, guardrail |
| `go/internal/web/ai/leon_extra.go` | create | POST /apartments/{id}/leon/setup/try (replaces 1435's empty file) |
| `go/internal/web/ai/leon_facts_catalog.json` | create | guide_facts.FACTS, generated |
| `go/internal/web/ai/leon_guest_i18n.json` | create | guest strings of the fixed replies and quick answers, generated |
| `go/internal/web/ai/leon_prompt.txt` | create | leon.CHARACTER, generated |
| `go/internal/web/ai/leon_try.go` | create | guest cards, plan multiplier, TryReply |
| `go/internal/web/ai/leon_try_test.go` | create | parity tests, SQL tests and route tests with a fake model |
| `go/internal/web/ai/testdata/leon_try_golden.json` | create | Python's answers, generated |
| `docs/tasks/1436-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1436-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root): `ls go/internal/web/ai/leon_handlers.go go/internal/web/ai/leon_facts.go` both exist; `sha256sum go/internal/web/ai/leon_extra.go | cut -c1-64` prints `2e45acc3b5796a60970d1efef687fdb334112f902d9108ba6c994413ff9f3cba` (brief 1435's file); `ls go/internal/web/ai/leon_core.go 2>&1 | tail -2` says "No such file"; `grep -cF 'def try_reply(apartment, text: str, *, lang: str, host_name: str) -> Dict[str, Any]:' App/app/leon.py` prints `1`; `grep -cF 'def for_guest(apartment_id: int, level: str, lang: str) -> List[Dict[str, Any]]:' App/app/guide_facts.py` prints `1`; `find docs/tasks/1436-files -type f | wc -l` prints `10`. Anything else: STOP (§8).

1. Copy the files (one call, repo root). Run exactly:

   ```bash
   mkdir -p App/scripts && cp docs/tasks/1436-files/App/scripts/leon_try_golden.py.txt App/scripts/leon_try_golden.py
   mkdir -p App/tests && cp docs/tasks/1436-files/App/tests/test_go_ai_leon_try.py.txt App/tests/test_go_ai_leon_try.py
   mkdir -p go/internal/web/ai && cp docs/tasks/1436-files/go/internal/web/ai/leon_core.go.txt go/internal/web/ai/leon_core.go
   mkdir -p go/internal/web/ai && cp docs/tasks/1436-files/go/internal/web/ai/leon_extra.go.txt go/internal/web/ai/leon_extra.go
   mkdir -p go/internal/web/ai && cp docs/tasks/1436-files/go/internal/web/ai/leon_facts_catalog.json.txt go/internal/web/ai/leon_facts_catalog.json
   mkdir -p go/internal/web/ai && cp docs/tasks/1436-files/go/internal/web/ai/leon_guest_i18n.json.txt go/internal/web/ai/leon_guest_i18n.json
   mkdir -p go/internal/web/ai && cp docs/tasks/1436-files/go/internal/web/ai/leon_prompt.txt.txt go/internal/web/ai/leon_prompt.txt
   mkdir -p go/internal/web/ai && cp docs/tasks/1436-files/go/internal/web/ai/leon_try.go.txt go/internal/web/ai/leon_try.go
   mkdir -p go/internal/web/ai && cp docs/tasks/1436-files/go/internal/web/ai/leon_try_test.go.txt go/internal/web/ai/leon_try_test.go
   mkdir -p go/internal/web/ai/testdata && cp docs/tasks/1436-files/go/internal/web/ai/testdata/leon_try_golden.json.txt go/internal/web/ai/testdata/leon_try_golden.json
   ```

   Then check them: `sha256sum App/scripts/leon_try_golden.py App/tests/test_go_ai_leon_try.py go/internal/web/ai/leon_core.go go/internal/web/ai/leon_extra.go go/internal/web/ai/leon_facts_catalog.json go/internal/web/ai/leon_guest_i18n.json go/internal/web/ai/leon_prompt.txt go/internal/web/ai/leon_try.go go/internal/web/ai/leon_try_test.go go/internal/web/ai/testdata/leon_try_golden.json | tail -30`. Every hash must equal this table:

| sha256 | file (sidecar = `docs/tasks/1436-files/<path>.txt`) |
|---|---|
| `1c1dca614d85fa7d9a530aebdc75ef10242d7d5d86d62e5d30ab15270b5cc685` | `App/scripts/leon_try_golden.py` |
| `24a2712ea95a15c73d2ab52f6658ffa700adec7692f5bd904078d7871c102440` | `App/tests/test_go_ai_leon_try.py` |
| `37d399dc2b267bda211a2de685f964f3b66f19d2df2da9efee132eb7727b7c40` | `go/internal/web/ai/leon_core.go` |
| `9d4d38633dde4cbb5707cfd32c1f38d7e0eba019c374d81d1b501587e5d0c103` | `go/internal/web/ai/leon_extra.go` |
| `59e8fb624f15e102c4ffd4b4140aca04d2261d79aa770e2ef37a5e343b1f4086` | `go/internal/web/ai/leon_facts_catalog.json` |
| `fc09df76962800d633b2fd00b10ed70e1720bbada07149bac5ed9424d63dda39` | `go/internal/web/ai/leon_guest_i18n.json` |
| `6fb3bce3afbaaa49ab5b57aa919a15147c6f9720160c0e5a4232443839165308` | `go/internal/web/ai/leon_prompt.txt` |
| `5a7621c62b517a8d7dd5b363cb0085c63a30e41b78935f0285a73e61e76c886c` | `go/internal/web/ai/leon_try.go` |
| `258c480d20f9dc0107adf0aaba0205a649999c267c0643c6403766e53c83a9fd` | `go/internal/web/ai/leon_try_test.go` |
| `b35e0f026dd7fe104096823db54eb7df52cc3e25d0d50084afde2dec1d022bd0` | `go/internal/web/ai/testdata/leon_try_golden.json` |
   (`leon_extra.go` is replaced; the other files are new.)
   Commit "1436 step 1".

2. Golden freshness (from `App/`, no database needed): `.venv/bin/python scripts/leon_try_golden.py --check 2>&1 | tail -5; echo rc=$?` prints `rc=0` and no `stale:` line; `git status --short | grep -E 'leon' | tail -5` (repo root) prints nothing. A `stale:` line: STOP (never edit to match).

3. PostgreSQL (as brief 1435 step 3; skip if `UBYHOST_TEST_DATABASE_URL` is set or the server already runs: `su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pgai/data status' | tail -1`):

   ```bash
   mkdir -p /var/tmp/pgai && chown postgres /var/tmp/pgai && su postgres -c '[ -d /var/tmp/pgai/data/base ] || /usr/lib/postgresql/16/bin/initdb -D /var/tmp/pgai/data -A trust >/dev/null; /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pgai/data -o "-p 55432 -k /var/tmp/pgai" -l /var/tmp/pgai/log -w start' 2>&1 | tail -3
   ```

   Expected: `server started`. Then use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres` in the later steps (if the server already runs from an earlier brief, `su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pgai/data status' | tail -1` says `server is running`; use it). If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, skip this step. No PostgreSQL 16 binaries: write "DB tests not run (CI only)" in the report and run the Go commands without the variable (the DB tests then SKIP; name each skipped test in the report).

4. Go (from `go/`): `test -z "$(gofmt -l ./internal/web/ai)" && go build ./... 2>&1 | tail -30 && go vet ./internal/web/ai/ 2>&1 | tail -30 && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres go test ./internal/web/ai/ -run 'Leon' -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30`. Expected: no output from gofmt, build or vet, then `--- PASS:` for the seven 1435 tests and TestLeonTextRulesMatchPython, TestLeonSchemaPromptAndConstantsMatchPython, TestLeonValidateMatchesPython, TestLeonGuestCardsAndPromptMatchPython, TestLeonTryReplyMatchesPython, TestLeonTryRoute and one `ok` (about 70 seconds: one database per golden case). None may SKIP when the URL is set. A FAIL: read the last 30 lines, STOP and paste them. Commit "1436 step 4".

5. Python (from `App/`): `.venv/bin/python -m pytest tests/test_go_ai_leon.py tests/test_go_ai_leon_try.py -q --tb=short -rs 2>&1 | tail -30` prints `2 passed`, 0 skipped. `git diff --stat -- go/go.mod go/go.sum | tail -2` (repo root) prints nothing. Write the report (§9) and commit "1436 step 5".

## 5. Do not touch

`App/app/` and every other Python file (new files under `App/scripts/` and `App/tests/` named in §3 only), `App/migrations_pg/`, `go/internal/hostweb/` (layout, `i18n.json`), `go/internal/session/`, `go/internal/jobs/`, `go/internal/anthropic/`, `go/internal/mail/`, `go/internal/ubyport/`, `go/cmd/ubyhost-web/main.go`, `registry.go`, `register_web.go` and every other `register_*.go`, `go/go.mod`, `go/go.sum`, `App/tests/conftest.py`, `deploy/`, `.github/`, `docs/ENVIRONMENT.md`, `docs/context/` (status, test-map, decisions, known-issues, workflow), and every file in `go/internal/web/ai/` that is not named in §3 (the guide-editor thread owns the `guide*.go` files there). No env var, no `UBYHOST_GO_PATHS` value, no migration, no dependency. Hard rules 1 to 5, 8 and 9 of AGENTS.md.

## 6. Commands

Steps 2 (golden), 4 (Go) and 5 (pytest) above. From the repo root: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5`. Never `go test ./...`, never the full pytest suite.

## 7. Acceptance

- [ ] The 10 sha256 values match §4 step 1.
- [ ] `leon_try_golden.py --check` prints no `stale:` line (exit 0).
- [ ] gofmt, build and vet print nothing; the 6 new Leon tests PASS (none skipped, or each skip named) and the 1435 tests still PASS.
- [ ] `pytest tests/test_go_ai_leon.py tests/test_go_ai_leon_try.py` passes with 0 skipped; `go/go.mod` and `go/go.sum` unchanged.
- [ ] `git show --stat --format= $(git log --format=%h --grep='^1436 step') | grep '|' | tail -40` lists only §3 paths.
- [ ] Commits "1436 step 1", "1436 step 4", "1436 step 5"; nothing pushed.

## 8. Stop and ask

As brief 1430 §8 (stop and write the report if an anchor is missing, a sha256 differs, a test fails twice, you reach 25 tool calls or about 50k tokens, a dependency seems needed, a file outside §3 needs a change, §5 would be touched, or a step is unclear). A golden `--check` that prints `stale:` is a STOP: never edit a sidecar, a Python file or a golden to match.

## 9. Report

Write `docs/tasks/1436-report.md` (600 tokens at most) and set this brief's `Status: review`: diff stat, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left (none).

## Risk list (for the reviewer)

`go/internal/web/ai/leon_try.go`: **`TryReply`** (the order of the local checks before any model call: paused plan, empty or over 500 characters, smalltalk, noise, the 5-a-day cap, no live guide; what is recorded and when; what is sent: `LeonSystemBlocks`, `LeonUserTurn`, the property id as key, 500 tokens), **`GuestCards`** (visibility `everyone` and `booked` only; the text of a card that is not `done` is left out; against guide_facts.py 136-153). `leon_core.go`: **`LeonRedact`** and the matchers `leonPhones`, `leonLongIDs` (what is replaced before the message leaves), `LeonValidate` (the guardrail), `LeonGuideBlock`. `leon_extra.go`: **the route gate** (404 unless Leon is on with the current terms and the guide is live; CSRF and login come from `leonEnter`) and the JSON shape. `leon_try_test.go` `TestLeonTryRoute` shows the phone number never reaches the model.

## Owner steps

None: nothing is switched on.
