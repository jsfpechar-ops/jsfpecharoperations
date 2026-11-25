# 2046: Go stay detail: "Generate invoice" button and back arrow in the stay header

Status: todo
Depends on: nothing (2045 only produced the evidence) | Base commit: HEAD of the branch you start on | Branch: current
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 100k tokens (stop at 25 calls; see section 8)

## 1. Objective

At 1280 px the Python stay page (`/reservations/{id}`) shows, in the header, a back arrow above the title and a "Generate invoice" (or "Invoice N") button next to "Copy guest form link". Go shows neither (evidence: `/var/tmp/parity-visual/reservation-detail-en/reservation-detail-en-1280-side.png`, Python left, Go right). Owner rule: every function Python has, Go must have. Make Go's stay header match Python at 1280. 390 and 768 already match; they must not change.

Decision on section order (owner option 1): keep Go's section order ("Stay" link-row group after Police reporting etc.). Python's order carries no function Go lacks. Request payment is retired (booking and payments are never used); do not port or touch it.

## 2. Context (verified in this checkout)

- Python template `App/app/templates/reservation_detail.html`:
  - line 74 (header, inside `<div class="stay-head-actions">`, after the copy-link button, before the resend-claim form):
    `{% if stay_invoice %}<a class="btn ghost ph-hide" href="/invoices/{{ stay_invoice.id }}">{{ t('invoice.stay.open', number=stay_invoice.number) }}</a>{% else %}<a class="btn ghost ph-hide" href="/invoices/new?reservation_id={{ reservation.id }}">{{ t('invoice.new') }}</a>{% endif %}`
  - line 81 (row menu): same links with class `row-menu-item ph-only`.
  - The button shows ALWAYS (no billing, plan, or archived condition): `stay_invoice` only picks the label and link (`invoices.active_invoice_for_stay`, `App/app/routes/admin.py:4146`). `ph-hide` hides it below 1024 px; `ph-only` shows the menu item only below 1024 px.
  - Back arrow: `partials/settings_back_header.html` line 3, `<a class="airbnb-back" href="{{ href }}" aria-label="{{ t('common.back') }}">{{ icon('arrow-left', 20) }}</a>`, `href=return_to`.
- Go `go/internal/web/staydetail/templates/stay_detail.tmpl`:
  - The arrow markup EXISTS (line 49, `<a class="airbnb-back" href="{{.ReturnTo}}" aria-label="{{t "common.back"}}">{{icon "arrow-left" 20}}</a>`) but task 1862 hides it on desktop with CSS in `App/app/static/app2.css` line 3582: `body.v2 .host-stay-detail.stay-layout .airbnb-header>.airbnb-back,body.v2 .host-stay-detail.stay-layout .airbnb-header>.page-help-wrap{display:none}`, inside a desktop media block that starts at line 3578. `.stay-layout` is set only by the Go template (comment line 3577).
  - Header actions: no invoice button. The invoice link exists only in the row menu (line 96) as `<a class="row-menu-item" ...>` WITHOUT `ph-only`.
  - Go already serves the targets: `GET /invoices/new` (`go/internal/web/invoices/pages_new.go:15`) and `/invoices/{id}`; `StayInvoice` is already loaded (`staydetail/view.go:144`, `types.go:64`). No route work is needed: **no 2047**.
  - i18n: `invoice.new` and `invoice.stay.open` already exist for all languages in `go/internal/web/staydetail/i18n.json` (cs line 45-46, en line 210-211, vi line 375). No new keys.
