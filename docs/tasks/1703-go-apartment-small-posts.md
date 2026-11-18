# 1703: Go property settings 4: PIN, link, timing, archive, feeds, sync, police letter, codelists

Status: todo — scoped (final brief 2026-11-15). Executable only after its exact-diff pass: sidecars in `docs/tasks/1703-files/`, anchors and sha256 table (§2), written to the rules in [workflow](../context/workflow.md#writing-briefs-for-haiku). Until then the executor must not start it.
Depends on: 1702e3 | Base commit: current tip of the working branch | Branch: task/1703-go-apartment-small-posts
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: A for filing timing, police connection, police-letter credentials and codelists. The exact-diff pass lists the risk files for review.

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1703 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1703 step'`.

## 1. Objective

Port the five remaining property POSTs for automation timing, adding a calendar feed, testing the police connection, reading a police letter and refreshing police codelists. Keep the changes dormant until 1705.

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first (no new personal-data field without a `retention.py` line, no new outbound request without a reason in the PR); 3 no secrets, no real data (fixtures use `@example.test`); 4 no new dependency without a decision line; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, a schema change is a new `App/migrations_pg/` file; 6 light mode, every form works without JavaScript (Go forms carry the `_csrf` input); 11 Go first.

**Python source of truth:** `admin.py` 3046-3686.

**Routes in scope (method path, Python function):**

| POST path | Behavior to pin in Go tests |
|---|---|
| `/apartments/{id}/automation-timing` | Update only the timing fields. Exercise JSON and form responses, scheduled hour bounds and wizard refusals. |
| `/apartments/{id}/feeds` | Use the Go iCal URL validator and guarded fetch. Exercise duplicate URLs, draft and errors on the property and wizard forms, and the saved-feed outcome when sync fails. |
| `/apartments/{id}/test-connection` | Preserve ownership and form validation, the new-login/old-password lockout guard, the read-only calls and successful verification side effects. Reuse the read-only client used by 1702d2. |
| `/apartments/{id}/police-letter` | Keep the input transient. Pin the JSON and HTML responses and `Cache-Control: no-store`, including invalid input. Use fictional credentials in tests. |
| `/apartments/{id}/refresh-codelists` | Use the existing read-only UbyPort client. Verify persisted code lists and counts on success, plus the failure redirect. |

Existing Go handlers to keep in the 1705 inventory
- `properties.Register` mounts regenerate PIN and link, archive and unarchive, and feed deletion.
- `properties.RegisterSync` mounts `POST /sync`.

Use Go tests with hand-written expectations for the request, response and database state. The [Go-first policy](../context/go-first.md) allows a new Python golden generator only where the exact-diff pass establishes a filing-data need. Record any accepted parity differences in the report.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/properties/apartment_small_posts.go` | create | the POSTs not yet on Go |
| `go/internal/web/properties/apartment_small_posts_test.go` | create | handlers, parity and database tests |
| `go/cmd/ubyhost-web/register_web_properties_apartment_small_posts.go` | create | registers the five routes |
| `go/cmd/ubyhost-web/register_web_properties_apartment_small_posts_test.go` | create | route registration test |
| `docs/tasks/1703-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1703-report.md` | create | the report (§9) |

No other file may change. Two open briefs naming the same file in §3 run in the order of the dependency overview in [go-sqlite-final](../plans/go-sqlite-final.md).

## 4. Steps

0. Checks (repo root). Anything other than the stated result: STOP (§8). The exact-diff pass fills in the `grep -cF` anchor lines for every file this brief edits and the `ls` line proving the new files do not exist yet.
1. Copy the sidecars to their repo paths and run `sha256sum -c` on the table in §2: all OK.
2. Add the handlers and their parity tests from the sidecars. The exact-diff pass records any reused view fields and catalog entries in §3. `gofmt -l` prints nothing.
3. Register the five method-and-path patterns in one new `go/cmd/ubyhost-web/register_web_*.go` file using `init()` and `registerRoutes`. Keep the routes dormant.
4. Run the commands in §6 and write the report.

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file; `handlers.go` and shared `i18n.json` (add new catalog files instead); anything under `App/app/` except what §3 lists; filing code (`go/internal/ubyport`, `App/app/reporting.py`) unless §3 lists it.

## 6. Commands

- `cd go && gofmt -l . | tail -5` prints nothing
- `cd go && go vet ./internal/web/... ./cmd/... 2>&1 | tail -20` is silent
- `cd go && go test ./internal/web/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30` passes, no test skipped
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean
- Host pages: `test_layout_lint_browser.py` green plus one 390, 768 and 1280 px screenshot per page in the report (rule 10).

## 7. Acceptance

- Go tests cover each row in §2, including a success, at least one refusal and a signed-out request with the Python redirect.
- Request tests pin status, headers, response body and any expected database writes. The iCal fetch uses the existing Go `ical` package and its SSRF guard.
- The registration test covers the five new POST patterns and verifies that all five receive requests through the normal mux.
- `git log --oneline --grep='^1703 step'` shows one commit per step; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3 would have to change; a new column, retention line or outbound request is needed; the tests need a skip.

## 9. Report

`docs/tasks/1703-report.md`: commits, command outputs (last 30 lines), accepted differences, screenshots (host pages), what was left undone.

## Rollout wave and rollback

- **Rollout:** Dormant: nothing is added to `UBYHOST_GO_PATHS` by this brief; the switch is brief 1705.
- **Rollback:** Revert the PR.

## Owner steps

None.
