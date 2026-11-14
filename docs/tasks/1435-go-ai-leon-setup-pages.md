# 1435: Go port of the Leon setup wizard pages: entry, steps and save

Status: review
Depends on: 1433 (Havel pages: its handler gate and test rig) | Base commit: the current head of the working branch | Branch: the current branch (one big PR)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B (privacy-relevant outbound request: the assistant's model calls)

**One big PR mode.** Work on the current branch. After each step that changes a file, commit it as `1435 step k` (k is the step number). Never create a branch, never push, never open a PR. Acceptance checks below use `git log --oneline --grep='^1435 step'` and `git show --stat`, not a fixed base commit.

## 1. Objective

Add the Leon setup wizard pages to `go/internal/web/ai`: `GET /apartments/{id}/leon/setup`, `GET /apartments/{id}/leon/setup/{step}` and `POST /apartments/{id}/leon/setup`, with their facts reads, templates and a golden check against the real Python. No model call; the test-message route is brief 1436. Not registered yet (brief 1437).

## 2. Context

Rules (AGENTS.md): 2 privacy first (**no model call and no outbound request in this brief**; it reads the host's own property rows and writes nothing); 4 no new dependency; 5 plain PostgreSQL, the Python SQL with `$n` placeholders; 6 light mode, the forms work without JavaScript (the wizard posts plain forms); 7 and 10 (browser, geometry, UX gate) belong to the brief that switches the pages on: they stay dormant, and the templates are ports of the existing markup with the same classes, so `static/leon-setup.js` and the CSS need no change.

**All code is pre-written, compiled and tested** next to the merged guide editor (`go/internal/web/ai/guide*.go`; every name of this thread starts with `havel` or `leon`, so no name meets one of the guide files). Sidecars: `docs/tasks/1435-files/<repo path>.txt`. It builds on brief 1433's `HavelDeps`, `HavelStore`, `havelCall.gate/login` and test rig.

**What this ports:** `App/app/routes/leon_setup.py` 19-114 (`_offered`, `_facts`, entry, step page, save); `App/app/leon.py` 442-480 (`host_state`, `setup_step`, terms version); `guest_guide.items`/`progress` (guest_guide.py 152-168, 278-295; the topic and kind order is generated into `leon_catalog.json`); `guest_guide_import.imports`, `in_progress`, `sources_left`, `enabled`; `guest_guide_merge.drafted_count`; `ai.enabled_for_property("leon", id)` (ai.py 107-115); templates `leon_setup/_layout.html`, `switch_on`, `import`, `cards`, `try`, `done`. The test-message route is brief 1436.

**Parity, route by route** (`App/app/routes/leon_setup.py`; same dependency order as Python: CSRF for a POST, then the int path parameter (a bad id is a 422 before the login), then login, then `_offered` (the host's own property, not archived, else 404; Leon offered, else 404)):

| Go | Python | What it does |
|---|---|---|
| `GET /apartments/{id}/leon/setup` | `setup_entry` 47-60 | redirects to the first step still to do (`leon.setup_step`) |
| `GET /apartments/{id}/leon/setup/{step}` | `setup_step_page`, `_step_page` 62-99 | one of switch_on, import, cards, try, done (else 404); while Leon is off or its terms are old every step but the first goes back to switch_on; `Cache-Control: no-store` |
| `POST /apartments/{id}/leon/setup` | `setup_save` 101-114 | `skip_import` to cards, `finish` to done, anything else to the entry |

**Links the wizard makes to routes of the guide-editor thread** (Python serves them until that thread's paths are switched, Go afterwards; neither is in this brief): `POST /apartments/{id}/leon` (the Leon switch, `next=setup`), `POST /apartments/{id}/guide/import`, `GET /apartments/{id}/guide/{item_id}?from=leon`, `/guide`, `/guide/quick`, `/guide/qr`.

**Parity notes:** the card list is `SELECT` of the guide cards with the photo count, ordered by the catalog (a built-in kind takes its topic and place from the catalog; an unknown topic sorts last); progress is live when all five must-have cards are done or skipped; the import list is the newest ten; a failed import does not use a source up. The leaving of the layout's own `Page.Title` is `leon_setup.title` with the property name. Starlette's `HTTPException(404)` body `{"detail":"Not Found"}` and the 422 body for a bad id are reproduced; `HEAD` and other methods answer 405 with `Allow` as FastAPI does.

**Paths:** with brief 1437 these become fully served by Go: `/apartments/*/leon/setup` (GET and POST, as Python) and `/apartments/*/leon/setup/*` (GET of every step, POST only on `try`, as Python; any other method is a 405 in both). **Go-path assumption:** nothing under `/apartments/*/leon` is in the server's `UBYHOST_GO_PATHS` yet; a broad `/apartments/*` entry would send these routes to Go as soon as 1437 deploys (flag it to the owner, brief 1437 owner steps).


## 3. Files

| Path | Action | What |
|---|---|---|
| `App/scripts/leon_golden.py` | create | writes the wizard's data files and golden cases from the real Python |
| `App/tests/test_go_ai_leon.py` | create | pytest: the Go files are current with the Python |
| `go/internal/web/ai/leon_catalog.json` | create | guest guide topics, kinds, must-have cards, generated |
| `go/internal/web/ai/leon_extra.go` | create | empty list of extra routes (brief 1436 replaces it) |
| `go/internal/web/ai/leon_facts.go` | create | property row, card list and progress, imports, wizard state, Leon gate |
| `go/internal/web/ai/leon_facts_test.go` | create | parity tests and SQL tests |
| `go/internal/web/ai/leon_handlers.go` | create | the three wizard routes and the step page |
| `go/internal/web/ai/leon_handlers_test.go` | create | route tests on PostgreSQL |
| `go/internal/web/ai/leon_i18n.json` | create | host strings the pages read, generated |
| `go/internal/web/ai/leon_i18n_keys.txt` | create | keys for the generator |
| `go/internal/web/ai/leon_templates/leon_setup.tmpl` | create | layout and the five step pages |
| `go/internal/web/ai/testdata/leon_golden.json` | create | Python's answers, generated |
| `docs/tasks/1435-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1435-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root): `ls go/internal/web/ai/havel_handlers.go go/internal/web/ai/havel_testdb_test.go` both exist (1433 and 1431 are on this branch); `ls go/internal/web/ai/leon_handlers.go 2>&1 | tail -2` says "No such file"; `grep -cF 'def setup_step(apartment, *, live: bool, checking: int, import_started: bool, import_on: bool) -> str:' App/app/leon.py` prints `1`; `grep -cF 'def _step_page(request: Request, apartment_id: int, step: str, asked: str = "", answer: Optional[Dict[str, Any]] = None):' App/app/routes/leon_setup.py` prints `1`; `find docs/tasks/1435-files -type f | wc -l` prints `12`. Anything else: STOP (§8).

1. Copy the files (one call, repo root). Run exactly:

   ```bash
   mkdir -p App/scripts && cp docs/tasks/1435-files/App/scripts/leon_golden.py.txt App/scripts/leon_golden.py
   mkdir -p App/tests && cp docs/tasks/1435-files/App/tests/test_go_ai_leon.py.txt App/tests/test_go_ai_leon.py
   mkdir -p go/internal/web/ai && cp docs/tasks/1435-files/go/internal/web/ai/leon_catalog.json.txt go/internal/web/ai/leon_catalog.json
   mkdir -p go/internal/web/ai && cp docs/tasks/1435-files/go/internal/web/ai/leon_extra.go.txt go/internal/web/ai/leon_extra.go
   mkdir -p go/internal/web/ai && cp docs/tasks/1435-files/go/internal/web/ai/leon_facts.go.txt go/internal/web/ai/leon_facts.go
   mkdir -p go/internal/web/ai && cp docs/tasks/1435-files/go/internal/web/ai/leon_facts_test.go.txt go/internal/web/ai/leon_facts_test.go
   mkdir -p go/internal/web/ai && cp docs/tasks/1435-files/go/internal/web/ai/leon_handlers.go.txt go/internal/web/ai/leon_handlers.go
   mkdir -p go/internal/web/ai && cp docs/tasks/1435-files/go/internal/web/ai/leon_handlers_test.go.txt go/internal/web/ai/leon_handlers_test.go
   mkdir -p go/internal/web/ai && cp docs/tasks/1435-files/go/internal/web/ai/leon_i18n.json.txt go/internal/web/ai/leon_i18n.json
   mkdir -p go/internal/web/ai && cp docs/tasks/1435-files/go/internal/web/ai/leon_i18n_keys.txt.txt go/internal/web/ai/leon_i18n_keys.txt
   mkdir -p go/internal/web/ai/leon_templates && cp docs/tasks/1435-files/go/internal/web/ai/leon_templates/leon_setup.tmpl.txt go/internal/web/ai/leon_templates/leon_setup.tmpl
   mkdir -p go/internal/web/ai/testdata && cp docs/tasks/1435-files/go/internal/web/ai/testdata/leon_golden.json.txt go/internal/web/ai/testdata/leon_golden.json
   ```

   Then check them: `sha256sum App/scripts/leon_golden.py App/tests/test_go_ai_leon.py go/internal/web/ai/leon_catalog.json go/internal/web/ai/leon_extra.go go/internal/web/ai/leon_facts.go go/internal/web/ai/leon_facts_test.go go/internal/web/ai/leon_handlers.go go/internal/web/ai/leon_handlers_test.go go/internal/web/ai/leon_i18n.json go/internal/web/ai/leon_i18n_keys.txt go/internal/web/ai/leon_templates/leon_setup.tmpl go/internal/web/ai/testdata/leon_golden.json | tail -30`. Every hash must equal this table:

| sha256 | file (sidecar = `docs/tasks/1435-files/<path>.txt`) |
|---|---|
| `1f9fc11c896681190ad728f5dbba9da8c4bdaad29ff51abd6424825974ac9b19` | `App/scripts/leon_golden.py` |
| `6b1ba02fc5840ef93067334b8f038e9c08f7fa19ffa9a86da4fadb272a9f59bb` | `App/tests/test_go_ai_leon.py` |
| `c113ba98ef4676b774d928c8b6d94fda8d9d3d4baa68a584f4f121481d24decc` | `go/internal/web/ai/leon_catalog.json` |
| `2e45acc3b5796a60970d1efef687fdb334112f902d9108ba6c994413ff9f3cba` | `go/internal/web/ai/leon_extra.go` |
| `d27988282cec9df1b66c69741e4c1ad00b1c6cd4cbbb567d92863957fdf3757e` | `go/internal/web/ai/leon_facts.go` |
| `9f7b604a971e2c6383b1eafd3ee1388b9b2c695e7e01d78775a2c1351674cb0e` | `go/internal/web/ai/leon_facts_test.go` |
| `db6c701977ad79d2aa3b70ca551d3e29ad6fc32e28c8bb57ec18818240c49a35` | `go/internal/web/ai/leon_handlers.go` |
| `f2f232d1f4be5c6e2df330901280db8e771f6b6973c81c8191ba0bed39733b45` | `go/internal/web/ai/leon_handlers_test.go` |
| `65bdf9cb96270b94b9a1059381aed1c1558d91e24c93d9123884670ddd82c547` | `go/internal/web/ai/leon_i18n.json` |
| `2711ea47c02a3cbcb0dff6dc239072eb16362dcccc1f5c88c509aa3bc6bbd924` | `go/internal/web/ai/leon_i18n_keys.txt` |
| `a1e06902aa6237763e0c5292e4d91c03ece4a8100d822fbe56d0d6660921b2a9` | `go/internal/web/ai/leon_templates/leon_setup.tmpl` |
| `af0dc2a2e50dce4c06d343f7d1fe48c18013707ad6ef2d0e77b12b783e0aff18` | `go/internal/web/ai/testdata/leon_golden.json` |

   Commit "1435 step 1".

2. Golden freshness (from `App/`, no database needed): `.venv/bin/python scripts/leon_golden.py --check 2>&1 | tail -5; echo rc=$?` prints `rc=0` and no `stale:` line; `git status --short | grep -E 'leon' | tail -5` (repo root) prints nothing. A `stale:` line or a changed file: STOP (Python moved; never edit a sidecar, the Python or the Go to match).

3. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, skip to step 4. Else:

   ```bash
   mkdir -p /var/tmp/pgai && chown postgres /var/tmp/pgai && su postgres -c '[ -d /var/tmp/pgai/data/base ] || /usr/lib/postgresql/16/bin/initdb -D /var/tmp/pgai/data -A trust >/dev/null; /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pgai/data -o "-p 55432 -k /var/tmp/pgai" -l /var/tmp/pgai/log -w start' 2>&1 | tail -3
   ```

   Expected: `server started`. Then use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres` in the later steps (if the server already runs from an earlier brief, `su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pgai/data status' | tail -1` says `server is running`; use it). If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, skip this step. No PostgreSQL 16 binaries: write "DB tests not run (CI only)" in the report and run the Go commands without the variable (the DB tests then SKIP; name each skipped test in the report).

4. Go (from `go/`): `test -z "$(gofmt -l ./internal/web/ai)" && go build ./... 2>&1 | tail -30 && go vet ./internal/web/ai/ 2>&1 | tail -30 && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres go test ./internal/web/ai/ -run 'Leon' -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30`. Expected: no output from gofmt, build or vet, then `--- PASS:` for TestLeonStateMatchesPython, TestLeonProgressMatchesPython, TestLeonReadsOnPostgres, TestLeonGatesAndErrors, TestLeonEntryPicksTheFirstStepToDo, TestLeonStepPages, TestLeonSaveRedirects and one `ok` (about 10 seconds). None may SKIP when the URL is set. A FAIL: read the last 30 lines, STOP and paste them. Commit "1435 step 4".

5. Python (from `App/`): `.venv/bin/python -m pytest tests/test_go_ai_leon.py -q --tb=short -rs 2>&1 | tail -30` prints `1 passed`, 0 skipped. Write the report (§9) and commit "1435 step 5".

## 5. Do not touch

`App/app/` and every other Python file (new files under `App/scripts/` and `App/tests/` named in §3 only), `App/migrations_pg/`, `go/internal/hostweb/` (layout, `i18n.json`), `go/internal/session/`, `go/internal/jobs/`, `go/internal/anthropic/`, `go/internal/mail/`, `go/internal/ubyport/`, `go/cmd/ubyhost-web/main.go`, `registry.go`, `register_web.go` and every other `register_*.go`, `go/go.mod`, `go/go.sum`, `App/tests/conftest.py`, `deploy/`, `.github/`, `docs/ENVIRONMENT.md`, `docs/context/` (status, test-map, decisions, known-issues, workflow), and every file in `go/internal/web/ai/` that is not named in §3 (the guide-editor thread owns the `guide*.go` files there). No env var, no `UBYHOST_GO_PATHS` value, no migration, no dependency. Hard rules 1 to 5, 8 and 9 of AGENTS.md.

## 6. Commands

Steps 2 (golden), 4 (Go) and 5 (pytest) above. From the repo root: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5`. Never `go test ./...`, never the full pytest suite. No screenshots: the pages are not reachable until the owner lists their paths (brief 1437).

## 7. Acceptance

- [ ] The 12 sha256 values match §4 step 1.
- [ ] `leon_golden.py --check` prints no `stale:` line (exit 0).
- [ ] gofmt, build and vet print nothing; the 7 Leon tests named in step 4 PASS, none skipped (or each skip named with its reason).
- [ ] `pytest tests/test_go_ai_leon.py` passes with 0 skipped.
- [ ] `git show --stat --format= $(git log --format=%h --grep='^1435 step') | grep '|' | tail -40` lists only §3 paths.
- [ ] Commits "1435 step 1", "1435 step 4", "1435 step 5"; nothing pushed.

## 8. Stop and ask

As brief 1430 §8 (stop and write the report if an anchor is missing, a sha256 differs, a test fails twice, you reach 25 tool calls or about 50k tokens, a dependency seems needed, a file outside §3 needs a change, §5 would be touched, or a step is unclear). A golden `--check` that prints `stale:` is a STOP: never edit a sidecar, a Python file or a golden to match.

## 9. Report

Write `docs/tasks/1435-report.md` (600 tokens at most) and set this brief's `Status: review`: diff stat, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left (none).

## Risk list (for the reviewer)

`go/internal/web/ai/leon_handlers.go`: **`leonEnter`** (the order CSRF, path id, login, then the host's own property and the Leon gate; a property of another workspace or an archived one must be a 404; tenancy as `access.apartment`), `stepPage` (the redirect to `switch_on` while Leon is off or its terms are old; the done steps), `leonSave`. `go/internal/web/ai/leon_facts.go`: **`Apartment`** (`owner_user_id IS NOT DISTINCT FROM`, `archived_at IS NULL`), **`Offered`** (`UBYHOST_AI_FEATURES` lists `leon`, a key is set, the owner is on the test list, a paused plan is refused; against ai.py 107-115 and billing.py 112-157), `Items`/`LeonOrder`/`LeonProgressOf` (the card order and the live rule), `Imports`/`SourcesLeft`. `leon_templates/leon_setup.tmpl`: the forms and the links to the guide-editor routes.

## Owner steps

None: nothing is switched on.
