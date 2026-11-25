# 2062: Go home page stay dates (short weekday format), parity read-outs, final gate

Status: todo
Executor: Haiku 5.5 (30 tool calls). One PR, draft. May edit only `go/internal/web/hostweb/**` (code, templates, tests). Commit trailers:
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014N5J8NCpdqN2TbR61gYRQf

## 1. Objective
The home-host "Další pobyt" / "Next stay" card shows "pá 4. – po 7. 12." in Python at 390 and 768 but "04.12.2026 – 07.12.2026" in Go. Port Python's date format. Then read two parity PNGs, run the full parity gate once, and run the Go layout lint.

## 2. Context (diagnosis, file:line)
- Python: `App/app/templates/dashboard.html:117` (next-stay card) and `:114` (key-row cards) print `{{ stay_range(res.date_from, res.date_to) }}`. Filter: `App/app/templating.py:385` `stay_range` (uses `_PASS_WEEKDAYS` / `_PASS_MONTHS`, lines 343-360).
- Rules of `stay_range` (unparseable date returns ""):
  - cs same month `pá 4. – po 7. 12.`; cs across months `st 30. 12. – so 2. 1.`
  - en same month `Fri 4 – Mon 7 Dec`; en across `Wed 30 Dec – Sat 2 Jan`
  - vi always `T6 4/12 – T2 7/12`
  - Weekdays cs `po út st čt pá so ne`; en `Mon Tue Wed Thu Fri Sat Sun`; vi `T2 T3 T4 T5 T6 T7 CN`. Months en `Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec`.
  - "same month" means same year and month. Monday is index 0.
- Go: `go/internal/web/hostweb/templates/dashboard.tmpl:66` (key rows) and `:71` (next stay) call `dash_range`, registered at `go/internal/web/hostweb/dashboard.go:37` as `fmtDateRange` (`dashboard_data.go:921`, prints `DD.MM.YYYY – DD.MM.YYYY`). `fmtDateRange` is also used at `dashboard_data.go:863` (needs-you lines): leave that call as is.
- Go host languages: en, cs, vi (`go/internal/web/hostweb/i18n.json`). Any other lang uses en, like Python (`lang if in table else "en"`). Root template data has `$d.Lang` (`dashboard_data.go:90`); `pyDay(s)` (`dashboard_data.go:184`) parses ISO dates.
- Both cards at 390/768 differ in Go; at 1280 the desktop table is already identical.
- See `/var/tmp/parity-visual/home-host-cs/home-host-cs-390-side.png` (left Python, right Go).

## 3. Files
`go/internal/web/hostweb/dashboard_data.go`, `go/internal/web/hostweb/dashboard.go`, `go/internal/web/hostweb/templates/dashboard.tmpl`, new `go/internal/web/hostweb/stay_range_test.go`.

## 4. Steps (one commit each, message `2062 step k`; every command ends `2>&1 | tail -30`)

### Step 1: formatter
Anchor: `grep -nF "func fmtDateRange" go/internal/web/hostweb/dashboard_data.go`. Directly below `fmtDateRange` add `func stayRange(lang, dateFrom, dateTo string) string` implementing exactly the rules in section 2 with `pyDay` and `time.Weekday` (Go Sunday=0: use `(int(t.Weekday())+6)%7` for the Monday-first index). Use `itoa` for numbers (already in the package). Unparseable either date: return "". Languages: switch on lang "cs", "vi", default en tables.
Run: `cd go && go build ./internal/web/hostweb/ 2>&1 | tail -30`. Expect no output.

### Step 2: register and use in the template
In `dashboard.go` add to `dashFuncs` (anchor `"dash_range":          fmtDateRange,`) the line `"stay_range":          stayRange,`. Keep `dash_range`.
In `dashboard.tmpl` replace on line 66 and line 71 only: `{{dash_range .Row.Reservation.DateFrom .Row.Reservation.DateTo}}` with `{{stay_range $d.Lang .Row.Reservation.DateFrom .Row.Reservation.DateTo}}`. If `$d` is not in scope on either line (build or test error "undefined variable"), STOP and report.
Run: `cd go && go test ./internal/web/hostweb/ 2>&1 | tail -30`. If `testdata` golden files fail only on those two date strings, regenerate per the test's own instruction (grep `-update` in `dashboard_test.go`), and check the diff contains only date text.

