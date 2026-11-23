# 1664 report

Status: review

## Files

`guide_external.go`, `guide_index.go`, `guide_index.tmpl`, `guide/i18n_keys.txt`, `guide/i18n.json`, `stays/i18n.json`, `host_i18n.py`, `host_vi_i18n.py`, `guide_external_test.go`, `test_go_pages_layout_lint_browser.py`.

## Commands (last 5 lines)

**gofmt -l**: (empty)

**go vet**: (clean)

**go test ai + ubyhost-web**: `ok .../ai 24.410s` / `ok .../ubyhost-web 2.577s`

**go_host_i18n.py --check**: (exit 0)

**pytest i18n/copy**: `32 passed, 1 warning in 1.60s`

**pytest layout lint** (`/tmp/shots1664b`): `4 passed, 1 warning in 23.15s`

## §7 acceptance

- [x] Validator/handler tests; domain line assertion on `data-guide-external`.
- [x] Audit detail `host=www.notion.so` only.
- [x] Catalog, i18n/copy rows green.
- [x] Harness 0 findings, 0 skipped.
- [x] Screenshot notes below; Remove link uses `ui_button` **quiet**.

## Screenshots (`/opt/cursor/artifacts/1664/` — review pass)

**Saved 390:** Subline reads “Guests see a link to www.notion.so.”; Save link secondary, Remove link quiet text button.

**Saved 1280:** Same copy at desktop width; domain in subline, quiet Remove beside Save link.

## Deviations

- `flash.error.guide_external_url` ends `….` not `…` so `test_flash_literals` passes (brief had ellipsis only).
- Redirect `?msg=` / `?err=` before `#external` matches `hostweb.Back`.

## Blocked

None.