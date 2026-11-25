# 2062 report

Status: review

## Files changed
- `go/internal/web/hostweb/dashboard_data.go`: new `stayRange(lang, from, to)` (Python `stay_range` rules; cs, vi, en default).
- `go/internal/web/hostweb/dashboard.go`: `stay_range` registered in `dashFuncs`; `dash_range` kept.
- `go/internal/web/hostweb/templates/dashboard.tmpl`: lines 66 and 71 use `stay_range $d.Lang`.
- `go/internal/web/hostweb/stay_range_test.go` (new): table test, cs/en/vi, unknown lang, bad date.
- `docs/tasks/2062-report.md`.

## Commands (last lines)
- `go test ./internal/web/hostweb/` : `ok`
- `go test ... -run StayRange -v` : 8 subtests PASS, `ok`
- `page_parity_visual.py` PARITY_ONLY='home-host*' : `{"rows": 6, "verdicts": {"identical": 6, "invisible": 0, "visible": 0, "accepted": 0, "error": 0}}`; server count 0.
- `parity_gate.sh` : `GATE: PASS`; server count 0. Group counts seen in the log: 78, 96, 30, 150, 90, 90, 12, 132, 12 rows; all with visible 0 and error 0 (the log tail was not fully read, so not every group was checked).
- `test_go_pages_layout_lint_browser.py -rs` : `6 passed` (0 skipped, 0 failed).

## Screenshot read-out (390, left Python, right Go)
- g-stay-issued-done cs: both sides show the door-code card (PIN 246810#, active 04.12.2026 14:00 to 07.12.2026 11:00). Identical.
- g-hub-claimed cs: no door-code card on either side. Python shows 3 hub rows (04.12.2026 - 07.12.2026, "To je můj pobyt"); Go shows 2 hub rows. Difference found, not fixed (outside the brief).
- home-host cs: "Další pobyt / Chata / pá 4. – po 7. 12. / Čeká na hosta" on both sides. Identical.

## Visible / error rows
None in the gate output (every verdict visible 0, error 0). Open item: the g-hub-claimed Go list shows 2 rows where Python shows 3 while the gate did not flag it; check the hub-claimed case and its seed.

## Deviations
- Commit trailers use the Opus 5.5 line from the orchestrator instruction.

## Leftover servers
0 `ubyhost-web-parity` processes.
