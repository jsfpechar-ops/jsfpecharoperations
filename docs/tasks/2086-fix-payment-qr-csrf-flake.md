# 2086: Fix random CSRF-token flake in test_guest_qr_page_without_account_explains_in_language

Status: done
Owner: orchestrator

## 1. Objective
Eliminate the 1-in-10,000 random flake in `App/tests/test_payment_rails.py::test_guest_qr_page_without_account_explains_in_language` where the random CSRF token in `<meta name="csrf-token">` can accidentally contain the substring `"paid"`.

## 2. Context
CI run `45525238896` (`postgres full shard 2`) passed 1,592 of 1,593 tests on PR #1319 (`a27ec0ed4`) and failed only on `test_guest_qr_page_without_account_explains_in_language` because `assert "paid" not in page.text.lower()` matched `paid` inside `<meta name="csrf-token" content="...y4yazgxfvxpaidv3...">` in `<head>`.

## 3. Files
- `App/tests/test_payment_rails.py`

## 4. Steps
1. In `App/tests/test_payment_rails.py`, inside `test_guest_qr_page_without_account_explains_in_language`, split out `body = page.text.split("<body", 1)[-1]` and assert `"paid" not in body.lower()`.
2. Run `pytest tests/test_payment_rails.py` on both SQLite and PostgreSQL.

## 5. Do not touch
- `App/app/`
- `go/`

## 6. Commands
- `cd App && .venv/bin/python -m pytest tests/test_payment_rails.py -q --tb=short -x 2>&1 | tail -30`
- `cd App && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5433/guest_test .venv/bin/python -m pytest tests/test_payment_rails.py -q --tb=short -x 2>&1 | tail -30`
- `python3 scripts/context_lint.py 2>&1 | tail -30`

## 7. Acceptance
- `test_payment_rails.py` passes (33 passed) on SQLite and PostgreSQL.
- `python3 scripts/context_lint.py` prints `context lint: OK`.

## 8. Stop and ask
- If any other test in `test_payment_rails.py` fails.

## 9. Report
Write a short report to `docs/tasks/2086-report.md`.
