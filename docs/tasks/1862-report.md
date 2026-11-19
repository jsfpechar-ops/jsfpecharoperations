# 1862 report: stay page desktop layout

Branch: `task/1860-1864-stay-page` | Status: **review**

## Files

`go/internal/web/staydetail/`: `displayname.go`, `displayname_test.go`, `layout_1862_test.go` (new); `tpl.go` (one func-map line), `templates/stay_detail.tmpl`, `i18n_keys.txt` + `i18n.json` (`stays.table.stay`, `how.toggle`). `App/app/static/app2.css` (+50: four `@media (min-width:1024px)` blocks). `App/tests/test_1861_stay_detail_go_parity.py` (`neutralise_1862`). Key `app2.css?v=20261119-stay1862`: `App/app/templates/base.html`, `go/internal/hostweb/layout/shell.html`, `testdata/v2_{alerts_hidden,cs_impersonating}.html`, `App/tests/static_versions.json`.

## Commands (last lines)

```
steps 1-7 go vet/test staydetail: ok | gofmt -l: (empty) | i18n --check: exit 0
7b parity (PostgreSQL 16): 3 passed
8-11 CSS scope check: (empty) | removed lines: 0 | stay-layout in reservation_detail.html: 0
13a layout lint (Go serves both stays, 1024 added): 4 passed in 244s
13b: 8 lines "same size None"
13d Python rows (no Go): 232 passed in 355s
13d parity (GOENV): 3 passed
13d geometry (GOENV): FAILED stays/en/1024 "synthetic persistent date-change alert not rendered"
13d go vet/test staydetail, hostweb, cmd/ubyhost-web: ok (DB tests skip: no UBYHOST_TEST_DATABASE_URL)
context lint: OK
```

Every browser run: 0 skipped. The geometry failure is the Go stays list (`/reservations`, routed by `GOENV`), not this page: `origin/main` a734a72f4 fails the same with the same env. Not this brief's.

## §7

- [x] CSS: four blocks only, every selector `.stay-layout`, scope check empty, 0 removed lines.
- [x] 390/768 (+open) pixel-identical (13b).
- [x] Header, menu help, archived Restore, spacing, order, rows, deadline "?" kept: see PR body.
- [x] Lint green 0 skipped; 390/768/1024/1280 opened.
- [x] Go and Python rows green, except the `main` geometry failure above. Context lint green.
- [x] `test_layout_lint_browser.py` not in any commit; no file outside §3 changed by 1862.
- [x] Design-system checklist: PR body.

## PR body (UX gate)

stay-detail. 390: unchanged (back arrow, upper-case name and "?", facts card, fixed Send bar). 768: unchanged. 1024: crumb "Stays > Tomas Novak" above the title-case H1; no arrow, no "?"; Copy guest form link (secondary), Send to UbyPort (primary) and the menu on the H1 row, right-aligned; pill and property · dates under it; Guests with Edit count and + Add a guest right-aligned, clear gap to the table; "Stay" group (Request payment, Stay settings: 56 px rows, icon, bold label, chevron); Police reporting last, hand-filing row inside its card. 1280: same; opened Stay settings and hand-filing content intact (+open).
stay-archived. 390 and 768: unchanged (yellow banner still shown below 1024). 1024: Restore from archive (primary) and the menu on the H1 row, the long name wraps to two lines, no clipping; grey Archived pill kept; no yellow banner; Stay group holds Stay settings only (inactive stays hide Request payment). No Send button before or after in this fixture. 1280: same on one line.
13b: all eight 390/768 comparisons `None`. Pre-existing: the fixed Havel button overlaps a row's chevron in full-page shots, before and after.

Design system (§5): [x] shell, no `<style>`/`style=""`, only colour `#efefeb` (= `.btn.ghost`) [x] one action row: one primary, one secondary, rest in ⋮; phone unchanged [x] each form one Save [x] no fine print; remaining "?" inline [x] 12 px gaps, no truncated label [x] 390, 768, 1024, 1280 checked [x] lint green, 0 skipped [x] keys: none new in `host_i18n.py`; two existing keys added to the Go catalog [ ] CI watched: 1864.

## Deviations

- Step 0: `page-help-wrap` greps 0: `{{page_help "stay"}}` emits it as a direct child of `airbnb-header`, as Python's `help_after`. Proceeded.
- Step 7: the brief's `guests < stay-quick-edit < reports` contradicts §2 (CSS `order`, no DOM move): the test asserts the DOM order `guests < reports < stay-quick-edit`. `stay-row-ic` ≥2 on the normal page, ≥1 archived (Request payment hidden). `renderStay`/`fixedView` reused, not copied (same package).
- Step 7b: `_detail()` found the root by the literal `<div class="host-stay-detail">`; it now applies rule 1's regex first (shared `_ROOT_1862`), else the Go side never reaches the comparison. Ten rules, no eleventh.
- `GOENV`: `UBYHOST_GO_PATHS=/reservations`, `UBYHOST_DATABASE_URL` = `UBYHOST_TEST_DATABASE_URL` = local PostgreSQL 16. i18n script run with `.venv/bin/python`.
- No Go test hunk changed. Commits a7ef19cd6 and c60878563 (DB test fixes) are another agent's, not 1862.

## Questions

Open questions 1-4 unchanged.

## Owner steps

None; see 1864.
