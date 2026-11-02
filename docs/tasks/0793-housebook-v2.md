# 0793 brief: Domovní kniha (/housebook) on the v2 look

Status: in-progress

Executor: Haiku 5.5. Read `AGENTS.md`, `docs/context/executor.md`, then `docs/tasks/0790-records-pages-v2-common.md` (shared rules, tests, report) and follow it.

## Page

- Template: `App/app/templates/housebook.html` (176 lines). CSS block: `/* 0793 housebook v2 (start) */` … `(end)` in `App/app/static/app2.css`. Wrap the body in `<div class="housebook-page">`.
- This is a legal guest register: every column, the CSV/PDF export menu (`housebook_csv_menu`), the PDF export dialog, the archived section with Restore, and the row menu (edit, PDF, delete-to-archive with confirm) must stay and work. Do not change any value or label text.
- Head: h1 = `t('housebook.title')`; `.stays-head-actions` holds the export menu (`housebook_csv_menu(...)`, same arguments) and a ghost button to `/submissions` with `t('nav.reports')` (replaces the old tab strip). No phone add button.
- Filters: keep the filter form (`#housebook-filter-panel`, its toggle and summary, `data-filter-*` attributes) right under the head. Style: one row of fields + Apply/Reset inside a `.card`; same height for the Filters toggle and the export button (audit: 41 vs 36 px).
- Desktop table (>= 1024 px): `<div class="card stays-desk housebook-scroll" tabindex="0" role="region" aria-label="…">` with all 11 columns + actions. The table may be wider than the card: the card scrolls sideways (`overflow-x:auto`) and shows a visible right-edge shadow while more columns are hidden (CSS only, e.g. background-attachment local/scroll gradient trick). Header cells do not wrap (`white-space:nowrap`); badges never cut. Signed/reported badges become pills: signed yes `p-ok`, no `p-warn`; reported `p-ok` (+ date in `<small>`), not required `p-n`, rejected `p-bad`, not sent `p-n`.
- Phone (< 1024 px): `.stays-phone` card per guest: `.sav` = first letter of surname; `b` = surname first name; `small` = stay dates · property; pill = reported state. Href = the row's guest href. The archived section and the guide link get `ph-hide`. The entries count line stays.
- The audit says the table was clipped at 768-1024 px with no scroll cue; below 1024 px the phone cards replace it (same rule as stays), so no extra tablet rules.

## 0710 entry (append to PAGES in App/tests/v2_mockup.py)

`{"name": "housebook", "path": "/housebook", "view": "stays", "phone_view": "pobyty", "phone_mockup": PHONE_MOCKUP_V2, "selectors": [".head h1", ".head .btn.ghost", "main table th", "main table td", "main .pill.p-ok", "main .pill.p-warn"], "phone_selectors": [".tabs", ".tab.on", ".mh .big, .head h1", ".card.stay", ".sav", ".stay .in b", ".stay .in small"], "missing_ok": {"main .pill.p-ok": "tone depends on data", "main .pill.p-warn": "tone depends on data"}}`
Also run `tests/test_host_filter_panels_browser.py` (filter panel behaviour must not change).

## 1. Objective

Restyle the page(s) named above onto the v2 look; no behaviour change.

## 2. Context

See the sections above and docs/tasks/0790-records-pages-v2-common.md.

## 3. Files

Only the files named above, plus this brief's report.

## 4. Steps

Follow the sections above in order.

## 5. Do not touch

base.html, catalog.json, static_versions.json, docs/design/mockup/, other briefs' CSS blocks and templates.

## 6. Commands

From App/: PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest <files> -q --tb=short 2>&1 | tail -30

## 7. Acceptance

The named tests pass with 0 skipped; screenshots at 390 and 1440 px exist.

## 8. Stop and ask

A test outside the standing rule fails, or the tool-call cap comes near: write the report with what is left.

## 9. Report

docs/tasks/<number>-report.md as described in 0790.
