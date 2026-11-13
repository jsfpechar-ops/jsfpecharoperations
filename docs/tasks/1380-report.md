# 1380 report: Go host page layout

Status: review

## 1. Files changed (git diff --stat f55aa98 vs HEAD before report commit)

19 code files plus the report, all in brief §3: App/scripts/go_host_i18n.py (glob edit, 5 lines), App/scripts/go_layout_golden.py, App/tests/test_go_layout_golden.py, go/internal/hostweb/layout/ (layout.go, funcs.go, args.go, py.go, macros_ui.go, macros_components.go, icons.go, shell.html, i18n_keys.txt, i18n.json, layout_test.go, testdata/ x4). Commit `1380 step 2` (e0b101e). Nothing under go/internal/hostweb/*.go, go/cmd/, Jinja templates or App/app/ changed.

## 2. Commands (last lines)

- `sha256sum -c MANIFEST.sha256` (bundle, step 1): 19 of 19 lines `OK`.
- `sha256sum -c` again from repo root after copy (step 2): 19 of 19 lines `OK`.
- `App/scripts/go_host_i18n.py --check`: no output, exit 0.
- `App/scripts/go_layout_golden.py --check`: no output, exit 0.
- `gofmt -l .` empty; `go vet ./internal/hostweb/...` clean; `go test -count=1 -race ./internal/hostweb/...`:
  `ok .../hostweb 1.026s`, `ok .../hostweb/layout 1.678s`.
- `go build ./cmd/ubyhost-web`: no output, exit 0 (binary removed afterwards, not committed).
- §6 cmd 2 (DB test): skipped, no UBYHOST_TEST_DATABASE_URL in this session. CI decides.
- `pytest tests/test_go_layout_golden.py tests/test_go_host_i18n.py -q`: `3 passed in 2.15s`.
- `python3 scripts/context_lint.py`: warnings only (pre-existing test name overlaps, one commit touched App/ after last status.md update), last line `context lint: OK`. `next free: task 1381 | migration 0046`.

## 3. Section 7

- [x] sha256sum all OK; diff limited to §3 files.
- [x] Both generators --check exit 0.
- [x] §6 cmds 1, 3, 4 as expected; go build clean.

## 4. Deviations

None. The step 2 commit message is `1380 step 2` per the brief; step 5 commit follows the same pattern. No push, no PR (executor.md opens a PR, but the owner instructed no push for this run).

## 5. Questions

None.

## 6. Owner steps left

Push branch task/1380-go-host-layout and open a draft PR; wait for CI (DB shell test runs there). Then review and merge with scripts/merge-pr-on-green.sh once green.
