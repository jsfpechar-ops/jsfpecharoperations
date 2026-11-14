# 1432: Go port of Havel's confirm cards and the support mail to the operator

Status: review
Depends on: 1431 | Base commit: the current head of the working branch | Branch: the current branch (one big PR)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B (privacy-relevant outbound request: the assistant's model calls)

**One big PR mode.** Work on the current branch. After each step that changes a file, commit it as `1432 step k` (k is the step number). Never create a branch, never push, never open a PR. Acceptance checks below use `git log --oneline --grep='^1432 step'` and `git show --stat`, not a fixed base commit.

## 1. Objective

Add the confirm cards (stay, cleaning, guest link, new PIN, calendar sync) with their owner-scoped lookups, and the support mail Havel queues for UbyHost's operator, to `go/internal/web/ai`, compared with the real Python through a generated golden (the mail html byte for byte). No route yet.

## 2. Context

Rules (AGENTS.md): 2 privacy first (the support mail carries what the host typed into the support form and the host's last four messages, to UbyHost's own operator address only; no new field; **no outbound HTTP request: the mail goes into `email_outbox` and the existing mail job sends it**); 4 no new dependency; 5 plain PostgreSQL.

**All code is pre-written, compiled and tested** over 1431. Sidecars: `docs/tasks/1432-files/<repo path>.txt`.

**What this ports** (Python mirror): `App/app/havel_actions.py` (all: `prepare`, `NotPrepared`); `App/app/routes/havel.py` 41-60 (`_properties`, `_feed_count`, `_card`'s reads); `dashboard_calendar.overlapping_count` (routes/dashboard_calendar.py 54-61); `guest_slug.link_key` (guest_slug.py 143-148, read side); `App/app/mail_notify.py` 2972-3014 (`build_havel_support`, `havel_support`) with `_shell`, `_block_heading`, `_block_paragraph`, `_block_fact` copied from `go/internal/mail/submission_problem.go` because that package keeps them private (read-only here). The golden holds 36 card cases (every action type, the date window edges, 365 and 366 nights, 60 and 61 guests, a newline after a time which Python's `$` accepts) and 3 mails whose text **and html** are compared byte for byte.

**One deliberate difference (list it in the PR):** `guest_slug.link_key` creates the property's readable slug when it has none (`ensure`, a write). The Go card only reads: with no current slug it shows the permanent token link (`/l/<token>`), which works for ever. A property without a permanent token has no link, as in Python. The next time Python's guest-links page runs it creates the slug.

**Other assumptions:** the ISO week of the idempotency key uses the request clock in UTC (Python's `datetime.now()` is the container's local time); `UBYHOST_MAIL_BACKEND` console or ses switches the mail on, as `mail.mail_enabled`.

**PR text (outbound request, hard rule 2).** This brief adds no request to a third party. It queues one `havel_support` e-mail to `UBYHOST_OPERATOR_EMAIL` (default `support@ubyhost.com`) in `email_outbox`, sent later by the existing mail job (Python today, `go/internal/mail` when that thread moves it). Reason: the host asked UbyHost support for help through Havel's support card, or a limit sent the host's message to support instead of the model. Content: the account e-mail, workspace name, language, page, the host's summary and note and the host's last four messages, exactly as `build_havel_support` does today; the same text twice in one ISO week is one mail; at most three a week per host (brief 1431).


## 3. Files

| Path | Action | What |
|---|---|---|
| `App/scripts/havel_cards_golden.py` | create | writes the cards and support-mail golden from the real Python |
| `App/tests/test_go_ai_havel_cards.py` | create | pytest: the cards golden is current with the Python |
| `go/internal/web/ai/havel_cards.go` | create | confirm cards, property and link lookups |
| `go/internal/web/ai/havel_cards_test.go` | create | parity tests and SQL tests |
| `go/internal/web/ai/havel_mail.go` | create | the support mail to the operator and its outbox row |
| `go/internal/web/ai/testdata/havel_cards_golden.json` | create | Python's cards and mails, generated |
| `docs/tasks/1432-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1432-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root): `git log --oneline --grep='^1431 step 1' | wc -l` prints at least `1`; `ls go/internal/web/ai/havel_store.go go/internal/web/ai/havel_testdb_test.go` both exist; `ls go/internal/web/ai/havel_cards.go 2>&1 | tail -2` says "No such file"; `ls App/tests/test_go_ai_havel.py` exists (1430's file) and `ls App/tests/test_go_ai_havel_cards.py 2>&1 | tail -2` says "No such file"; `grep -cF 'def prepare(action: Dict[str, Any], properties: List[Any], today: date, *, return_to: str,' App/app/havel_actions.py` prints `1`; `grep -cF 'def build_havel_support(' App/app/mail_notify.py` prints `1`; `find docs/tasks/1432-files -type f | wc -l` prints `6`. Anything else: STOP (§8).

1. Copy the files (one call, repo root). Run exactly:

   ```bash
   mkdir -p App/scripts && cp docs/tasks/1432-files/App/scripts/havel_cards_golden.py.txt App/scripts/havel_cards_golden.py
   mkdir -p App/tests && cp docs/tasks/1432-files/App/tests/test_go_ai_havel_cards.py.txt App/tests/test_go_ai_havel_cards.py
   mkdir -p go/internal/web/ai && cp docs/tasks/1432-files/go/internal/web/ai/havel_cards.go.txt go/internal/web/ai/havel_cards.go
   mkdir -p go/internal/web/ai && cp docs/tasks/1432-files/go/internal/web/ai/havel_cards_test.go.txt go/internal/web/ai/havel_cards_test.go
   mkdir -p go/internal/web/ai && cp docs/tasks/1432-files/go/internal/web/ai/havel_mail.go.txt go/internal/web/ai/havel_mail.go
   mkdir -p go/internal/web/ai/testdata && cp docs/tasks/1432-files/go/internal/web/ai/testdata/havel_cards_golden.json.txt go/internal/web/ai/testdata/havel_cards_golden.json
   ```

   Then check them: `sha256sum App/scripts/havel_cards_golden.py App/tests/test_go_ai_havel_cards.py go/internal/web/ai/havel_cards.go go/internal/web/ai/havel_cards_test.go go/internal/web/ai/havel_mail.go go/internal/web/ai/testdata/havel_cards_golden.json | tail -30`. Every hash must equal this table:

| sha256 | file (sidecar = `docs/tasks/1432-files/<path>.txt`) |
|---|---|
| `8a60bfcc080f79153db98492909bd92a2273c10d7a6281b6c9f40aa795cd2138` | `App/scripts/havel_cards_golden.py` |
| `b54a770026f05a241fcf1b54d551ac3e6d8523b7bd8b806c71312747b307806f` | `App/tests/test_go_ai_havel_cards.py` |
| `4c6ad92df86a7838a812434b138ef668b21757d61e6f00cdff87f8425760e24f` | `go/internal/web/ai/havel_cards.go` |
| `3bec72a3887a9d5fe732fa7c9bf8788a6271e3dea710822569e70be7145b779f` | `go/internal/web/ai/havel_cards_test.go` |
| `69a7a118ba5cc31924cb73d639ab63403de9fc06e16549d28e4b21313ea190de` | `go/internal/web/ai/havel_mail.go` |
| `85626b5ae67125b3637486511b6dc0da4bcb72244bd36424e5b6e04384725b02` | `go/internal/web/ai/testdata/havel_cards_golden.json` |

   Commit "1432 step 1".

2. Golden freshness (from `App/`, no database needed): `.venv/bin/python scripts/havel_cards_golden.py --check 2>&1 | tail -5; echo rc=$?` and `.venv/bin/python scripts/havel_golden.py --check 2>&1 | tail -5; echo rc=$?` each print `rc=0` and no `stale:` line; `git status --short | grep -E 'havel|leon' | tail -5` (repo root) prints nothing. A `stale:` line or a changed file: STOP.

3. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, skip to step 4. Else:

   ```bash
   mkdir -p /var/tmp/pgai && chown postgres /var/tmp/pgai && su postgres -c '[ -d /var/tmp/pgai/data/base ] || /usr/lib/postgresql/16/bin/initdb -D /var/tmp/pgai/data -A trust >/dev/null; /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pgai/data -o "-p 55432 -k /var/tmp/pgai" -l /var/tmp/pgai/log -w start' 2>&1 | tail -3
   ```

   Expected: `server started`. Then use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres` in the later steps (if the server already runs from an earlier brief, `su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pgai/data status' | tail -1` says `server is running`; use it). If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, skip this step. No PostgreSQL 16 binaries: write "DB tests not run (CI only)" in the report and run the Go commands without the variable (the DB tests then SKIP; name each skipped test in the report).

4. Go (from `go/`): `test -z "$(gofmt -l ./internal/web/ai)" && go build ./... 2>&1 | tail -30 && go vet ./internal/web/ai/ 2>&1 | tail -30 && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres go test ./internal/web/ai/ -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -40`. Expected: no output from gofmt, build or vet, then `--- PASS:` for all earlier tests and TestHavelCardsMatchPython, TestHavelFieldLabels, TestHavelSupportMailMatchesPython, TestHavelSupportKey, TestHavelSupportOnPostgres, TestHavelLookupsOnPostgres and one `ok`. A FAIL: read the last 30 lines, STOP and paste them. Commit "1432 step 4".

5. Python (from `App/`): `.venv/bin/python -m pytest tests/test_go_ai_havel.py tests/test_go_ai_havel_cards.py -q --tb=short -rs 2>&1 | tail -30` prints `3 passed`, 0 skipped. Write the report (§9) and commit "1432 step 5".

## 5. Do not touch

`App/app/` and every other Python file (new files under `App/scripts/` and `App/tests/` named in §3 only), `App/migrations_pg/`, `go/internal/hostweb/` (layout, `i18n.json`), `go/internal/session/`, `go/internal/jobs/`, `go/internal/anthropic/`, `go/internal/mail/`, `go/internal/ubyport/`, `go/cmd/ubyhost-web/main.go`, `registry.go`, `register_web.go` and every other `register_*.go`, `go/go.mod`, `go/go.sum`, `App/tests/conftest.py`, `deploy/`, `.github/`, `docs/ENVIRONMENT.md`, `docs/context/` (status, test-map, decisions, known-issues, workflow), and every file in `go/internal/web/ai/` that is not named in §3 (the guide-editor thread owns the `guide*.go` files there). No env var, no `UBYHOST_GO_PATHS` value, no migration, no dependency. Hard rules 1 to 5, 8 and 9 of AGENTS.md.

## 6. Commands

Steps 2 (golden), 4 (Go) and 5 (pytest) above. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`. Never `go test ./...`, never the full pytest suite.

## 7. Acceptance

- [ ] The 6 sha256 values match §4 step 1.
- [ ] Both golden `--check` runs print no `stale:` line; `git status --short | grep -E 'havel|leon'` is empty after step 1's commit.
- [ ] gofmt, build and vet print nothing; the six new tests PASS (none skipped, or the skip named with its reason) and the earlier tests still PASS.
- [ ] `pytest tests/test_go_ai_havel.py tests/test_go_ai_havel_cards.py` passes with 3 tests, 0 skipped.
- [ ] `git show --stat --format= $(git log --format=%h --grep='^1432 step') | grep '|' | tail -40` lists only §3 paths.
- [ ] Commits "1432 step 1", "1432 step 4", "1432 step 5", nothing pushed.

## 8. Stop and ask

As brief 1430 §8 (stop and write the report if an anchor is missing, a sha256 differs, a test fails twice, you reach 25 tool calls or about 50k tokens, a dependency seems needed, a file outside §3 needs a change, §5 would be touched, or a step is unclear). A golden `--check` that prints `stale:` is a STOP: never edit a sidecar, a Python file or a golden to match.

## 9. Report

Write `docs/tasks/1432-report.md` (600 tokens at most) and set this brief's `Status: review`: diff stat, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left (none).

## Risk list (for the reviewer)

`go/internal/web/ai/havel_cards.go`: **`HavelPrepareCard`** (a card is built only from an action that `HavelValidate` already passed and only for a property in the host's own list; the card form posts to the existing route, which checks again; against havel_actions.py 47-124: window, nights, guests, e-mail, times, the archived and no-link reasons); `LinkKey` (the deliberate token fallback) and `Apartments` (owner-scoped, `archived_at IS NULL`, `ORDER BY internal_name`). `go/internal/web/ai/havel_mail.go`: **`HavelBuildSupportMail`** (what is mailed to the operator, against mail_notify.py 2976-2997), `HavelSupportKey` and `EnqueueSupport` (recipient, kind, idempotency key, payload; against 3000-3014). `havel_cards_test.go` shows the golden is compared field by field and the mail html byte for byte.

## Owner steps

None: nothing is switched on.
