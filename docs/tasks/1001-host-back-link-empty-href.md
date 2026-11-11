# 1001: host page "Back to overview" link has an empty href

Cause: in `App/app/templates/host_page.html` the `ph_back` block reads `page_back`, a `{% set %}` made outside the block. Jinja blocks do not see it, so every host page renders `href=""` and a click reloads the same page (visible on /stay-fees/{id}, also in preview mode).

## Do exactly this
1. In `App/app/templates/host_page.html`, line with `{% block ph_back %}`: replace `href="{{ page_back }}"` with `href="{{ self.back_url() | trim }}"`. Change nothing else (`{% if page_back %}` stays).
2. Add `App/tests/test_1001_back_link_href.py`: reuse `from tests.test_stay_fee_detail import _property, _stay, host  # noqa: F401`; create a property + stay for 2026-08 like `tests/test_design_fees.py`; GET `/stay-fees/{id}?month=2026-08&lang=en`; assert `'class="ui-ph-back airbnb-back" href="/stay-fees?month=2026-08"'` in the HTML.
3. Run from `App/`: `/tmp/claude-0/v/bin/python -m pytest tests/test_1001_back_link_href.py tests/test_design_fees.py -q --tb=short -x 2>&1 | tail -30`.
4. Report: the diff and the test result. Do not touch the Invoices / Invoice settings / Change in Settings chips.
