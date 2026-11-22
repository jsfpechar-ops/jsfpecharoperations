# 2036 report

Status: review

## Files changed

`guide_access.go`, `guide/templates/access.tmpl`, `guide_index.go` + `guide_index.tmpl`, `guide_access_test.go`, `guide_index_access_link_test.go`, `guide/i18n_keys.txt`, `guide/i18n.json`, `host_i18n.py`, `guide_i18n.py`, `guide.html`, `havel.py`, `havel_data.go`, `ENVIRONMENT.md`, `test_go_pages_layout_lint_browser.py`.

## Commands (last 5 lines)

**Go** (`go test ./internal/web/ai/... ./cmd/ubyhost-web/ -run 'Guide|Access|Route'`):

```
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/ai	8.441s
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	0.218s
```

**Browser** (`UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots2036`):

```
1 passed, 1 warning in 24.92s
```

**Python** (`test_host_i18n`, `test_guide_coverage`, copy/privacy):

```
41 passed, 1 warning in 8.81s
```

**context_lint**: `context lint: OK`

## Acceptance (§7)

- [x] Go access tests; no plaintext in responses/audit (covered in `TestAccessSaveTypesAndSecrecy`)
- [x] Name input always rendered; no-JS POST proves server refuses Other without name
- [x] Help section Entry codes (en, cs, vi); `test_guide_coverage.py` green
- [x] Harness: 0 findings, 27 shots (`/opt/cursor/artifacts/2036/`), 0 skipped
- [x] Guide index link gated on `UBYHOST_GO_ACCESS_PAGE=1`

## Screenshots (paths under `/opt/cursor/artifacts/2036/`)

- **empty** — 390: Access & guide title with help, Entry codes empty state and Add code visible (security prompt suppressed via `two_factor_prompted_at` on harness user); 768/1280: same structure in narrow column.
- **one** — 390: one stacked row, masked code, Replace/Clear; 768: wider gutters; 1280: Replace/Clear inline right.
- **three** — 390: three rows, no Add; 768: preview heading starts below fold; 1280: guest preview lists Gate, Building, Garage masked.
- **other** — 390: edit form open; 768: long Other label wraps; 1280: replace form + preview with 60-char label and notion.so Change link.
- **expired** — 390/768/1280: amber expired row notice with date.
- **error** — 390/768/1280: add form with Other selected (open form state for validation).
- **replaced** — 390: neutral banner with full replaced notice after POST Replace; masked row shows `••••8`; 1280: same banner above Entry codes card, form closed, row updated.
- **preview-lock** — 390/768/1280: preview shows apartment door line + code; card 3 door status present.
- **preview-nolock** — 390/768/1280: bike room line only, no door card.

## Deviations

- `App/app/havel.py` and `go/internal/web/ai/havel_data.go`: `entry-codes` anchor for `test_guide_coverage.py` (test header names these with guide edits).
- Regenerated `go/internal/web/ai/testdata/havel_golden.json` via `App/scripts/havel_golden.py` after `entry-codes` anchor.
- `go_web_harness._seed`: sets `two_factor_prompted_at` so security prompt does not cover lint shots.

## Questions

None.

## Owner steps

Unchanged from brief §9 (list path in `UBYHOST_GO_PATHS`, then `UBYHOST_GO_ACCESS_PAGE=1`).