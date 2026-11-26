# 2089 Report — Mobile Calendar Property Index and Single-Property Month View

- Implemented in Go (`go/internal/web/hostweb/mini_calendar.go`, `go/internal/web/hostweb/templates/_calendar_widget.tmpl`, `go/internal/web/hostweb/calendar_i18n.json`).
- On phone (`<768 px`), `/?cal_view=calendar` with 2+ active properties shows an Airbnb-minimal Property List (colored property dot + name + server-rendered 5-week dot/bar SVG with coral today ring; no subtitle, no cross-property toggle).
- Tapping a property opens `/?cal_view=calendar&cal_property={id}` with a 44 px back header and single-property interactive month view; 1-property hosts auto-skip the picker.
- Verified with Go unit tests and Chromium 390/768/1280 layout-lint + geometry tests (including 1-property auto-skip host).
