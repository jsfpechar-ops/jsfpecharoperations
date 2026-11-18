# 1705 report

Status: review

## Commits

- `1705 step 1` — `register_web_properties_all_test.go` (42 routes)
- `1705 step 2` — wave **P Property settings** in `go-cutover-runbook.md`
- `1705 step 3` — this report

## Commands

```
cd go && GOTOOLCHAIN=auto gofmt -l . | tail -5
# (clean)

cd go && GOTOOLCHAIN=auto go test ./internal/web/properties/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/properties	(cached)
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	1.6xxs

python3 scripts/context_lint.py 2>&1 | tail -10
# OK (clean)
```

## Acceptance (§7)

- [x] Completeness test: 42 method+path rows, exact mux patterns (`TestPropertySettingsAllRoutesRegistered`).
- [x] `/entities`, `/apartments`, `/apartments/{id}` GET and POST registrations checked in the table.
- [x] Runbook wave P: narrow selectors, no `/apartments/*` or `/settings/*` wildcards; collisions vs wave 2 exports, wave 7 setup, wave 8 guide; rollback steps.
- [x] `git log --oneline --grep='^1705 step'` shows three step commits; diff only §3 files.

## Accepted differences

- No `docs/tasks/1705-files/` sidecars or sha256 table (brief §2 never landed); inventory taken from live `register_web_properties*` / `register_web_settings*` and `properties/*.go`.
- Wizard: only `POST /apartments/{id}/setup` in the test; GET wizard paths stay wave 7 per runbook P7.
- Smart-lock POST routes remain Python (1707); P1 moves `GET /smart-locks` only.

## Screenshots (host pages)

Not run: paths dormant; UX gate still outstanding (1704 reports). Owner opens pages after first wave-P selector group.

## Left undone

- Owner: follow wave P steps in the runbook; layout lint + 390/768/1280 on Go after first switch.
- `go vet` from brief §6 not run (user command list omitted it).