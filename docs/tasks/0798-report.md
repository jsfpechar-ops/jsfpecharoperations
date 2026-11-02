# 0798 report

Status: blocked (steps 1, 2 partly; 4 not done; geometry rules 1-3 not fixed)

## Files changed (uncommitted)
- App/app/templates/submissions.html, housebook.html, stay_fees.html (copy, rule 6)
- App/app/templates/base.html (cache key app2.css?v=20261102-0798)
- docs/tasks/screenshots-0790/*-390.png, *-1280.png for submissions, invoices, housebook, stay-fees (8 files; overwritten)

## Rule 6 (copy)
- Moved into the page's help body: submissions lede and receipts hint; housebook archived lede and PDF export help and PDF limit warning; stay-fees email status line.
- Deleted: housebook guide link (duplicate of help "more" link); stay-fees QR help line (repeated the amount shown beside it).
- Kept, owner to decide: stay-fees summary line under h1 (#fee-list-summary, counts); stay-fees "send to databox" and "period running" sub lines.

## Commands
1. Browser geometry, 4 pages: 66 passed, 0 skipped (82 s).
2. Static/lint tests: 6 failed. test_static_versions x2 refuses on stale keys in host.css and host2.css (not touched by me; `--write` not applied). test_design_lint: T3 classes missing from catalog (submissions-page, housebook-page, invoices-page, stay-fees-toolbar, stay-fees-page, fee-pay-h, small). test_host_i18n x3: "no such table: apartment", not investigated.
3. context_lint: OK.

## Measure (replaces measure.py, which was not written as a file)
Scratch check ran a copy of the geometry module inside App/tests (deleted after use). Still open at 390/1024/1280/1440:
- R1: help toggle sits 49 px below the h1 on all four pages.
- R2: housebook phone card, text 15 px from top edge. Desktop table cells excluded (scroll container).
- R3: invoices month-step and label touch (gap 0); "Apply filters" and "Cancel" touch the empty-state h2 (gap 0-1).
- R3: stay-fees "Apply filters" 6-7 px from the h1-class title.
Rules 1-4 CSS was not applied (app2.css untouched).

## Not done
Catalog entries (step 4); static-version manifest; screenshots not visually reviewed by me.

## Owner steps left
Decide on the three kept stay-fees lines. Confirm geometry fixes are wanted in this brief before a new executor run.
