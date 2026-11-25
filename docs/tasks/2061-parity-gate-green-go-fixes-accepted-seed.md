# 2061: Parity gate to green: Go needs-you fix, guest check-mark, ACCEPTED rows, door-code seed

Status: todo
Depends on: 2060 | Branch: claude/nice-hawking-fw98ct | Executor: Haiku 5.5 | 30 tool calls | Tier: B (Go templates, harness, seed)
Run order: 2061 first. 2062 (g-hub-claimed fix and the one full gate) is written after step 6 of this brief reports its finding.

## 1. Objective

The full `scripts/e2e/parity_gate.sh` is red with 38 visible rows. Classification of every row (orchestrator looked at the 1280 en side PNGs, Python left, Go right):

| Case | Class | Cause |
|---|---|---|
| home-host cs/en | REAL | Go lists "Police report not sent" for a stay of a property that has no UbyPort login; Python shows "Nothing needs you today." |
| reservation-detail cs/en 1280 | ACCEPTED (brief 1862) | Go-only desktop layout (`stay-layout`, `stay-rows-group`: crumb above title, Stay rows group, Police reporting last). 2046 already added the arrow and invoice button; nothing new remains. Recorded: `docs/tasks/1862-stay-page-layout.md` section 2 (owner decisions) and `docs/context/decisions.md` line 66. |
| apt-guide-qr cs/en | ACCEPTED (brief 2036) | Python's flex `h2` eats the space ("Newlink"); Go writes `&#160;` before `tip-nowrap` on purpose (`go/internal/web/ai/guide_common.go:79`, `docs/tasks/2036-go-apartment-access-page-report.md` line 13). Only the section title differs. |
| apt-guide-full cs/en | ACCEPTED (2045 + 2051 section 11) | External guide card (2045, same as `apt-guide`), Leon "?" next to the title (2051 section 10, "ACCEPTED"), and the same Python "orAirbnb" spacing as above. |
| guide-item cs/en | ACCEPTED (2051 section 11) | Python has two Save buttons (Save and next card + Save); Go has one by design (design-system rule 5, one Save per form). |
| g-stay-issued-done cs/en | REAL | Check mark: Python `icon('check', 14)` (thin SVG), Go `&#10003;` (heavy glyph). `go/internal/web/guest/templates/stay.tmpl` lines 105 and 143. |
| g-hub-claimed cs/en | REAL, cause not located | Python lists 3 stay rows, Go 2 (same dates). Step 6 finds the cause; 2062 fixes it. |
| Door card on g-stay-issued-done | SEED | See section 2. |

## 2. Context (verified)

- Python needs-you: `App/app/needs_you.py` `stay_line`, inside `if status in _SEND:` the first lines are `if not files: return None`. Go: `go/internal/web/hostweb/dashboard_data.go` `stayLine` (line 884 block `if status == "ready" || status == "awaiting_verification" {`) has no such check, so it prints the amber line. `files` is the function parameter already in scope.
- Python guest check mark: `App/app/templates/guest/stay.html` lines 115 and 154: `<span aria-hidden="true">{{ icon('check', 14) }}</span>`. The icon markup is `<svg class="ui-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false" data-icon="check"><path d="M20 6 9 17l-5-5"/></svg>` (size 14 uses stroke-width 2; `App/app/templates/_icons.html` lines 40 and 52-54).
- Door card. Python `App/app/templates/guest/stay.html` line 66 `{% if door_code %}` sits INSIDE the branch `{% elif remaining is not none and remaining <= 0 %}` (line 46: "all done"). The first branch (line 32) is `{% if expected is none %}`: the "How many people are staying?" picker. `expected` comes from `reporting.reservation_progress` (`App/app/routes/guest.py` line 1532, `remaining` line 1548), which reads `reservation.declared_guests`. `door_codes.view` itself returns the issued code correctly (source manual, lock ttlock, issued row). Go reads the same column (`go/internal/web/guest/pick_data.go` line 148: `SELECT declared_guests, expected_guests_override, lead_reduced_guests FROM reservation`). The seed (`scripts/e2e/seed_parity_guest.py` lines 109 and 124) sets `declared_guests` only on `reservation_claim` (via `set_claim`), never on `reservation`. So expected is none on both sides, both show the picker and neither shows the door card. Fix: also set `reservation.declared_guests` for `res_issued` and `res_issued_done`.
- ACCEPTED dict: `scripts/e2e/parity_cases.py` line 75, `ACCEPTED = {...}`, key = case name without `-cs`/`-en`, value = reason string (used at `scripts/e2e/page_parity_visual.py` line 296).

