# 1521: Go port of "Sync now" (POST /sync)

Status: review
Depends on: 1520 (both append to the same catalog files; the catalog sha256 below assumes this order) | Base commit: current branch (One big PR mode) | Branch: current branch
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B

> **One big PR mode.** The owner wants one big pull request. You work on the current branch: commit `1521 step k` after each step that changes a file, never create a branch, never push, never open a PR. The orchestrator merges. Acceptance below does not depend on a base commit: it uses `git log --oneline --grep='^1521 step'` and `git show --stat` on those commits.

## 1. Objective

Port `POST /sync` of `App/app/routes/admin.py`: fetch the signed-in host's iCal calendars now, run the deadline watch for the workspace, and answer with the counted flash. The fetching reuses `ical.SyncFeed`; the owner-scoped loop is a new file in `go/internal/ical/`.

## 2. Context

Files are in the sidecar `docs/tasks/1521-files/`; copy, check, test. **Do not open them.**

| Route | Python | Parity |
|---|---|---|
| `POST /sync` | `sync_now` admin.py 3415-3441, `icalsync.sync_all(owner_user_id=)` icalsync.py 1240-1288, `reporting.check_deadlines` (Go: `calendar.CheckDeadlines`), `_form_return_to` 341-353, `flash_plural` admin_helpers.py 116 | only active feeds of active apartments of this workspace are fetched (another host's feed, a switched-off apartment, a stopped feed are not); paused billing accounts are skipped and not counted; `last_ical_sync` is written; flash `flash.feeds.synced` in its one/few/many form with created/updated/cancelled, plus the error flash `flash.error.feeds_unreadable` when a feed failed; `return_to` (default `/`, fragment dropped) |

**New outbound request: PR text (hard rule 2).** `POST /sync` makes the same request the `ical` job makes every few minutes and Python's `sync_now` makes today: an HTTPS GET of each calendar URL the host entered, through `ical.Fetch` (DNS-resolving safety check, pinned address, redirect limit; the owner's feed URLs are validated when added). Reason: the host pressed "Sync now" and expects the newest bookings. No new host is contacted, no new data is sent. Tests use a local `httptest` server only.

**Paths.** `/sync` (POST only in Python) becomes fully served by Go. Assumption: `/sync` is not in `UBYHOST_GO_PATHS` today, so the route is not live at deploy.