- Tests: `go/internal/web/staydetail/layout_1862_test.go` (`TestLayout1862Both` asserts substrings of the rendered page), `handlers_test.go`, `panels_test.go`, `view_test.go`. Helper names `renderStay`, `view1862` are used there.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/staydetail/templates/stay_detail.tmpl` | edit | add header invoice button; add `ph-only` to the row-menu invoice item |
| `App/app/static/app2.css` | edit (1 selector) | stop hiding the back arrow on desktop |
| `go/internal/web/staydetail/layout_1862_test.go` | edit | assert the new markup |
| `docs/tasks/2046-report.md` | write | |

CSS is shared with Python (Python pages never carry `.stay-layout`, so the change is Go-only). No other file may change.

## 4. Steps

1. Setup: `git pull --ff-only origin claude/nice-hawking-fw98ct 2>&1 | tail -2`. Check the anchors exist: `grep -nF 'data-stay-header-copy>{{t "host.copy_guest_form_link"}}</button>{{end}}</div>' go/internal/web/staydetail/templates/stay_detail.tmpl | tail -3` prints one line (line 88). Not found: stop.

2. `stay_detail.tmpl`, header button. The line 88 ends with `</button>{{end}}</div>` and the next line begins `  {{if .Reservation.ArchivedAt}}<form method="post" action="/reservations/{{$id}}/unarchive" class="inline ph-hide stay-restore">`. Insert this new line between those two lines (after line 88, at the same two-space indent), i.e. inside `stay-head-actions`, after the `stay-head-cta` div, exactly as Python places it after its CTA block:
```
  {{if .StayInvoice}}<a class="btn ghost ph-hide" href="/invoices/{{.StayInvoice.ID}}">{{t "invoice.stay.open" "number" .StayInvoice.Number}}</a>{{else}}<a class="btn ghost ph-hide" href="/invoices/new?reservation_id={{$id}}">{{t "invoice.new"}}</a>{{end}}
```
   Commit `2046 step 2`.

3. `stay_detail.tmpl`, row menu. Find (anchor, line 96): `{{if .StayInvoice}}<a class="row-menu-item" href="/invoices/{{.StayInvoice.ID}}" role="menuitem">` and replace both `class="row-menu-item"` inside that one line (the `{{if}}` branch and the `{{else}}` branch) with `class="row-menu-item ph-only"`. Result line:
```
        {{if .StayInvoice}}<a class="row-menu-item ph-only" href="/invoices/{{.StayInvoice.ID}}" role="menuitem">{{t "invoice.stay.open" "number" .StayInvoice.Number}}</a>{{else}}<a class="row-menu-item ph-only" href="/invoices/new?reservation_id={{$id}}" role="menuitem">{{t "invoice.new"}}</a>{{end}}
```
   Commit `2046 step 3`.

4. Test. In `layout_1862_test.go`, inside `TestLayout1862Both`, add these two entries to the `want` list (after the `action="/reservations/7/submit"` entry):
```
			`<a class="btn ghost ph-hide" href="/invoices/new?reservation_id=7">`,
			`<a class="row-menu-item ph-only" href="/invoices/new?reservation_id=7"`,
```
   (`view1862` has no `StayInvoice`, so the "new" branch renders; reservation id is 7, as the submit entry shows.) Run: `cd go && go test ./internal/web/staydetail/... 2>&1 | tail -30`. Expect `ok`. Another test in that package fails because it counts `ph-hide` or `btn ghost` occurrences: read its last 30 lines, update that expected count once, rerun; fails again: stop. Commit `2046 step 4`.

5. CSS, the back arrow. In `App/app/static/app2.css` find with `grep -nF "stay-layout .airbnb-header>.airbnb-back,body.v2" App/app/static/app2.css` (line 3582) and replace that one line with these two lines (the arrow is no longer hidden; the help wrap stays hidden as before):
```
  body.v2 .host-stay-detail.stay-layout .airbnb-header>.page-help-wrap{display:none}
  body.v2 .host-stay-detail.stay-layout .airbnb-header>.airbnb-back{grid-column:1/-1;grid-row:1;justify-self:start;margin:0 0 8px}
