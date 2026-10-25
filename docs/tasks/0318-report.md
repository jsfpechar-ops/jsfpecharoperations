# 0318 report

Status: review

Files changed: App/app/guide_i18n.py (en and cs keys), App/app/templates/guide.html (sections list, setup, business section, stay fee, invoices), App/tests/test_guide.py, App/tests/test_guide_browser.py, docs/tasks/screenshots-guide/guide-setup-390.png, guide-business-390.png, guide-stay_fee-390.png, guide-invoices-390.png (new), docs/tasks/0318-report.md.

Commands (last 5 lines):
- `.venv/bin/python -c "...count..."`: 56
- `pytest tests/test_guide.py -k same_keys`: 1 passed
- `pytest tests/test_guide.py -q -x` (after step 11): 3 passed
- `pytest tests/test_guide_browser.py -q -rs`: 2 passed in 6.12s (0 skipped)
- `pytest tests/test_guide.py tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py -q -x`: 30 passed, 1 warning
- `pytest tests/test_design_guardrails_browser.py tests/test_a11y_guard_browser.py -q -rs`: 14 passed in 118.15s (0 skipped)
- `python3 scripts/context_lint.py`: context lint: OK

Section 7 acceptance: ticked (setup order, #business in side nav, stay fee and invoice sections, en and cs key parity, no dashes, four screenshots looked at, browser tests 0 skipped).

Screenshots (one sentence each): setup shows the what and when, Add a property steps, guided setup, trouble list and the five old parts; business shows the operator explanation, five steps and trouble list; stay_fee shows the stay fee intro, Set it up steps, Report and pay steps and trouble list; invoices shows the settings note, six steps and trouble list.

Deviations:
- Step 1 branch creation skipped as instructed; work is on the existing worktree branch.
- Base commit: origin/main is f311d3b, the brief says 92646d3. Not changed in the brief (no other file may change).
- Browser path used chromium-1243 (brief's 1194 does not exist).
- The guide browser test rewrote all screenshots; the unrelated ones (cleaning, finding, glossary, guest_links, stays, overview, settings) were reverted or deleted and not committed.
- Brief section 4 step 1 expected output not checked against a branch; the counts 2 and 0 matched.

Questions: none.

Owner steps left: follow "Add a property" on a staging phone (brief owner step 1), and read "Report and pay a period" against the last real stay-fee month (owner step 2).
