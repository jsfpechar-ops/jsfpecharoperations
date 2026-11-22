# 2036 report

Status: review

## Files changed

`guide_access.go`, `guide/templates/access.tmpl`, `guide_index.go` + `guide_index.tmpl`, `guide_access_test.go`, `guide_index_access_link_test.go`, `guide/i18n_keys.txt`, `guide/i18n.json`, `host_i18n.py`, `guide_i18n.py`, `guide.html`, `havel.py`, `havel_data.go`, `ENVIRONMENT.md`, `test_go_pages_layout_lint_browser.py`.

## Design fix (guide-page shell @390)

- `guide-page` + `guide_section_open/close` and `guide-form-card` (not `settings-lane`).
- KV: `dl.ui-facts`; facts hidden while editing a row; Other preview uses `Other` + optional short name row.
- `BodyKind` `form`; help tips inline in h1/section titles like guide index.

## Commands (tails)

**Go** (`go test -count=1 ./internal/web/ai/ ./cmd/ubyhost-web/ ./internal/apartmententrycode/`):

```
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/ai	25.806s
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	2.495s
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/apartmententrycode	0.002s
```

**Browser** (`UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots2036c`):

```
5 passed, 1 warning in 28.91s
```

**go_host_i18n --check**: exit 0

**context_lint**: `context lint: OK`

## Acceptance (§7)

- [x] Go access tests; no plaintext in responses/audit (covered in `TestAccessSaveTypesAndSecrecy`)
- [x] Name input always rendered; no-JS POST proves server refuses Other without name
- [x] Help section Entry codes (en, cs, vi); `test_guide_coverage.py` green
- [x] Harness: 0 findings, 27 shots (`/opt/cursor/artifacts/2036c/`), 0 skipped
- [x] Guide index link gated on `UBYHOST_GO_ACCESS_PAGE=1`

## Screenshots (`/opt/cursor/artifacts/2036c/` — reviewed)

- **access-three-390** — Grey page background; white section cards for Entry codes and guest preview. Each code in a nested `guide-form-card`; Type above Code with design gap; small `?` beside title/section headings; Replace/Clear pill actions.
- **access-three-1280** — Same content in guide-page column: three bordered code cards with Replace/Clear on the right; preview section two-column `ui-facts` (Gate / Building / Garage masked).
- **access-other-390** — Edit form only inside white Entry codes card (facts hidden while editing); Type Other, long Name in field; preview shows Other + masked code (long name suppressed in preview for lint); Notion Change link below fold.
- **access-expired-390** — Stacked facts with valid-until `01.01.2020` (dd.mm.yyyy); attention banner “Expired on 01.01.2020…”; Add code in section footer.
- **access-preview-lock-390** — Preview lists Gate masked + “Apartment door / from the lock at check-in”; third section card for door status copy.

(Full harness still captures empty/one/error/replaced/preview-nolock at 390/768/1280 under `/tmp/shots2036c/layout-lint/`.)

## Deviations

- `App/app/havel.py` and `go/internal/web/ai/havel_data.go`: `entry-codes` anchor for `test_guide_coverage.py` (test header names these with guide edits).
- Regenerated `go/internal/web/ai/testdata/havel_golden.json` via `App/scripts/havel_golden.py` after `entry-codes` anchor.
- `go_web_harness._seed`: sets `two_factor_prompted_at` so security prompt does not cover lint shots.

## Questions

None.

## Owner steps

Unchanged from brief §9 (list path in `UBYHOST_GO_PATHS`, then `UBYHOST_GO_ACCESS_PAGE=1`).