Rules: hard rules 2, 5, 8. The existing `ical.SyncAll` (the job) is not touched.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/ical/syncowner.go` | create | `SyncOwner`: `SyncAll` limited to one owner (new file in the shared `ical` package) |
| `go/internal/web/properties/flashes.go` | create | `pluralFlash` (host_i18n.plural_key rules) |
| `go/internal/web/properties/sync.go` | create | `RegisterSync`, `syncNow` |
| `go/internal/web/properties/sync_test.go` | create | tests |
| `go/cmd/ubyhost-web/register_web_properties_sync.go` | create | `init()` calling `registerRoutes` |
| `go/internal/web/properties/i18n_keys.txt` | edit (append) | the flash keys |
| `go/internal/web/properties/i18n.json` | edit (generated) | catalog |
| `docs/tasks/1521-go-properties-sync.md` | edit | `Status:` line only |
| `docs/tasks/1521-report.md` | create | report |

No other file may change. Live traffic: none changes (`i18n.*` only gain keys; `ical` gains a function nothing calls but the new route).

## 4. Steps

1. Copy the new files:

```bash
mkdir -p go/internal/ical && cp docs/tasks/1521-files/go/internal/ical/syncowner.go.txt go/internal/ical/syncowner.go
mkdir -p go/internal/web/properties && cp docs/tasks/1521-files/go/internal/web/properties/flashes.go.txt go/internal/web/properties/flashes.go
mkdir -p go/internal/web/properties && cp docs/tasks/1521-files/go/internal/web/properties/sync.go.txt go/internal/web/properties/sync.go
mkdir -p go/internal/web/properties && cp docs/tasks/1521-files/go/internal/web/properties/sync_test.go.txt go/internal/web/properties/sync_test.go
mkdir -p go/cmd/ubyhost-web && cp docs/tasks/1521-files/go/cmd/ubyhost-web/register_web_properties_sync.go.txt go/cmd/ubyhost-web/register_web_properties_sync.go
```

2. Check them:

```bash
sha256sum -c <<'SUMS' 2>&1 | tail -12
62024c8c5851b7170b552813a94013d038f9eb16a7b4dfe9ce9e90bc719e9995  go/internal/ical/syncowner.go
f79a7f9de143a59e31b3ef36f5fbf3925b1a50c6be394571236c1e9814882cf7  go/internal/web/properties/flashes.go
37ade83f41a69ff369accab55c4b34cdd7861710af4abdae1366bbe82d6288ed  go/internal/web/properties/sync.go
afe1ac4ee5a64c26fa1a9084c68b6ba3baf1d66a33c8169f7c9eb4a67e65d49f  go/internal/web/properties/sync_test.go
0cdd43f14501e341551a8e383d4cccd833fa167d86357830b96ea5aa5a42dc5b  go/cmd/ubyhost-web/register_web_properties_sync.go
SUMS
```

Expected: 5 lines ending `OK`.

3. Append the keys and regenerate the catalog:

```bash
printf '\n' >> go/internal/web/properties/i18n_keys.txt
cat docs/tasks/1521-files/i18n_keys_append.txt >> go/internal/web/properties/i18n_keys.txt
cd App && .venv/bin/python -c "
import sys; sys.path.insert(0, 'scripts')
from pathlib import Path
import go_host_i18n as g
d = Path('../go/internal/web/properties')
(d / 'i18n.json').write_text(g.render(g.read_keys(d / 'i18n_keys.txt')), encoding='utf-8')
" && cd .. && sha256sum go/internal/web/properties/i18n.json
```

Expected: `a34501e5785a460a5e2262a812dd815056cf56c6d3dee154be189b2ae6b0db97  go/internal/web/properties/i18n.json`. Then commit: `git add go && git commit -q -m "1521 step 3: files and catalog" && git show --stat HEAD | tail -12`.

4. Run §6, write the report, set `Status: review`, commit `1521 step 4`.

## 5. Do not touch

- Read-only: `go/internal/hostweb/`, `go/internal/session/`, `go/internal/jobs/`, `go/cmd/ubyhost-web/main.go`, `go/cmd/ubyhost-web/registry.go`, `go/cmd/ubyhost-web/register_web.go`, `App/tests/conftest.py`, every file under `App/app/`, `App/scripts/`.
- `docs/ENVIRONMENT.md`, `docs/context/status.md`, `test-map.md`, `decisions.md`, `known-issues.md`.
- Nothing is added to `UBYHOST_GO_PATHS` anywhere (deploy files, env docs, tests). Do not edit the sidecar files, `go.mod` or `go.sum`; no `go get`, no `go mod tidy`.
- Hard rules 2, 3, 4, 5, 8 of AGENTS.md. Never push to `main`; never merge; no branch, no PR.

## 6. Commands

From the repo root. The Go tests need PostgreSQL: `export UBYHOST_TEST_DATABASE_URL=postgresql://...` as the owner's environment gives (unset means the database tests skip, which is a stop (§8), not a pass).

```bash
cd go && test -z "$(gofmt -l .)" && go build ./... && go vet ./internal/ical/ ./internal/web/properties/ ./cmd/... 2>&1 | tail -5 && go test -count=1 -v -run 'Plural|SyncNow|SyncOwner' ./internal/web/properties/ 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -10 && go test -count=1 ./internal/web/properties/ ./internal/ical/ ./cmd/ubyhost-web/ 2>&1 | grep -v INFO | tail -6
```

Expected: `--- PASS: TestPluralFlashKey`, `--- PASS: TestSyncNow`, then three `ok` lines (the `ical` package takes about 30 s).

```bash
python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -3
git log --oneline --grep='^1521 step' | tail -10
```

Expected: `context lint: OK`; one commit per step that changed a file.

## 7. Acceptance

- [ ] Step 2: 5 `OK`; step 3: the sha256 given there.
- [ ] `gofmt`, `go vet`, `go build ./...` clean; the §6 tests ran (no skip) and pass.
- [ ] `git log --oneline --grep='^1521 step'` and `git show --stat` of those commits touch only §3 paths.

## 8. Stop and ask

Stop, and write the report, if: a sidecar `sha256sum` or `git apply --check` fails; an anchor is not found; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`, see executor.md); a new dependency seems needed; a file outside §3 needs a change; §5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1521-report.md` (600 tokens at most) and set `Status: review`. It has: the files changed (`git show --stat` of the `1521 step` commits), each command with the last 5 lines of its output, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

- `go/internal/ical/syncowner.go` (copy of the `SyncAll` loop with an owner filter `a.owner_user_id = $1`: check the filter and that `SyncFeed` is called unchanged).
- `go/internal/web/properties/sync.go` (outbound fetch; CSRF, login, then the sync, as Python).

## Owner steps

1. Nothing to deploy yet. `/sync` is its own path: it can go into `UBYHOST_GO_PATHS` without waiting for the other briefs.
2. On staging, press Sync now on `/` and compare the flash with Python.
