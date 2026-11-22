# 2036 report

Status: review

## Files changed

`guide_access.go`, `guide/templates/access.tmpl`, `guide_index.go` + `guide_index.tmpl`, `guide_access_test.go`, `guide_index_access_link_test.go`, `guide/i18n_keys.txt`, `guide/i18n.json`, `host_i18n.py`, `guide_i18n.py`, `guide.html`, `havel.py`, `havel_data.go`, `ENVIRONMENT.md`, `test_go_pages_layout_lint_browser.py`.

## Design fix (guide-page shell @390)

- `guide-page` + `guide_section_open/close` and `guide-form-card` (not `settings-lane`).
- KV: `dl.ui-facts`; facts hidden while editing a row; preview uses custom label as `dt` for every type (guest parity).
- `guideSectionOpen`: `&#160;` before `tip-nowrap` so flex h2 keeps “Entry codes” spaced (was “Entrycodes”).
- `app2.css`: `dt` wrap in guide `ui-facts`; `#guest-preview` facts stack at all widths (long labels).
- `BodyKind` `form`; help tips inline in h1/section titles like guide index.

## Commands (tails)

**Go** (`go test -count=1 ./internal/web/ai/ ./cmd/ubyhost-web/ ./internal/apartmententrycode/`):

```
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/ai	24.722s
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	2.495s
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/apartmententrycode	0.002s
```

**Browser** (`UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots2036d`):

```
5 passed, 1 warning in 27.61s
```

**go_host_i18n --check**: exit 0

**context_lint**: `context lint: OK`

## Acceptance (§7)

- [x] Go access tests; no plaintext in responses/audit (covered in `TestAccessSaveTypesAndSecrecy`)
- [x] Name input always rendered; no-JS POST proves server refuses Other without name
- [x] Help section Entry codes (en, cs, vi); `test_guide_coverage.py` green
- [x] Harness: 0 findings, 27 shots (`/opt/cursor/artifacts/2036d/`), 0 skipped
- [x] Guide index link gated on `UBYHOST_GO_ACCESS_PAGE=1`

## Screenshots (`/opt/cursor/artifacts/2036d/` — reviewed)

- **access-three-390** — White cards; section title reads “Entry codes” with inline `?`; three code cards with stacked Type/Code; guest preview lists Gate, Building entrance, Garage with masked codes.
- **access-other-390** — “Entry codes” heading spaced correctly; edit form (Other, long Name, empty Code); preview card shows full custom label wrapping above `••••9`; Host’s guide + notion Change line below.
- **access-other-1280** — Form in left column; preview stacks long custom label (A… B…) over masked code; external host line unchanged.

(Full harness under `/tmp/shots2036d/layout-lint/`.)

## Deviations

- `go/internal/web/ai/guide_common.go` + `App/app/static/app2.css`: section title nbsp and preview `ui-facts` wrap (orchestrator review; brief listed neither).
- `App/app/havel.py` and `go/internal/web/ai/havel_data.go`: `entry-codes` anchor for `test_guide_coverage.py` (test header names these with guide edits).
- Regenerated `go/internal/web/ai/testdata/havel_golden.json` via `App/scripts/havel_golden.py` after `entry-codes` anchor.
- `go_web_harness._seed`: sets `two_factor_prompted_at` so security prompt does not cover lint shots.

## Questions

None.

## Owner steps

Unchanged from brief §9 (list path in `UBYHOST_GO_PATHS`, then `UBYHOST_GO_ACCESS_PAGE=1`).