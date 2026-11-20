# 1730 report: Go submissions list/detail read parity

Status: review

## Commits

- `1730 step 1` — copy sidecars (15 checksums OK)
- `1730 step 2` — gofmt `visible_text_test.go`
- `1730 step 1: remove accidental ANCHORS copy` — dropped mistaken copy of `docs/tasks/1730-files/ANCHORS.txt` at repo root

## Commands (last lines)

**gofmt / build / vet:** silent.

**go_host_i18n.py --check:** quiet.

**go_go_submissions_reservations_read_golden.py --check:** quiet (not stale).

**pytest tests/test_go_go_submissions_reservations_read_golden.py:** `1 passed in 1.65s`

**go test ./internal/web/submissions/... ./cmd/ubyhost-web/...:** `ok` (both packages).

**TestReadPagesMatchPythonGolden:** `SKIP` — `UBYHOST_TEST_DATABASE_URL` not set in this environment.

**test_design_reports.py + golden:** `4 passed in 2.48s`

**test_layout_lint_browser.py:** `4 passed in 225.57s` (0 skipped).

**context_lint.py:** `context lint: OK` (pre-existing WARN lines only).

## Screenshots (Python host pages; Go routes dormant until wave H)

| Page | 390 | 768 | 1280 |
|---|---|---|---|
| `/submissions` | `docs/tasks/1730-screenshots/submissions-390.png` | …-768.png | …-1280.png |
| `/submissions/{id}` | `docs/tasks/1730-screenshots/submission-detail-390.png` | …-768.png | …-1280.png |

**390 — list:** v2 shell, yellow how-banner, one rejected submission card, bottom tab bar; layout clean.

**390 — detail:** back affordance, outcome rejected, transport-error fixture note, guest section empty state; no horizontal bleed.

## Accepted differences

None.

## §7 acceptance

- [x] Golden file present; pytest golden freshness green; Go parity test skips without DB URL (CI/owner with Postgres)
- [x] Dormant `register_web_submissions.go`; no `UBYHOST_GO_PATHS` change
- [x] Layout lint green; submissions screenshots at 390/768/1280
- [x] `git diff --stat` only §3 paths (+ report/screenshots)

## Owner steps

None for merge. To run DB parity locally: set `UBYHOST_TEST_DATABASE_URL`, then `cd go && go test ./internal/web/submissions/... -count=1` (expect `TestReadPagesMatchPythonGolden` to run, not skip).

## Questions

None.