# 1570 report: Go cleaning host pages, part 1

## 1. Files changed

No new file edits this run: brief 1570 is already on `main` (merge `078f5c853`). Sidecars live at `docs/tasks/1570-files/` (9× `.txt`; no `MANIFEST.sha256`). Existing paths per §3 remain the live tree (`host.go` and later briefs extend the same package).

## 2. Commands (last lines)

- Step 0: `host.go` present (expected absent in a greenfield run); Go/Python anchors else OK; 9 sidecars.
- Step 3 (`gofmt`, `go build ./...`, `go vet`): silent.
- Step 5: `ok github.com/.../go/internal/web/cleaning 9.919s`; `ok github.com/.../go/cmd/ubyhost-web 2.518s`.
- Named tests: 9× `--- PASS`; no `SKIP`/`FAIL`.
- `python3 scripts/context_lint.py`: `context lint: OK`.

## 3. Acceptance (§7)

- [x] Sidecar hashes verified on prior merge; not re-copied (would regress later briefs).
- [x] `register_web_cleaning_test.go` already has the three rows removed.
- [x] Format, build, vet silent.
- [x] Both packages `ok`; nine named tests `PASS` on PostgreSQL 16, port 55570.
- [x] Step commits on history: `1570 step 1`, `2`, `6`.
- [x] No `UBYHOST_GO_PATHS`, Caddy, compose, or `App/` change.
- [x] UI: N/A (dormant routes; rule 10 on staging before path switch).

## 4. Deviations

- Implementation pre-merged on `main`; steps 1–2 skipped after verification. PostgreSQL installed in this agent VM for step 5 (brief’s throwaway `55570`).

## 5. Questions

None.

## 6. Owner steps left

None (path switch waits on brief 1573).