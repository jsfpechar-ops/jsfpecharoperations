# 0792 brief: Faktury (/invoices) list on the v2 look

Status: in-progress

Executor: Haiku 5.5. Read `AGENTS.md`, `docs/context/executor.md`, then `docs/tasks/0790-records-pages-v2-common.md` (shared rules, tests, report) and follow it.

## Page

- Template: `App/app/templates/invoices.html` (53 lines). CSS block: `/* 0792 invoices v2 (start) */` … `(end)` in `App/app/static/app2.css`. Only the list page; `invoice_detail.html`, `invoice_form.html`, `invoice_stay_picker.html` are NOT in this brief.
- Head: h1 = `t('invoices.title')`; head primary `btn` "New invoice" (`/invoices/new`, `t('invoice.new')`); phone add button `round stays-add ph-only` to `/invoices/new`. The old second tab (invoice settings, see `page_tabs` for `invoices`) becomes a ghost head button with that tab's label and href.
- Filters: today the toolbar block includes `_list_filter.html`. Put `{% include "_list_filter.html" %}` at the top of the body under the head (keep it working with and without JS). If it renders unstyled on v2, add the minimum rules inside the 0792 block, scoped `body.v2 .invoices-page`; wrap the page body in `<div class="invoices-page">`.
- Desktop table columns stay: number (keep the link), date, customer, kind, total, status, actions (open + PDF button as `a.btn.ghost.sm`). Status pills: paid `p-ok`, unpaid `p-warn`, cancelled `p-n`, other `p-n`. The total stays (it is the invoice's own amount, not a dashboard metric). Keep pagination.
- Phone card: `.sav` = first letter of the customer; `b` = customer; `small` = number · date; pill = status. Same href `/invoices/<id>`. No PDF button on phone (it is on the invoice page).

## 0710 entry (append to PAGES in App/tests/v2_mockup.py)

`{"name": "invoices", "path": "/invoices", "view": "stays", "phone_view": "pobyty", "phone_mockup": PHONE_MOCKUP_V2, "selectors": [".head h1", ".head .btn", ".head .btn.ghost", "main table th", "main table td"], "phone_selectors": [".tabs", ".tab.on", ".mh .big, .head h1", ".stays-add", ".card.stay", ".sav", ".stay .in b", ".stay .in small"], "missing_ok": {}}`
If the rich test host has no invoices, put the table/card selectors in missing_ok with the reason "fixture has no invoice" and say so in the report.

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
