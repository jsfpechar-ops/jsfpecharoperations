# 1171b-fix-2: police login on the test_p1_review apartment fixture

Tier A follow-up to [1171](1171-skip-stays-without-police-details.md). Status: ready.

## §1 Why
CI on PR #959 fails 2 tests in `App/tests/test_p1_review.py` (`test_B_early_arrival_deadline_alert_raised`, `test_C_moved_earlier_moves_the_guest_with_the_stay`): `check_deadlines` returns 0, not 1. Since 1171 a property with a blank `uby_idub`, `uby_ws_user` or `uby_ws_password_enc` gets no `deadline` alert, and the file's `_apt` fixture creates apartments with none of the three. The tests mean a property that files through UbyHost, so the fixture gets the same three values `App/tests/test_deadlines.py` uses. No app code changes.

## §2 Scope
Only the `_apt` helper in `App/tests/test_p1_review.py`.

## §3 Files
- `App/tests/test_p1_review.py`

## §4 Change
Replace exactly:
```python
def _apt(now, mode="manual", owner=None):
    return db.insert("apartment", {"internal_name": "A", "automation_mode": mode, "active": 1,
                                    "created_at": now, "owner_user_id": owner})
```
with:
```python
def _apt(now, mode="manual", owner=None):
    # 1171: a property without its police login is not watched; these tests
    # mean one that files through UbyHost.
    return db.insert("apartment", {"internal_name": "A", "automation_mode": mode, "active": 1,
                                    "created_at": now, "owner_user_id": owner,
                                    "uby_idub": "IDUB-TEST", "uby_ws_user": "ws-test",
                                    "uby_ws_password_enc": db.encrypt_secret("ws-secret")})
```

## §5 Test
From `App/`: `.venv/bin/python -m pytest tests/test_p1_review.py -q --tb=short 2>&1 | tail -30` — all pass. Then `python3 scripts/context_lint.py | tail -5` from the repo root.

## §6 Done when
Only §3 file changed (`git status --short`), tests pass, one commit "1171b-fix-2: police login on p1_review fixture".
