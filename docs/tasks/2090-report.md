# 2090 Report — Comfy Dashboard Refresh

- Implemented in Go (`go/internal/web/hostweb/property_rails.go`, `go/internal/web/hostweb/dashboard.go`, `go/internal/web/hostweb/templates/dashboard.tmpl`) and token-only CSS (`App/app/static/comfy.css`, `App/app/static/comfy-responsive.css`).
- Replaced phone `.hs` giant avatar carousel with compact swipeable per-property stay rails (~113 px tall cards, card #2 peeking at 390 px, `Calendar ›` link per property, urgency sorting, 5-rail/5-card caps, 1-line empty placeholder).
- Added desktop `Today / Next 7 days` switcher (`?window=today|next7`, auto-defaulting to `next7` when `today` is empty) beside the heading and linked 14-day Gantt property names to `/?cal_view=calendar&cal_property={id}`.
- Verified with Go tests and Chromium 390/768/1280 layout-lint + geometry tests + full visual screenshot review.