## 3. Files (you may touch only these)

| File | Action |
|---|---|
| `go/internal/web/hostweb/dashboard_data.go` | edit (step 1) |
| `go/internal/web/hostweb/needs_you_nofiles_test.go` | new (step 1) |
| `go/internal/web/guest/templates/stay.tmpl` | edit (step 2) |
| `scripts/e2e/parity_cases.py` | edit (step 3) |
| `scripts/e2e/seed_parity_guest.py` | edit (step 4) |
| `docs/tasks/2061-report.md` | new |

## 4. Steps (one commit each: `2061 step k`)

### Step 1: Go needs-you, no UbyPort login means no stay line
1. `grep -nF 'return line("amber", t("needs_you.short.ready"' go/internal/web/hostweb/dashboard_data.go` must find one line (about 892). Open lines 880 to 895.
2. Anchor (exactly): 
```
	if status == "ready" || status == "awaiting_verification" {
		mode := r.AutomationMode
```
Replace with:
```
	if status == "ready" || status == "awaiting_verification" {
		if !files {
			return nyLine{}, false
		}
		mode := r.AutomationMode
```
The anchor occurs twice in the file only if the first (line 876) has the same two lines; use the occurrence whose next line is `mode := r.AutomationMode`. Anything else: STOP.
3. Test: `grep -rn "stayLine(" go/internal/web/hostweb/*_test.go | head -3`. Copy the setup of the nearest existing call into the new `go/internal/web/hostweb/needs_you_nofiles_test.go`: status "ready", automation mode manual, `files=false` returns false; `files=true` returns the amber line. If no existing test calls `stayLine`, write the test through the nearest function that does (grep `needsYou` in tests); if none, STOP.
4. Run: `cd go && go test ./internal/web/hostweb/... 2>&1 | tail -30`. Expect `ok`.

### Step 2: Go guest check mark equals Python's
1. `grep -nF '&#10003;' go/internal/web/guest/templates/stay.tmpl` must give lines 105 and 143 only (also check with `grep -c`: 2).
2. On both lines replace `<span aria-hidden="true">&#10003;</span>` with:
`<span aria-hidden="true"><svg class="ui-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false" data-icon="check"><path d="M20 6 9 17l-5-5"/></svg></span>`
Do not touch the `&check;` on the all-done mark (a different element; compare in step 5, do not change here).
3. Run: `cd go && go test ./internal/web/guest/... 2>&1 | tail -30`. Expect `ok`. A test that asserts `&#10003;` fails: update that one assertion to `data-icon="check"`; any other failure: STOP.

### Step 3: ACCEPTED rows (harness)
In `scripts/e2e/parity_cases.py`, find with `grep -nF '"dev-ui":' scripts/e2e/parity_cases.py`. After the `"dev-ui"` entry line (before the closing `}`) add exactly:
```
    "apt-guide-full": "Go keeps the External guide card (2045) and the Leon help mark in the section heading (2051 section 10, accepted); Python lacks the card and has the title spacing quirk (see apt-guide-qr).",
    "apt-guide-qr": "Section title spacing: Python's flex h2 drops the space (New link shown as one word); Go keeps it with a no-break space on purpose (brief 2036, go/internal/web/ai/guide_common.go).",
    "guide-item": "Go has one Save per form (Save and next card, or Save on the last card): design-system rule 5; Python shows two buttons (brief 2051 section 11, accepted).",
    "reservation-detail": "Go-only desktop stay page layout at 1024 px and up (brief 1862, owner decisions 2026-11-19; decisions.md line 66). The back arrow and Generate invoice button already match (brief 2046).",
```
Also extend the existing `"apt-guide"` key? No: leave it. Run: `python3 -c "import ast,sys; ast.parse(open('scripts/e2e/parity_cases.py').read())" 2>&1 | tail -30`. Expect no output.
Note: `reservation-detail` is accepted at all widths by key. Only 1280 differs today; 390 and 768 stay identical and are reported identical, not accepted.

