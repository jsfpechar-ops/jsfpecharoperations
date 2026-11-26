# 2088 Report — 4-step Stay Journey Status Strip

- Implemented in Go (`go/internal/web/stays/journey.go`, `go/internal/hostweb/layout/icon_export.go`, `go/internal/web/staydetail/templates/stay_detail_comfy.tmpl`) with token-only CSS (`App/app/static/comfy.css`).
- Chronological 4-step strip: Link (`mail`) -> Form (`users` + counter) -> Code (`key-round`, hidden without lock/entry code) -> Police (`shield`, hidden without UbyPort or on demo).
- Rendered on `/reservations` (phone cards + desktop rows), Dashboard desktop table + phone rails, and as a labeled horizontal checklist at the top of `/reservations/{id}`.
- Verified zero PIN/code/email leakage, `layout_lint.js` 0 findings, and Chromium 390/768/1280 screenshots.
