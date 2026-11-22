# 1664 report

Status: review

## Files

`guide_external.go`, `guide_index.go`, `guide_index.tmpl`, `guide/i18n_keys.txt`, `guide/i18n.json`, `host_i18n.py`, `host_vi_i18n.py`, `guide_external_test.go`, `test_go_pages_layout_lint_browser.py`.

## Commands (last 5 lines)

**gofmt -l**: (empty)

**go vet**: (clean)

**go test Guide|Route**: `ok .../internal/web/ai 6.812s` / `ok .../cmd/ubyhost-web (cached)`

**go_host_i18n.py --check**: (exit 0)

**pytest i18n/copy**: `32 passed, 1 warning in 1.86s`

**pytest layout lint**: `4 passed, 1 warning in 24.56s`

**context_lint.py**: `context lint: OK`

## §7 acceptance

- [x] Validator/handler tests; POST route via `guideAdd`.
- [x] Audit detail `host=www.notion.so` only.
- [x] Catalog, i18n/copy rows green.
- [x] Harness 0 findings, 0 skipped; nine external screenshots.
- [x] Screenshot notes below; design-system: host settings lane, `ui-field`/`ui-form-actions`, ghost remove, help tip, flash banner on error.

## Screenshots (`/opt/cursor/artifacts/1664/`)

**External guide** — 390: empty field and Save link below cards; 768: same plus domain line and Remove link after save; 1280: wide table, external section with error flash and port example in banner.

**Saved** — 390: domain subline “www.notion.so” and Remove link; 768/1280: section sits between Leon-off row and Add card, actions aligned.

**Error** — 390/768/1280: red flash above form, invalid port URL still in field.

## Deviations

- Clear uses plain `<button class="ui-btn ui-btn-ghost">` (`ui_button` has no `name`/`value`).
- `flash.error.guide_external_url` ends `….` not `…` so `test_flash_literals` passes (brief had ellipsis only).
- Redirect `?msg=` / `?err=` before `#external` matches `hostweb.Back` (tests assert suffix `#external`).

## Blocked

None.