### Step 4: seed so the door card shows on both sides
In `scripts/e2e/seed_parity_guest.py`, find `grep -nF 'db.execute("UPDATE reservation SET registration_completed_at = ? WHERE id = ?", (now, out["res_issued_done"]))' scripts/e2e/seed_parity_guest.py` (line 127). Replace that line with:
```
    db.execute("UPDATE reservation SET registration_completed_at = ?, declared_guests = 1 WHERE id = ?", (now, out["res_issued_done"]))
```
Then find (in function `issued`, after the `set_claim(out["res_issued"], ...)` call, line 109 to 110) the line `    db.insert("guest", {` that follows it (first occurrence after `res_issued`) and insert BEFORE it:
```
    db.execute("UPDATE reservation SET declared_guests = 1 WHERE id = ?", (out["res_issued"],))
```
If `declared_guests` is not a column of `reservation` (the Postgres schema, `grep -n declared_guests App/migrations_pg/*.sql | head -3`), STOP and report the column name that `reporting.reservation_progress` reads (`grep -n "declared_guests" App/app/reporting.py | head -5`).
Run: `source scripts/e2e/parity_env.sh` (alone), then `cd App && PARITY_GROUP=H PARITY_ONLY=g-stay-issued-done-en .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -12`. Open `/var/tmp/parity-visual/g-stay-issued-done-en/g-stay-issued-done-en-390-side.png`. Expect the door-code card ("Door code", 246 810 style PIN) on BOTH sides. If it is on neither: STOP and write what `remaining` is (add no code).

### Step 5: reruns
`PARITY_ONLY='g-stay-issued-done*,home-host*,apt-guide-qr*,apt-guide-full*,guide-item*,reservation-detail*'` with groups A,B,D,F,H (`PARITY_GROUP=A,B,D,F,H`), same command shape as step 4. Expect: home-host, g-stay-issued-done (check mark) identical or invisible; the four accepted cases reported as accepted, 0 visible. If g-stay-issued-done still shows a diff after the door card appears, open the 390 side PNG, describe it in the report (do not fix, 2062 handles it).

### Step 6: g-hub-claimed diagnosis (read-only, no code change)
Python `pick_stay` (`App/app/routes/guest.py` lines 1408 to 1451) lists `_visible_reservations(apartment)` plus claimed incomplete stays; Go `go/internal/web/guest/pick.go` lines 120 to 150 does the same via `mustVisible` and `reservationForGuestExtra` (`pick_data.go` 104). The seed claims `res_claimed` (declared on claim only, see step 4 note). Find which of the seed's stays (unclaimed, provisional, claimed, locked, issued, issued_done, all dated today+10..+13) Python lists and Go omits: compare `_visible_reservations` (`grep -n "def _visible_reservations" -A25 App/app/routes/guest.py`) with `mustVisible` (`grep -n "func mustVisible" -A30 go/internal/web/guest/pick_data.go`) and `_claimed_reservation_ids` with `claimedReservationIDs`. Write the exact differing condition (file:line both sides) in the report. No edit.

## 5. Do not touch
Python code, other templates, the QR-masking config, any ACCEPTED entry that exists, the `&check;` mark, tests other than the ones named.

## 6. Commands (test-map rows)
`cd go && go test ./internal/web/hostweb/... ./internal/web/guest/... 2>&1 | tail -30`; parity reruns in steps 4 and 5; `python3 scripts/context_lint.py 2>&1 | tail -3`. Rule 7: the guest check-mark change needs the g-stay-issued-done 390 screenshot in the report (step 4 or 5 PNG).

## 7. Acceptance
- [ ] home-host cs/en not visible; g-stay-issued-done check mark identical.
- [ ] The door card is in the 390 side PNG on both sides.
- [ ] apt-guide-qr, apt-guide-full, guide-item, reservation-detail reported accepted, 0 visible.
- [ ] Go tests in section 6 pass; step 6 finding written.

## 8. Stop and ask
Any anchor not found verbatim; `declared_guests` not a reservation column; a test other than the named one fails; door card still missing after step 4.

## 9. Report
`docs/tasks/2061-report.md` (600 tokens), then `Status: review`. Do not run the full `parity_gate.sh`. Commit trailers:
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014N5J8NCpdqN2TbR61gYRQf

## 10. Next (2062, orchestrator writes it from your step 6 finding)
Fix the g-hub-claimed row count in Go, rerun H, then run `scripts/e2e/parity_gate.sh` once; expect `GATE: PASS`. Owner confirm wanted on the two "ACCEPTED" calls not stated verbatim by the owner (reservation-detail via 1862, apt-guide-qr via 2036).
