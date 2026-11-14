# 1433: Go port of the Havel pages: GET /havel, POST /havel, POST /havel/support, POST /havel/not-helped

Status: review
Depends on: 1432 | Base commit: the current head of the working branch | Branch: the current branch (one big PR)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B (privacy-relevant outbound request: the assistant's model calls)

**One big PR mode.** Work on the current branch. After each step that changes a file, commit it as `1433 step k` (k is the step number). Never create a branch, never push, never open a PR. Acceptance checks below use `git log --oneline --grep='^1433 step'` and `git show --stat`, not a fixed base commit.

## 1. Objective

Add the four Havel routes, their templates and the page context to `go/internal/web/ai`, following `App/app/routes/havel.py` line by line, tested on PostgreSQL with a fake model (the real API is never called). Not registered yet (brief 1434), so nothing can reach them.

## 2. Context

Rules (AGENTS.md): **2 privacy first: this brief is where the model request is made. It sends exactly what `HavelBuildMessages` builds (brief 1430), nothing else; see "PR text"**; 4 no new dependency; 5 plain PostgreSQL; 6 light mode only, the forms work without JavaScript (every form posts to a real route and the page re-renders); 7 and 10 (browser, geometry and UX gate) are for the brief that switches a page on: these pages stay dormant, and the templates are ports of existing markup with the same CSS classes and `data-` attributes, so `static/havel.js` and the CSS need no change.

**All code is pre-written, compiled and tested** over 1432. Sidecars: `docs/tasks/1433-files/<repo path>.txt`.

**Parity, route by route** (`App/app/routes/havel.py`; every handler follows its Python function line by line, same permission order: CSRF (`protect_host_post`, POST only), then login, then the feature switch):

| Go | Python | What it does |
|---|---|---|
| `GET /havel` (`pageHandler`) | `havel_page` 136-155 | topic, q (letters and `_`, 30), page (default `guide`), `ask`, `return_to` through `safe_local_path`; quick-help layers, no model; with header `X-Havel: 1` the thread fragment |
| `POST /havel` (`sendHandler`) | `havel_send` 179-273 | message over 600 characters is an error text; greeting and thanks are local; 6 exchanges per conversation (the 7th goes to support); AI off shows `havel.off`; a limit shows its text, counts `limit_hit` and forwards week and month limits to support; otherwise one model call, counted (burst, week, month), gap log for `escalate` and `fail`, refusals counted, the action card or the fallback link; budget `month` shows `havel.off`, any other budget reason `havel.resting`, both forwarded as `budget_<reason>` |
| `POST /havel/support` (`supportHandler`) | `havel_support` 275-311 | summary 800 and note 600 characters; weekly cap of 3 shows the operator address; empty form shows `havel.support.empty`; else the mail is queued (1432), counted, stat `support_sent` |
| `POST /havel/not-helped` (`notHelpedHandler`) | `havel_not_helped` 313-331 | the last question of the signed history goes to the gap log, 5 a day per host |

Other methods on these paths answer 405 `{"detail":"Method Not Allowed"}` with `Allow`, as Starlette does (a HEAD on `/havel` too). `POST /havel` reads urlencoded and multipart bodies (`havel.js` posts `FormData`); multipart is parsed before the CSRF check, as `go/internal/web/stayfees` does. The history field is signed with the session secret and the account id (brief 1430); a bad signature empties the history and never fails the request.

**The one thing the layout cannot do (read-only package, so worked around, say so in the PR):** the Python fragment answer (`_havel_fragment.html`, header `X-Havel: 1`, used by every panel interaction) is a bare HTML fragment, but `layout.Render` always wraps a page in the shell. `renderFragment` renders the fragment as the body of the page template `havel.fragment_page` between two marker elements, cuts it out, passes on the `Set-Cookie` the layout set (the CSRF nonce) and writes only the fragment. Cost: the shell's own reads run once more per panel request. A `layout.RenderFragment` in `go/internal/hostweb/layout` would remove this; ask the layout owner.

**Other parity notes:** `date.today()` in the card is the Prague date here (Python: the container's local date; only the window edge differs); owner scope is the workspace id, as `access.apartments`; the language is `hostweb.Lang`; the account e-mail comes from `user_account` (the session carries none); catalog texts are HTML-escaped by `html/template` as Jinja does (`'` becomes `&#39;`).

**PR text (outbound request, hard rule 2).** `POST /havel` makes at most one model request per host message, through `anthropic.Service.Call` (feature `havel`): it is refused when `UBYHOST_AI_FEATURES` does not list `havel`, when the provider key is unset, when `UBYHOST_AI_TEST_EMAILS` is set and the host is not on it, when a host limit is reached (burst 5 per 10 minutes, 8 a week and 15 a month times the plan multiplier, refusals) and when the month, day or key spend cap of the service is spent. The reason: to answer the host's how-to question from the guide. The content is the redacted question and conversation and the host context listed in brief 1430's PR text: **no guest data, door code, address, phone number or user id**. `TestHavelAnswerSendsOnlyRedactedFacts` sends a message with an e-mail address and a phone number and asserts that neither, nor the account e-mail, the workspace name, the PIN or the link token, reaches the model. No new recipient; the same request Python makes today.


## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/ai/havel_handlers.go` | create | GET /havel, POST /havel, POST /havel/support, POST /havel/not-helped |
| `go/internal/web/ai/havel_handlers_test.go` | create | route tests on PostgreSQL with a fake model |
| `go/internal/web/ai/havel_pages.go` | create | thread items, blocks, page context, safe_local_path |
| `go/internal/web/ai/havel_pages_test.go` | create | parity tests of the helpers |
| `go/internal/web/ai/havel_templates/havel.tmpl` | create | page, fragment, composer form, support form |
| `go/internal/web/ai/havel_templates/havel_thread.tmpl` | create | thread and confirm card |
| `go/internal/web/ai/havel_templates/havel_topics.tmpl` | create | quick-help topics |
| `docs/tasks/1433-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1433-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root): `git log --oneline --grep='^1432 step 1' | wc -l` prints at least `1`; `ls go/internal/web/ai/havel_cards.go go/internal/web/ai/havel_mail.go` both exist; `ls go/internal/web/ai/havel_handlers.go 2>&1 | tail -2` says "No such file"; `grep -cF 'async def havel_send(request: Request):' App/app/routes/havel.py` prints `1`; `grep -cF 'async def havel_not_helped(request: Request):' App/app/routes/havel.py` prints `1`; `grep -c 'data-havel-form' App/app/templates/_havel_form.html` prints `1`; `find docs/tasks/1433-files -type f | wc -l` prints `7`. Anything else: STOP (§8).

1. Copy the files (one call, repo root). Run exactly:

   ```bash
   mkdir -p go/internal/web/ai && cp docs/tasks/1433-files/go/internal/web/ai/havel_handlers.go.txt go/internal/web/ai/havel_handlers.go
   mkdir -p go/internal/web/ai && cp docs/tasks/1433-files/go/internal/web/ai/havel_handlers_test.go.txt go/internal/web/ai/havel_handlers_test.go
   mkdir -p go/internal/web/ai && cp docs/tasks/1433-files/go/internal/web/ai/havel_pages.go.txt go/internal/web/ai/havel_pages.go
   mkdir -p go/internal/web/ai && cp docs/tasks/1433-files/go/internal/web/ai/havel_pages_test.go.txt go/internal/web/ai/havel_pages_test.go
   mkdir -p go/internal/web/ai/havel_templates && cp docs/tasks/1433-files/go/internal/web/ai/havel_templates/havel.tmpl.txt go/internal/web/ai/havel_templates/havel.tmpl
   mkdir -p go/internal/web/ai/havel_templates && cp docs/tasks/1433-files/go/internal/web/ai/havel_templates/havel_thread.tmpl.txt go/internal/web/ai/havel_templates/havel_thread.tmpl
   mkdir -p go/internal/web/ai/havel_templates && cp docs/tasks/1433-files/go/internal/web/ai/havel_templates/havel_topics.tmpl.txt go/internal/web/ai/havel_templates/havel_topics.tmpl
   ```

   Then check them: `sha256sum go/internal/web/ai/havel_handlers.go go/internal/web/ai/havel_handlers_test.go go/internal/web/ai/havel_pages.go go/internal/web/ai/havel_pages_test.go go/internal/web/ai/havel_templates/havel.tmpl go/internal/web/ai/havel_templates/havel_thread.tmpl go/internal/web/ai/havel_templates/havel_topics.tmpl | tail -30`. Every hash must equal this table:

| sha256 | file (sidecar = `docs/tasks/1433-files/<path>.txt`) |
|---|---|
| `124c4c438e233a9a397babe4517e9801b57c9e8800d5ff2a890becf3c36d8950` | `go/internal/web/ai/havel_handlers.go` |
| `b9dda0a6052aee61de2179f573ab264d9b081b4b69012ba0fe70873d54ee6bd3` | `go/internal/web/ai/havel_handlers_test.go` |
| `fa3202317ba19b4df188a5c615cca5aee06b2ef50b3892c90c371ba10d3c96dd` | `go/internal/web/ai/havel_pages.go` |
| `079a80b15bb6bfbd9f995c3a5c6cb430482cbd3d66422c0a3ea60bcaf4f7d71e` | `go/internal/web/ai/havel_pages_test.go` |
| `12522d9ed6e47aa240497b34b7026554b29284fbc011d99ad8616fa598f5a53e` | `go/internal/web/ai/havel_templates/havel.tmpl` |
| `1b21289db659024521ca4e2217e26e2d6ef4fbbb35a79f26f28d6b08d9f6d31d` | `go/internal/web/ai/havel_templates/havel_thread.tmpl` |
| `f29f242211217d4c440f7caf0871888124c74c9fb10d2cf6198cc82d6e9d0c82` | `go/internal/web/ai/havel_templates/havel_topics.tmpl` |

   Commit "1433 step 1".

2. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, skip to step 3. Else:

   ```bash
   mkdir -p /var/tmp/pgai && chown postgres /var/tmp/pgai && su postgres -c '[ -d /var/tmp/pgai/data/base ] || /usr/lib/postgresql/16/bin/initdb -D /var/tmp/pgai/data -A trust >/dev/null; /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pgai/data -o "-p 55432 -k /var/tmp/pgai" -l /var/tmp/pgai/log -w start' 2>&1 | tail -3
   ```

   Expected: `server started`. Then use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres` in the later steps (if the server already runs from an earlier brief, `su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pgai/data status' | tail -1` says `server is running`; use it). If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, skip this step. No PostgreSQL 16 binaries: write "DB tests not run (CI only)" in the report and run the Go commands without the variable (the DB tests then SKIP; name each skipped test in the report).

3. Go (from `go/`): `test -z "$(gofmt -l ./internal/web/ai)" && go build ./... 2>&1 | tail -30 && go vet ./internal/web/ai/ 2>&1 | tail -30 && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres go test ./internal/web/ai/ -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -50`. Expected: no output from gofmt, build or vet, then `--- PASS:` for all earlier tests and TestHavelSignedOutAndCSRF, TestHavelPageGet, TestHavelFragmentGet, TestHavelOffShowsSupportOnly, TestHavelLocalReplyCostsNothing, TestHavelAnswerSendsOnlyRedactedFacts, TestHavelFragmentPostCarriesHistoryAndState, TestHavelGuardrailFailStoresOnlyTheRedactedQuestion, TestHavelRefusalsPauseTheHost, TestHavelLimitsForwardToSupport, TestHavelBurstDoesNotForward, TestHavelBudgetAndDisabledErrors, TestHavelTooLongAndConversationCap, TestHavelActionCard, TestHavelSupportRoute, TestHavelNotHelpedRoute, TestHavelLanguageComesFromTheCookie, TestHavelPageHelpersMatchPython, TestHavelSplitLines, TestHavelCardDateLabels and one `ok` (about 20 seconds). None may SKIP when the URL is set. A FAIL: read the last 30 lines, STOP and paste them. Write the report (§9) and commit "1433 step 3".

## 5. Do not touch

`App/app/` and every other Python file (new files under `App/scripts/` and `App/tests/` named in §3 only), `App/migrations_pg/`, `go/internal/hostweb/` (layout, `i18n.json`), `go/internal/session/`, `go/internal/jobs/`, `go/internal/anthropic/`, `go/internal/mail/`, `go/internal/ubyport/`, `go/cmd/ubyhost-web/main.go`, `registry.go`, `register_web.go` and every other `register_*.go`, `go/go.mod`, `go/go.sum`, `App/tests/conftest.py`, `deploy/`, `.github/`, `docs/ENVIRONMENT.md`, `docs/context/` (status, test-map, decisions, known-issues, workflow), and every file in `go/internal/web/ai/` that is not named in §3 (the guide-editor thread owns the `guide*.go` files there). No env var, no `UBYHOST_GO_PATHS` value, no migration, no dependency. Hard rules 1 to 5, 8 and 9 of AGENTS.md.

## 6. Commands

Step 3 above (Go). From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`. Never `go test ./...`, never the full pytest suite. No screenshots: the pages are not reachable until the owner lists their paths (brief 1434).

## 7. Acceptance

- [ ] The 7 sha256 values match §4 step 1.
- [ ] gofmt, build and vet print nothing; the 20 new tests PASS, none skipped (or each skip named with its reason), and the earlier tests still PASS.
- [ ] `git show --stat --format= $(git log --format=%h --grep='^1433 step') | grep '|' | tail -40` lists only §3 paths.
- [ ] `git show --stat --format= $(git log --format=%h --grep='^1433 step') | grep -cE 'go/internal/(hostweb|session|anthropic)/|go.mod'` prints `0`.
- [ ] Commits "1433 step 1" and "1433 step 3", nothing pushed.

## 8. Stop and ask

As brief 1430 §8 (stop and write the report if an anchor is missing, a sha256 differs, a test fails twice, you reach 25 tool calls or about 50k tokens, a dependency seems needed, a file outside §3 needs a change, §5 would be touched, or a step is unclear). A golden `--check` that prints `stale:` is a STOP: never edit a sidecar, a Python file or a golden to match.

## 9. Report

Write `docs/tasks/1433-report.md` (600 tokens at most) and set this brief's `Status: review`: diff stat, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left (none).

## Risk list (for the reviewer)

`go/internal/web/ai/havel_handlers.go`: **`sendHandler`** (the whole decision tree of `havel_send`: which message reaches the model and which does not; the order local reply, conversation cap, AI switch, limit state, model call; what is counted and when; the forward rules `limit_week`, `limit_month`, `conversation`, `budget_*`; against havel.py 179-273); **`enter`** (CSRF before login, then the multipart parse); **`pageContext` in havel_pages.go** (the support form, the topics, the masked reply address); `supportHandler` and `notHelpedHandler` (caps 3 and 5, truncation 800 and 600); `renderFragment` (the marker workaround; the CSRF cookie must be passed on). Templates: `havel_thread.tmpl` (the card form posts to `/reservations`, `/cleaning/events`, `/sync` or `/apartments/{id}/regenerate-pin` with a CSRF token; the not-helped and next forms), `havel_topics.tmpl`. `TestHavelAnswerSendsOnlyRedactedFacts` is the privacy proof: read it.

## Owner steps

None: nothing is switched on.
