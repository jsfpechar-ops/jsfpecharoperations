# 0860 report

Status: review

Files changed: `App/tests/test_host_list_page_layout_browser.py` (only).

Head check: `/invoices` head renders `<a class="btn" href="/invoices/new">` unconditionally (invoices.html line 25), so the none user has one primary action. Test now asserts it.

Change: `test_empty_states_use_the_shared_component`. For `/invoices` the empty block has 0 action links and the head has exactly one. Other three paths unchanged (1 link each).

Command: `cd App && UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_list_page_layout_browser.py -q -rs --tb=short 2>&1 | tail -30`
Result: `5 passed in 6.41s` (0 failed, 0 skipped).

§7: [x] 0 failed, 0 skipped.

Deviations: none. Not committed or pushed (per brief §9).
