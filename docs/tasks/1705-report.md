# 1705 report

Status: review

## Commits

- `1705 step 1`–`3` already on `main` (PR #1096 / wave exact-diff #1140).
- **This PR:** `1705 step 4` — exact-diff verify (`docs/tasks/1705-files/MANIFEST.sha256`) + refreshed report.

## MANIFEST (step 1)

```
sha256sum go/cmd/ubyhost-web/register_web_properties_all_test.go
93a987c04d360ec5fb4cc44e5d25c77c908427ac4066dac24d9ceadffb9daec7  (matches MANIFEST)
```

Runbook patch sidecar `docs/tasks/1705-files/docs/plans/go-cutover-runbook.md.patch.txt` matches MANIFEST `f0a0a8ee…`; `patch -p1 --dry-run` on `main`: already applied (wave **P** row present).

## Commands (last lines)

```
cd go && gofmt -l . | tail -5
(empty)

cd go && go vet ./internal/web/properties/... ./cmd/... 2>&1 | tail -20
(silent)

cd go && go test ./internal/web/properties/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/properties	0.069s
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	1.704s

python3 scripts/context_lint.py 2>&1 | tail -10
context lint: OK
```

## Acceptance (§7)

- [x] `TestPropertySettingsAllRoutesRegistered`: 42 method+path rows, exact mux patterns.
- [x] `/entities`, `/apartments`, `/apartments/{id}` GET and POST in the table.
- [x] Runbook wave P: narrow selectors; no `/apartments/*` or `/settings/*` wildcards; P1–P7 ordering documented.
- [x] Sidecars under `docs/tasks/1705-files/` unchanged; repo paths match MANIFEST test file.

## Accepted differences

- Reapply skipped: implementation and runbook already on `main`; patch dry-run is no-op.
- Wizard: `POST /apartments/{id}/setup` in the test; GET wizard steps stay wave 7 (runbook P7).
- Smart-lock POST routes remain Python (1707); P1 moves `GET /smart-locks` only.

## Screenshots (host pages)

Not run: paths dormant until owner adds wave-P selectors. After first P1 group: layout lint + 390/768/1280 on Go (rule 10).

## Left undone

- Owner: wave P steps in `docs/plans/go-cutover-runbook.md`; layout lint on Go after switch.