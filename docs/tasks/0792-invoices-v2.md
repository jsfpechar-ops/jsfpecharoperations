# 0792 brief: Faktury (/invoices) list on the v2 look

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
