# Report 1571: Go cleaning event save (create and update)

Status: review. Branch: `cursor/1571-go-cleaning-event-dff7` (re-executor 2026-11-20).

## Files changed (`git show --stat`)

- `go/cmd/ubyhost-web/register_web_cleaning_host_events_test.go` (new, 22 lines)
- `go/internal/web/cleaning/host_events.go` (new, 339 lines)
- `go/internal/web/cleaning/host_events_test.go` (new, 326 lines)
- `docs/tasks/1571-go-cleaning-event-save.md` (Status → review)
- `docs/tasks/1571-report.md` (this file)

Sidecars unchanged; sha256 of the three Go files matches brief §2 on `origin/main`.

## Commands (last 5 lines each)

- Step 1 `sha256sum -c`: all three `: OK`.
- Step 2 `gofmt` / `go build ./...` / `go vet ./internal/web/cleaning/... ./cmd/...`: no output.
- Step 3: **CI only** — no PostgreSQL 16 binaries or `postgres` user in this cloud agent image; steps 4 not run locally.
- `python3 scripts/context_lint.py | grep -v '^WARN'`: `context lint: OK`.

## Acceptance (§7)

- [x] sha256 of the three files matches.
- [x] Format, build and vet silent (step 2).
- [ ] DB tests on PostgreSQL (step 4): deferred to CI (no local PG).
- [x] Go sources already on `main` via merge `8fd8da9ec` (`1571 step 1` / `1571 step 5`); sidecars match.
- [x] No `UBYHOST_GO_PATHS`, Caddy, compose, env or Python change on this PR branch.
- [ ] UI: not applicable (dormant routes).

## Deviations

- Implementation already merged to `main`; rebase dropped duplicate `1571 step 1` (identical sidecars).
- Local executor could not start PG 55570 (brief step 3).

## Questions

None.

## Owner steps left

None until brief 1573 routes `/cleaning/events` to Go.