```
   The grid puts the crumb in row 1 and the title in row 2 (lines 3583-3585). So the arrow shares row 1 with the crumb: change line 3583 `.stay-layout .head .crumb{grid-column:1/-1;grid-row:1;margin:0 0 8px}` to `grid-row:2` and `h1.airbnb-title{...grid-row:2...}` (line 3584) to `grid-row:3`, `#now .sub` (line 3585) `grid-row:3` to `grid-row:4`, and `.stay-head-actions` (line 3586) `grid-row:2` to `grid-row:3`. Do exactly these four number changes and nothing else. Then screenshots (step 6). If the 1280 screenshot shows the arrow overlapping the title or the actions on a different row than the title, undo the number changes (`git checkout App/app/static/app2.css`), apply only the first two replacement lines with `grid-row:1` for the arrow and `margin:0` , try once more; still wrong: revert the CSS fully, keep steps 2 to 4, and say so in the report (the button part is the function; the arrow is cosmetic and breadcrumb "Stays" already navigates back).
   Commit `2046 step 5`.

6. Browser tests and screenshots. Start from `App/`. Per test-map ("Host pages, templates, CSS" and "Any host template, CSS or JS") run each, 0 skipped (`-rs` shows skips):
```
cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_go_pages_layout_lint_browser.py -q --tb=short -x -rs 2>&1 | tail -30
cd App && .venv/bin/python -m pytest tests/test_host_geometry.py tests/test_design_guardrails_browser.py -q --tb=short -x -rs 2>&1 | tail -30
```
   If the stay page is not in `test_go_pages_layout_lint_browser.py`, say so in the report (do not add it). Setup may need `source scripts/e2e/parity_env.sh` first (never pipe a `source`).
   Visual proof: `source scripts/e2e/parity_env.sh` alone; then `cd App && PARITY_GROUP=B PARITY_ONLY=reservation-detail-en .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -12`. Open `/var/tmp/parity-visual/reservation-detail-en/reservation-detail-en-390-side.png` (rule 7: one 390 px screenshot in the report) and `...-1280-side.png`. Expect at 1280: Go now has the arrow and the "Generate invoice" button like Python; copy the 390 and 1280 side PNGs to `docs/tasks/screenshots-2046/` (create it). Whatever differs at 1280 beyond that (section order, "Stay" link rows, Police card look) is accepted Go design: list it in the report, do not fix it.
   Commit `2046 step 6`.

7. Write `docs/tasks/2046-report.md` (up to 600 tokens): files changed, each command with its last 5 lines, one sentence per width on what you saw (390 / 768 / 1280), section 7 ticked, deviations. Then `python3 scripts/context_lint.py 2>&1 | tail -3`. Commit `2046: Go stay header invoice button and back arrow (report)`.

## 5. Do not touch

`App/app/**` except the one CSS file named above, any Python route or template, the invoice handlers, i18n files, `go/internal/web/invoices/**`, payments code. No new dependency.

## 6. Commands

```
cd go && go test ./internal/web/staydetail/... 2>&1 | tail -30
cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_go_pages_layout_lint_browser.py -q --tb=short -x -rs 2>&1 | tail -30
cd App && .venv/bin/python -m pytest tests/test_host_geometry.py tests/test_design_guardrails_browser.py -q --tb=short -x -rs 2>&1 | tail -30
python3 scripts/context_lint.py 2>&1 | tail -3
```
Go is at `/usr/local/go/bin` (`export PATH=/usr/local/go/bin:$PATH` if `go` is not found).

## 7. Acceptance

- [ ] `go test ./internal/web/staydetail/...` ok.
- [ ] The header has the invoice button with Python's exact classes (`btn ghost ph-hide`) and links; the row-menu item has `ph-only`.
- [ ] At 1280 the arrow is visible and does not overlap anything (or the report says it was reverted and why).
- [ ] 390 and 768 unchanged (side PNG shows no new difference); one 390 px screenshot in the report.
- [ ] Layout lint, geometry and guardrail browser tests: 0 skipped, 0 failures.
- [ ] `git status --short | tail -10` shows only section 3 files and the screenshots folder.

## 8. Stop and ask

- An anchor is not found verbatim: stop.
- A browser test fails on a page you did not touch: report it, stop; do not fix.
- The CSS change breaks the 1280 layout twice: revert the CSS, finish the rest, report.
- 25 tool calls used: finish the step, commit, report `Status: blocked` with `Done: steps 1 to k. Left: ...`.

## 9. Report

`docs/tasks/2046-report.md`, then `Status: review`.
