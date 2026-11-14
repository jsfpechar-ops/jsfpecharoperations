# 1437: Register the Leon setup wizard routes with the Havel ones (dormant until UBYHOST_GO_PATHS names them)

Status: todo
Depends on: 1436 | Base commit: the current head of the working branch | Branch: the current branch (one big PR)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B (privacy-relevant outbound request: the assistant's model calls)

**One big PR mode.** Work on the current branch. After each step that changes a file, commit it as `1437 step k` (k is the step number). Never create a branch, never push, never open a PR. Acceptance checks below use `git log --oneline --grep='^1437 step'` and `git show --stat`, not a fixed base commit.

## 1. Objective

Replace brief 1434's registration file and its test so that `go/cmd/ubyhost-web` also registers the Leon wizard routes of briefs 1435 and 1436, with a test that each path reaches its own pattern. Still switched off.

## 2. Context

Rules (AGENTS.md): **2 privacy first (the Leon wizard's test message can reach the model once the owner lists the paths; see "PR text")**; 4 no new dependency; 8 green merges auto-deploy, so these registrations are dormant until `UBYHOST_GO_PATHS` names the paths.

**All code is pre-written, compiled and tested** over 1436. Sidecars: `docs/tasks/1437-files/<repo path>.txt`. Both files **replace** brief 1434's (step 0 checks their hashes); the registration function still builds the same model client and does not touch the pool.

**What changes:** `registerWebAIHavel` now adds `ai.LeonRoutes(deps)` after `ai.HavelRoutes(deps)`: `GET` and `POST /apartments/{id}/leon/setup`, `GET /apartments/{id}/leon/setup/{step}`, `POST /apartments/{id}/leon/setup/try` and the 405 answers for other methods. The test adds seven patterns. The route table of the guide-editor thread (`register_web_ai_guide.go`) has no pattern under `/apartments/{id}/leon/setup`; `go test` of the whole `cmd/ubyhost-web` package fails with a pattern conflict if one appears.

**PR text (outbound request, hard rule 2).** Same request, same reason, same content and switches as brief 1436: Leon's test message, at most 5 a day per property, redacted, from the host's own guide, refused unless `UBYHOST_AI_FEATURES` lists `leon`. The Go container needs `UBYHOST_ANTHROPIC_API_KEY` (or the Mistral key), `UBYHOST_AI_FEATURES` and the spend variables; the owner checks them before switching.

**Paths that become fully served by Go** (Python serves no other method on them): `/havel` (GET, POST), `/havel/support` (POST), `/havel/not-helped` (POST), `/apartments/*/leon/setup` (GET, POST) and `/apartments/*/leon/setup/*` (GET of each step, POST only on `try`; other methods are 405 in both). **No new route goes live on deploy** unless the server's `UBYHOST_GO_PATHS` already holds a broad entry such as `/apartments/*` or `/havel*` (not readable from the repo; assumed absent). The Havel confirm cards post to `/reservations`, `/cleaning/events`, `/sync` and `/apartments/{id}/regenerate-pin`, which stay where they are. The wizard links to `/apartments/{id}/leon` (POST, `next=setup`) and `/apartments/{id}/guide/import`, served by the guide-editor thread.


## 3. Files

| Path | Action | What |
|---|---|---|
| `go/cmd/ubyhost-web/register_web_ai_havel.go` | create | replaces 1434's file: also registers the Leon wizard routes |
| `go/cmd/ubyhost-web/register_web_ai_havel_test.go` | create | replaces 1434's file: also checks the Leon patterns |
| `docs/tasks/1437-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1437-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root): `git log --oneline --grep='^1436 step 1' | wc -l` prints at least `1`; `ls go/internal/web/ai/leon_try.go go/cmd/ubyhost-web/register_web_ai_havel.go` both exist; `sha256sum go/cmd/ubyhost-web/register_web_ai_havel.go | cut -c1-64` prints `91478b45c0818b9c741a6172d693ea423250605e2546c3fb2ad032699869025e`; `sha256sum go/cmd/ubyhost-web/register_web_ai_havel_test.go | cut -c1-64` prints `0537817432cec8cd3efd1b73056ca7e0eceebfe866e97db04fac655ae7b57fdf`; `find docs/tasks/1437-files -type f | wc -l` prints `2`. Anything else: STOP (§8).

1. Copy the files (one call, repo root). Run exactly:

   ```bash
   mkdir -p go/cmd/ubyhost-web && cp docs/tasks/1437-files/go/cmd/ubyhost-web/register_web_ai_havel.go.txt go/cmd/ubyhost-web/register_web_ai_havel.go
   mkdir -p go/cmd/ubyhost-web && cp docs/tasks/1437-files/go/cmd/ubyhost-web/register_web_ai_havel_test.go.txt go/cmd/ubyhost-web/register_web_ai_havel_test.go
   ```

   Then check them: `sha256sum go/cmd/ubyhost-web/register_web_ai_havel.go go/cmd/ubyhost-web/register_web_ai_havel_test.go | tail -30`. Every hash must equal this table:

| sha256 | file (sidecar = `docs/tasks/1437-files/<path>.txt`) |
|---|---|
| `d0d69c6c6b21ed41f3253ed5dbcc151b0049b7830b6e4dfc96bb355566e5a166` | `go/cmd/ubyhost-web/register_web_ai_havel.go` |
| `5a018b7c17e25d606878c3ebff9572c511027e247ad348d8a134aeee33194a80` | `go/cmd/ubyhost-web/register_web_ai_havel_test.go` |

   Commit "1437 step 1".

2. Go (from `go/`): `test -z "$(gofmt -l ./internal/web/ai ./cmd/ubyhost-web)" && go build ./... 2>&1 | tail -30 && go vet ./internal/web/ai/ ./cmd/... 2>&1 | tail -30 && go test ./cmd/ubyhost-web/ -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30`. Expected: no output from gofmt, build or vet, then `--- PASS: TestHavelRoutesRegistered`, `--- PASS: TestHavelRegistrationNeedsNoPool`, `--- PASS: TestRoutesRegisterOnce` and one `ok`. A panic `pattern ... conflicts with` means another thread registered a pattern under `/havel` or `/apartments/{id}/leon/setup`: STOP and name it in the report. Commit "1437 step 2".

3. The whole ai package once with the database (start the server as brief 1435 step 3, or use `UBYHOST_TEST_DATABASE_URL` if set): `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres go test ./internal/web/ai/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -10` prints `ok` for `internal/web/ai` (about 2 minutes with the guide editor's tests) and `ok` for `cmd/ubyhost-web`. Without PostgreSQL write "DB tests not run (CI only)". Write the report (§9) and commit "1437 step 3".

## 5. Do not touch

`App/app/` and every other Python file (new files under `App/scripts/` and `App/tests/` named in §3 only), `App/migrations_pg/`, `go/internal/hostweb/` (layout, `i18n.json`), `go/internal/session/`, `go/internal/jobs/`, `go/internal/anthropic/`, `go/internal/mail/`, `go/internal/ubyport/`, `go/cmd/ubyhost-web/main.go`, `registry.go`, `register_web.go` and every other `register_*.go`, `go/go.mod`, `go/go.sum`, `App/tests/conftest.py`, `deploy/`, `.github/`, `docs/ENVIRONMENT.md`, `docs/context/` (status, test-map, decisions, known-issues, workflow), and every file in `go/internal/web/ai/` that is not named in §3 (the guide-editor thread owns the `guide*.go` files there). No env var, no `UBYHOST_GO_PATHS` value, no migration, no dependency. Hard rules 1 to 5, 8 and 9 of AGENTS.md.

## 6. Commands

Steps 2 and 3 above (Go). From the repo root: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5`. Never `go test ./...`.

## 7. Acceptance

- [ ] The 2 sha256 values match §4 step 1.
- [ ] gofmt, build and vet print nothing; TestHavelRoutesRegistered and TestHavelRegistrationNeedsNoPool PASS; the ai package tests PASS (or "CI only" with the reason).
- [ ] `git show --stat --format= $(git log --format=%h --grep='^1437 step') | grep '|' | tail -40` lists only §3 paths.
- [ ] Commits "1437 step 1", "1437 step 2", "1437 step 3"; nothing pushed.

## 8. Stop and ask

As brief 1430 §8 (stop and write the report if an anchor is missing, a sha256 differs, a test fails twice, you reach 25 tool calls or about 50k tokens, a dependency seems needed, a file outside §3 needs a change, §5 would be touched, or a step is unclear). A golden `--check` that prints `stale:` is a STOP: never edit a sidecar, a Python file or a golden to match.

## 9. Report

Write `docs/tasks/1437-report.md` (600 tokens at most) and set this brief's `Status: review`: diff stat, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left (none).

## Risk list (for the reviewer)

`go/cmd/ubyhost-web/register_web_ai_havel.go`: which model client and environment it gets, that it adds exactly `HavelRoutes` and `LeonRoutes`, and that it does not touch the pool while building. The route tables were reviewed in briefs 1433 and 1435.

## Owner steps

Do this only after briefs 1430 to 1437 are merged and deployed, the guide-editor routes of `/apartments/*/leon` and `/apartments/*/guide/*` are on Go (or still on Python), and Havel and the Leon wizard on Python have run cleanly for a week.

1. Check the Go containers have the model settings, as in brief 1434's owner steps (names: `UBYHOST_AI_FEATURES` containing `havel` and `leon`, the model key, `UBYHOST_AI_MONTHLY_USD_HAVEL`, `UBYHOST_AI_MONTHLY_USD_LEON`, `UBYHOST_APIFY_TOKEN` (the wizard shows the import step only when it is set), `UBYHOST_SECRET_KEY`, `UBYHOST_MAIL_BACKEND`).
2. In the server `.env`, add to `UBYHOST_GO_PATHS`, inside the double quotes and space-separated: `/havel` `/havel/*` `/apartments/*/leon/setup` `/apartments/*/leon/setup/*`. Look first that the Caddyfile's `path` matcher treats `*` between slashes as one segment (the existing `/payments/qr/*.png` entry works the same way).
3. Run `docker compose up -d`, open `/havel` and a property's Leon setup (`/apartments/<id>/leon/setup`), step through it and send one test message.
4. Rollback: remove the four paths and run `docker compose up -d` again.
