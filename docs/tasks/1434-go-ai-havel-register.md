# 1434: Register the Havel routes in the Go web service (dormant until UBYHOST_GO_PATHS names them)

Status: review
Depends on: 1433 | Base commit: the current head of the working branch | Branch: the current branch (one big PR)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B (privacy-relevant outbound request: the assistant's model calls)

**One big PR mode.** Work on the current branch. After each step that changes a file, commit it as `1434 step k` (k is the step number). Never create a branch, never push, never open a PR. Acceptance checks below use `git log --oneline --grep='^1434 step'` and `git show --stat`, not a fixed base commit.

## 1. Objective

Add `go/cmd/ubyhost-web/register_web_ai_havel.go`, which builds the real model client from the environment and registers the Havel routes of brief 1433, with a test that each path reaches its own pattern. Still switched off: no `UBYHOST_GO_PATHS`, Caddy, compose or env change.

## 2. Context

Rules (AGENTS.md): **2 privacy first (this registration builds the real model client; see "PR text")**; 4 no new dependency; 8 green merges auto-deploy, so keep the PR a draft until the owner may switch the paths on (the routes are dormant: Caddy sends no path to Go until `UBYHOST_GO_PATHS` names it).

**All code is pre-written, compiled and tested** over 1433. Sidecars: `docs/tasks/1434-files/<repo path>.txt`. This is the one file that touches `go/cmd/ubyhost-web/`; it is a new file of this thread (`registry.go` documents the pattern, as `register_web_exports.go` does) and `main.go` is not edited. The route function does not use the pool while it builds (`newMux` is called with a nil pool in tests).

**What it does:** `registerWebAIHavel` builds `ai.HavelDeps` from the process environment (`os.LookupEnv`), with `anthropic.NewService(pool, anthropic.ConfigFromEnv(os.LookupEnv))` as the model, and adds the ten patterns of `ai.HavelRoutes` (the four routes and the 405 answers for other methods) under their metrics labels.

**PR text (outbound request, hard rule 2).** This is the line that lets `POST /havel` reach the model API (Anthropic, or Mistral when `UBYHOST_AI_PROVIDER=mistral`) from the Go service, once the owner lists the path. Reason, content and switches are those of briefs 1430 and 1433: one request per host message to answer a how-to question from the guide; the redacted conversation and a small host context; no guest data; refused when `UBYHOST_AI_FEATURES` omits `havel`, the key is unset, the test-email list excludes the host, a host limit is reached or a spend cap (`UBYHOST_AI_MONTHLY_USD_HAVEL`, daily share, key cap) is spent. The Python app makes the same request today; while the path stays on Python, Go makes none. The Go container needs `UBYHOST_ANTHROPIC_API_KEY` (or the Mistral key), `UBYHOST_AI_FEATURES` and the spend variables in its environment: the owner checks that with `docker inspect` before switching (owner steps).


## 3. Files

| Path | Action | What |
|---|---|---|
| `go/cmd/ubyhost-web/register_web_ai_havel.go` | create | registers the four Havel routes with the real model client |
| `go/cmd/ubyhost-web/register_web_ai_havel_test.go` | create | the routes reach their own patterns |
| `docs/tasks/1434-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1434-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root): `git log --oneline --grep='^1433 step 1' | wc -l` prints at least `1`; `ls go/internal/web/ai/havel_handlers.go` exists; `ls go/cmd/ubyhost-web/register_web_ai_havel.go 2>&1 | tail -2` says "No such file"; `grep -cF 'func registerRoutes(fn func(*http.ServeMux, *metrics, *pgxpool.Pool)) {' go/cmd/ubyhost-web/registry.go` prints `1`; `grep -rn '"GET /havel"\|"POST /havel"' go/cmd/ubyhost-web | grep -v register_web_ai_havel | wc -l` prints `0`; `find docs/tasks/1434-files -type f | wc -l` prints `2`. Anything else: STOP (§8).

1. Copy the files (one call, repo root). Run exactly:

   ```bash
   mkdir -p go/cmd/ubyhost-web && cp docs/tasks/1434-files/go/cmd/ubyhost-web/register_web_ai_havel.go.txt go/cmd/ubyhost-web/register_web_ai_havel.go
   mkdir -p go/cmd/ubyhost-web && cp docs/tasks/1434-files/go/cmd/ubyhost-web/register_web_ai_havel_test.go.txt go/cmd/ubyhost-web/register_web_ai_havel_test.go
   ```

   Then check them: `sha256sum go/cmd/ubyhost-web/register_web_ai_havel.go go/cmd/ubyhost-web/register_web_ai_havel_test.go | tail -30`. Every hash must equal this table:

| sha256 | file (sidecar = `docs/tasks/1434-files/<path>.txt`) |
|---|---|
| `91478b45c0818b9c741a6172d693ea423250605e2546c3fb2ad032699869025e` | `go/cmd/ubyhost-web/register_web_ai_havel.go` |
| `0537817432cec8cd3efd1b73056ca7e0eceebfe866e97db04fac655ae7b57fdf` | `go/cmd/ubyhost-web/register_web_ai_havel_test.go` |

   Commit "1434 step 1".

2. Go (from `go/`): `test -z "$(gofmt -l ./internal/web/ai ./cmd/ubyhost-web)" && go build ./... 2>&1 | tail -30 && go vet ./internal/web/ai/ ./cmd/... 2>&1 | tail -30 && go test ./cmd/ubyhost-web/ -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30`. Expected: no output from gofmt, build or vet, then `--- PASS: TestHavelRoutesRegistered`, `--- PASS: TestHavelRegistrationNeedsNoPool`, `--- PASS: TestRoutesRegisterOnce`, `--- PASS: TestDuplicateRouteFails` and one `ok`. A panic `pattern ... conflicts with` means another thread registered a `/havel` pattern: STOP and name it in the report. A FAIL: read the last 30 lines, STOP.

3. The whole package once more with the database (as brief 1433 step 2 starts the server; skip if `UBYHOST_TEST_DATABASE_URL` is set): `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres go test ./internal/web/ai/ ./cmd/ubyhost-web/ -count=1 2>&1 | tail -10` prints two `ok` lines (the first takes about 20 seconds). Without PostgreSQL write "DB tests not run (CI only)". Write the report (§9) and commit "1434 step 3".

## 5. Do not touch

`App/app/` and every other Python file (new files under `App/scripts/` and `App/tests/` named in §3 only), `App/migrations_pg/`, `go/internal/hostweb/` (layout, `i18n.json`), `go/internal/session/`, `go/internal/jobs/`, `go/internal/anthropic/`, `go/internal/mail/`, `go/internal/ubyport/`, `go/cmd/ubyhost-web/main.go`, `registry.go`, `register_web.go` and every other `register_*.go`, `go/go.mod`, `go/go.sum`, `App/tests/conftest.py`, `deploy/`, `.github/`, `docs/ENVIRONMENT.md`, `docs/context/` (status, test-map, decisions, known-issues, workflow), and every file in `go/internal/web/ai/` that is not named in §3 (the guide-editor thread owns the `guide*.go` files there). No env var, no `UBYHOST_GO_PATHS` value, no migration, no dependency. Hard rules 1 to 5, 8 and 9 of AGENTS.md.

## 6. Commands

Steps 2 and 3 above (Go). From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`. Never `go test ./...`.

## 7. Acceptance

- [ ] The 2 sha256 values match §4 step 1.
- [ ] gofmt, build and vet print nothing; TestHavelRoutesRegistered and TestHavelRegistrationNeedsNoPool PASS; the package tests of `internal/web/ai` still PASS (or "CI only" with the reason).
- [ ] `git show --stat --format= $(git log --format=%h --grep='^1434 step') | grep '|' | tail -40` lists only §3 paths; `main.go`, `registry.go` and `register_web.go` are not among them.
- [ ] Commits "1434 step 1" and "1434 step 3"; nothing pushed; the PR stays a draft.

## 8. Stop and ask

As brief 1430 §8 (stop and write the report if an anchor is missing, a sha256 differs, a test fails twice, you reach 25 tool calls or about 50k tokens, a dependency seems needed, a file outside §3 needs a change, §5 would be touched, or a step is unclear). A golden `--check` that prints `stale:` is a STOP: never edit a sidecar, a Python file or a golden to match.

## 9. Report

Write `docs/tasks/1434-report.md` (600 tokens at most) and set this brief's `Status: review`: diff stat, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left (none).

## Risk list (for the reviewer)

`go/cmd/ubyhost-web/register_web_ai_havel.go`: **which model client and which environment it gets** (`anthropic.ConfigFromEnv(os.LookupEnv)` and `anthropic.NewService`: the same switches and caps as the guide import job) and that the function does not touch the pool while building. The route table itself was reviewed in brief 1433.

## Owner steps

Do this only after briefs 1430 to 1434 are merged and deployed, and Havel on Python has run cleanly for a week (the plan deletes Python code only after one clean production week on Go).

1. Check the Go containers have the model settings. On the server run `docker inspect ubyhost-go --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -E 'UBYHOST_(AI_FEATURES|ANTHROPIC_API_KEY|AI_MONTHLY_USD_HAVEL|HAVEL_WEEKLY|HAVEL_MONTHLY|SECRET_KEY|MAIL_BACKEND)=' | sed 's/KEY=.*/KEY=(set)/'`. Every name must be listed with the same value as in the Python container (`UBYHOST_AI_FEATURES` must contain `havel`). A missing name: stop, tell the orchestrator.
2. In the server `.env`, add these paths to `UBYHOST_GO_PATHS` (space-separated, inside the double quotes): `/havel` `/havel/*`. Caddy matches by path only; Python serves no other method on these paths (GET and POST of `/havel`, POST of `/havel/support` and `/havel/not-helped` are all ported here).
3. Run `docker compose up -d` from the deploy folder, then open `/havel` signed in, ask one question and check the answer, the counter and the support card.
4. Rollback: remove the two paths from `UBYHOST_GO_PATHS` and run `docker compose up -d` again.

The Leon setup paths (`/apartments/*/leon/setup`, `/apartments/*/leon/setup/*`) are a separate switch, see the Leon briefs.
