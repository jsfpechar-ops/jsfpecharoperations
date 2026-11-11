# 1100: host page back link has an empty href

Status: done

## 1. Objective
"Back to overview" on host pages (seen on /stay-fees/{id}, also in preview mode) must navigate, not reload the page.

## 2. Context
In `App/app/templates/host_page.html` the `ph_back` block read `page_back`, a `{% set %}` made outside the block. Jinja blocks do not see it, so the link rendered `href=""`.

## 3. Files
- App/app/templates/host_page.html
- App/tests/test_1100_back_link_href.py

## 4. Steps
1. In the `ph_back` block use `href="{{ self.back_url() | trim }}"`.
2. Test: the stay fee detail page links back to `/stay-fees?month=2026-08`.

## 5. Do not touch
The Invoices / Invoice settings / Change in Settings chips.

## 6. Commands
From `App/`: `.venv/bin/python -m pytest tests/test_1100_back_link_href.py tests/test_design_fees.py -q --tb=short -x 2>&1 | tail -30`

## 7. Acceptance
- [x] Both test files pass (3 passed).

## 8. Stop and ask
If another template overrides `ph_back` with the same problem.

## 9. Report
See docs/tasks/1100-report.md.
