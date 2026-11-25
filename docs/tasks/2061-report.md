# 2061 report

Status: review (partial: tool-call cap reached at step 5; step 6 not completed)

## Steps
- Step 1 (Go needs-you, no UbyPort login): done. `go/internal/web/hostweb/dashboard_data.go` `stayLine` returns no line when `files` is false in the ready/awaiting_verification branch. Test `go/internal/web/hostweb/needs_you_nofiles_test.go` (new). `go test ./internal/web/hostweb/...` ok.
- Step 2 (check mark): done. `go/internal/web/guest/templates/stay.tmpl` both `&#10003;` replaced with the Python icon SVG (data-icon="check"). `go test ./internal/web/guest/...` ok. Parity g-stay-issued-done cs and en: identical at 390/768/1280 (diff_px 0).
- Step 3 (ACCEPTED): done. `scripts/e2e/parity_cases.py` added apt-guide-full, apt-guide-qr, guide-item, reservation-detail (texts from brief). Parses.
- Step 4 (seed): done, not verified visually. `scripts/e2e/seed_parity_guest.py`: `declared_guests = 1` set on reservation res_issued and res_issued_done (column exists in reservation, migrations_pg/00001_baseline.sql:1845). Door card not checked: no 390 PNG was opened in this run.
- Step 5 (reruns, groups A,B,D,F,H): `{"rows": 36, "verdicts": {"identical": 12, "invisible": 0, "visible": 4, "accepted": 20, "error": 0}}`. Report: /var/tmp/parity-visual/report-A-B-D-F-H.md. Parity servers left: 0.
- Step 6 (g-hub-claimed): NOT located. Candidate condition, no verdict yet: Python `_visible_reservations` (App/app/routes/guest.py:769-786) filters status active, not archived, source not demo, date_from in [today, today+window], `c.guest_access_locked_at IS NULL`. Go `mustVisible` (go/internal/web/guest/pick_data.go:137) calls `visibleReservations`, not yet read.

## Visible rows after step 5 (from report file)
- home-host-cs 390 visible /var/tmp/parity-visual/home-host-cs/home-host-cs-390-side.png
- home-host-cs 768 visible /var/tmp/parity-visual/home-host-cs/home-host-cs-768-side.png
- home-host-en 390 visible /var/tmp/parity-visual/home-host-en/home-host-en-390-side.png
- home-host-en 768 visible /var/tmp/parity-visual/home-host-en/home-host-en-768-side.png

## Owner / orchestrator steps left
- Step 6 finding and door-card visual check (open 390 side PNG for g-stay-issued-done-en).
