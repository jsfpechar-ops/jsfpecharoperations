# 1705: Go property settings 6: completeness test, path collisions, rollout wave P

Status: review (exact-diff backfill 2026-11-20: sidecars in `docs/tasks/1705-files/`; Go implementation and runbook wave P already on `main` — executor verifies `MANIFEST.sha256` and reapplies only on a clean worktree).
Depends on: 1700-1704 and 1525/1527 decisions | Base commit: current tip of the working branch | Branch: task/1705-go-property-settings-switch
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: B (Sonnet writes the exact-diff pass; orchestrator reads the diff of the risk-listed files)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1705 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1705 step'`.

## 1. Objective

Add a method-and-path completeness test for the property settings thread and write the wave P steps in the cutover runbook. `POST /entities` (1522) and `POST /apartments` (1700b2) are already registered. Check those handlers and their GET counterparts together before bringing the paths to Go.

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first (no new personal-data field without a `retention.py` line, no new outbound request without a reason in the PR); 3 no secrets, no real data (fixtures use `@example.test`); 4 no new dependency without a decision line; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, a schema change is a new `App/migrations_pg/` file; 6 light mode, every form works without JavaScript (Go forms carry the `_csrf` input); 11 Go first.

**Python source of truth:** `go-full-move-remaining.md` sections 3 and 4; `go/cmd/ubyhost-web/register_web_properties*.go`.

**Routes in scope (method path, Python function):**

- all routes of briefs 1700-1704 plus the existing 1300/1301/1302/1520-1524 routes

Build the test inventory from the Python routes in this thread and match each method to the production Go mux. Reuse the handler-level parity tests in the preceding briefs for response behavior.

Both `deploy/lightsail/caddy/Caddyfile.acme` and `deploy/lightsail/caddy/Caddyfile.cloudflare` select Go by path for every HTTP method. The Python fallback handles only GET and HEAD when Go returns the explicit route-not-ported 501. Include matches under `/apartments/*` from onboarding, bookings and guest-guide routes and matches under `/settings/*` from exports in the collision review. A broad match requires coverage of every Python method it captures. Use narrower selectors for wave P where coverage is incomplete.

**All implementation code is pre-written on `main`.** Sidecars: `docs/tasks/1705-files/<repo path>.txt` (the runbook change is `docs/plans/go-cutover-runbook.md.patch.txt`; apply with `patch -p1` from the repo root). Step 1 copies the test file and applies the patch; never retype or edit them.

| sha256 | file | action |
|---|---|---|
| `93a987c04d360ec5fb4cc44e5d25c77c908427ac4066dac24d9ceadffb9daec7` | `go/cmd/ubyhost-web/register_web_properties_all_test.go` | create |
| `f0a0a8ee9f5567260c72d048a88e550317b46edf977f13500328777a7c472d76` | `docs/plans/go-cutover-runbook.md` | edit (via `.patch`) |

Full manifest: `docs/tasks/1705-files/MANIFEST.sha256`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/cmd/ubyhost-web/register_web_properties_all_test.go` | create | every property route answers on Go for its method |
| `docs/plans/go-cutover-runbook.md` | edit | wave P row and the collision fix |
| `docs/tasks/1705-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1705-report.md` | create | the report (§9) |

No other file may change. Two open briefs naming the same file in §3 run in the order of the dependency overview in [go-sqlite-final](../plans/go-sqlite-final.md).

## 4. Steps

0. Checks (repo root). Anything other than the stated result: STOP (§8). The exact-diff pass fills in the `grep -cF` anchor lines for every file this brief edits and the `ls` line proving the new files do not exist yet.
1. Copy the sidecars to their repo paths and run `sha256sum -c` on the table in §2: all OK.
2. Add the completeness test using the production route registrations. Check the method and the expected matched pattern for each request.
3. Compare the proposed wave P selectors with every Python route they capture in both Caddy configurations. Record the verified selector groups and rollback in the runbook.
4. Run the commands in §6 and record the results and browser evidence in the report.

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file; `handlers.go` and shared `i18n.json` (add new catalog files instead); anything under `App/app/` except what §3 lists; filing code (`go/internal/ubyport`, `App/app/reporting.py`) unless §3 lists it.

## 6. Commands

- `cd go && gofmt -l . | tail -5` prints nothing
- `cd go && go vet ./internal/web/properties/... ./cmd/... 2>&1 | tail -20` is silent
- `cd go && go test ./internal/web/properties/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30` passes, no test skipped
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean
- Host pages: `test_layout_lint_browser.py` green plus one 390, 768 and 1280 px screenshot per page in the report (rule 10).

## 7. Acceptance

- The test fails if a listed method is missing or matches a different route.
- `/entities`, `/apartments` and `/apartments/{id}` each have both a GET and a POST registration. The rollout moves the methods for each path together.
- Every Python route caught by a wave P selector is accounted for by method in the runbook. Paths in other workstreams remain on Python until their Go handlers are ready.
- `git log --oneline --grep='^1705 step'` shows one commit per step; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3 would have to change; a new column, retention line or outbound request is needed; the tests need a skip.

## 9. Report

`docs/tasks/1705-report.md`: commits, command outputs (last 30 lines), accepted differences, screenshots (host pages), what was left undone.

## Rollout wave and rollback

- **Rollout.** After the Go UX check in a test environment, start with verified read-only paths. Wait one day before moving verified write and mixed-method paths. Each selector moves all its methods together. Add only the selectors verified in the runbook.
- **Rollback.** Restore the saved `UBYHOST_GO_PATHS` line and reload Caddy using the runbook commands.

## Owner steps

1. After merge and the layout-lint run, open each page on Go in a test environment.
2. Add the first verified selector group from the runbook and wait one day.
3. Add the next verified selector group and exercise the corresponding forms.
