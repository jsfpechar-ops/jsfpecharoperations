# 0182 report

Status: review

Files changed: App/app/templates/_cleaning_screen.html (form removed), App/app/static/cleaning.css (dead .cleaning-period rules pruned, facts grid, 640 px stack), App/app/static/host2.css (dead .cleaning-period rules removed), App/app/templates/base.html and cleaning_shared.html (style keys bumped), App/tests/static_versions.json, App/tests/test_cleaning.py (new absence test), App/tests/test_design_guardrails_browser.py (facts alignment test), docs/tasks/0182-screenshots/.

Commands (last lines):
- design_lint.py: "design lint: OK"
- pytest tests/test_cleaning*.py: 38 passed, 21 skipped (browser tests skipped without env)
- pytest tests/test_cleaning_browser.py with UBYHOST_REQUIRE_BROWSER=1: 21 passed
- pytest test_design_guardrails_browser.py + test_a11y_guard_browser.py with env: 12 passed, 0 skipped
- pytest -k cleaning_card_facts with env: 1 passed
- shots.py: "3 shots, 0 with problems"

Deviations: shots.py needed App/.venv/bin/python and the file was not executable. Style key for cleaning.css is 20261020-0182a-0182 (the plain -0182 key was refused by the static-versions check after the CSS change).

Questions: none.
Owner steps left: review and merge via scripts/merge-pr-on-green.sh. No PR opened, no push.
