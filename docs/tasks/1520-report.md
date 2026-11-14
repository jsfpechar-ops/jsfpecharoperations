# 1520 report

Status: review
Branch: go-wave3 worktree (One big PR mode). Commits: `1520 step 1`, `1520 step 3`, and this `1520 step 4`. Not pushed, no PR.

## Files changed (step commits)
- `go/internal/web/properties/misc.go`, `templates/menu.tmpl`, `misc_test.go`, `more_helpers_test.go` (new)
- `go/cmd/ubyhost-web/register_web_properties_misc.go` (new)
- `go/internal/web/properties/i18n_keys.txt` (appended), `i18n.json` (regenerated)
- `docs/tasks/1520-go-properties-misc.md` (Status line), `docs/tasks/1520-report.md` (new)

## Checks
- Step 2 sha256sum: 5 of 5 OK.
- Step 3 i18n.json sha256 `84b1e603ad739d46f929ac31615deab87b6f1a282b2f4943478d84d7212728b9`: matches.
- Deviation: the generator needed `App/.venv`; created it per the common instructions (`pip install -r requirements.txt -r requirements-dev.txt`), not committed.
- `gofmt -l .` empty; `go build ./...` OK; `go vet` on properties and cmd clean.
- `go test -count=1 -v ./internal/web/properties/ ./cmd/ubyhost-web/` against PostgreSQL 16 on port 5611 (`UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5611/ubyhost_test`): exit 0, both `ok`. All named tests PASS (TestRefererPath, TestDoorCodesEnabled, TestPragueDay, TestMiscRegisterDoesNotTouchThePool, TestDismissAlert, TestDismissAlertInDoubt, TestSmartLocksRedirect, TestMenuPage, plus older tests). Skips: 0.
- `python3 scripts/context_lint.py`: `context lint: OK`.

## Deviations and open points
- None in code. The brief's §8 stop conditions did not trigger.
- D1 (menu badge cleaning reconcile not called) is the brief's known deviation for the reviewer.
- `/menu` screenshot (rule 7) not taken: the Go service cannot run here. Owner step 2 covers it.

## Owner steps left
1. Nothing to deploy yet; paths are not switched.
2. On staging with `/menu` in `UBYHOST_GO_PATHS`, check `/menu` at phone width against Python.

PostgreSQL on port 5611 was stopped and `/var/tmp/pg1520` removed after the run.