### Step 3: unit test
New `stay_range_test.go`, table test of `stayRange`:
- cs `2026-12-04`,`2026-12-07` = `pá 4. – po 7. 12.`
- cs `2026-12-30`,`2027-01-02` = `st 30. 12. – so 2. 1.`
- en `2026-12-04`,`2026-12-07` = `Fri 4 – Mon 7 Dec`
- en `2026-12-30`,`2027-01-02` = `Wed 30 Dec – Sat 2 Jan`
- vi `2026-12-04`,`2026-12-07` = `T6 4/12 – T2 7/12`
- unknown lang `de` uses en output; `""` or `bad` date returns "".
Run: `cd go && go test ./internal/web/hostweb/ -run StayRange 2>&1 | tail -30`. Expect ok.

### Step 4: visual read-out (read-only, no code)
Open `/var/tmp/parity-visual/g-stay-issued-done-cs/g-stay-issued-done-cs-390-side.png` and `/var/tmp/parity-visual/g-hub-claimed-cs/g-hub-claimed-cs-390-side.png` (if a path is missing: `ls /var/tmp/parity-visual | grep -E 'issued-done|hub-claimed'`). Report per image, per side (left Python, right Go): is the door-code card shown, does it show a PIN and times, and the number of hub rows. 2 reads only. Change nothing.

### Step 5: home rerun
`source scripts/e2e/parity_env.sh` (alone, never piped), then `cd App && PARITY_GROUP=A PARITY_ONLY='home-host*' .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -12`. Expect home-host cs and en at 390/768 identical or invisible. Open `/var/tmp/parity-visual/home-host-cs/home-host-cs-390-side.png` once and say what the card shows. If the group letter is wrong, grep `home-host` in `scripts/e2e/parity_cases.py`.

### Step 6: full gate (once)
`source scripts/e2e/parity_env.sh` (alone). Then `cd /home/user/jsfpecharoperations && nohup bash scripts/e2e/parity_gate.sh > /var/tmp/parity_gate.log 2>&1 &`. Poll in the foreground at most 6 times: `timeout 590 bash -c 'until grep -q "GATE:" /var/tmp/parity_gate.log; do sleep 20; done'; tail -5 /var/tmp/parity_gate.log`. Expect `GATE: PASS`. If not: list every visible and error row from the report, open at most 6 side PNGs, describe them, fix nothing. Then `ps -eo pid,cmd | grep -c '[u]byhost-web-parity'` must print 0 (else `pkill -f ubyhost-web-parity`, recheck).

### Step 7: layout lint (rules 7 and 10)
`cd App && PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5433/guest_test UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_go_pages_layout_lint_browser.py -q -x -rs 2>&1 | tail -30`. Expect 0 skipped, 0 failed. The parity side PNGs at 390/768/1280 of home-host (steps 5/6) count as the screenshots; in the report write one line per width ("390: ...; 768: ...; 1280: ...").

## 5. Do not touch
Anything under `App/app`, other Go packages, `needs-you` date text (`dashboard_data.go:863`), the parity tool and its cases.

## 6. Commands
Steps 1-7 above only. No full test suite.

## 7. Acceptance
- [ ] `go test ./internal/web/hostweb/` ok; `StayRange` test covers cs and en (and vi).
- [ ] home-host cs/en 390 and 768 identical or invisible.
- [ ] `GATE: PASS` line pasted, parity server count 0.
- [ ] Layout lint 0 skipped, 0 failed.
- [ ] Step 4 read-out written in the report.
- [ ] Only files under `go/internal/web/hostweb/` changed (plus the report).

## 8. Stop and ask
Any anchor missing, `$d` out of scope, a Go test failing twice, or the gate not PASS after the first run: STOP, report `blocked` with the rows.

## 9. Report
`docs/tasks/2062-report.md` per `docs/context/executor.md`.
