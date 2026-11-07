# 0985 report

Status: review

Files changed (test files only, plus this brief and its report):
- App/tests/test_0970_register_readable_browser.py: dropped unused `settle_motion` import (F401).
- App/tests/test_0976_audience_matrix.py: dropped unused `from app import guest_guide` (F401). Dropped the `cards = ` prefix on the `_go_live(...)` call (F841); the call is kept because it sets up the keys and goes live as a side effect. No assertion added.
- App/tests/test_property_readiness.py: dropped unused `import re` (F401).

Commands:
- `.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841`: "All checks passed!"
- `.venv/bin/python -m pytest tests/test_0976_audience_matrix.py tests/test_property_readiness.py -q --tb=short -rs`: 17 passed, 0 skipped.
- `python3 scripts/context_lint.py`: see commit log.

Deviations: none.
