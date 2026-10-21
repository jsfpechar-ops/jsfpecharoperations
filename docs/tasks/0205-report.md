# 0205 report (executor: Haiku 5.5)

Status: blocked

## Files changed (steps 1 to 6, one commit each)

- `App/app/push.py`: `refresh()` added (step 1). Commit 434be9b.
- `App/app/routes/push.py`: new, five endpoints and remove form (step 2). Commit 04d3056.
- `App/app/routes/admin.py`: import, include router, Settings context (step 3). Commit 9336ed6.
- `App/app/host_i18n.py`: Settings copy EN and CS (step 4). Commit cf08bfb.
- `App/app/host_vi_i18n.py`: Settings copy VI (step 5). Commit 477e058.
- `App/tests/test_push_routes.py`: new, endpoint tests (step 6). Commit in the same branch.
- `docs/tasks/0205-push-endpoints.md`: Status set to blocked.
- `docs/tasks/0205-report.md`: this report.

`import app.main` passes.

## Commands (§6)

1. `tests/test_push_routes.py tests/test_push.py tests/test_passkeys.py tests/test_flash_literals.py tests/test_host_i18n.py tests/test_no_em_dashes.py`: 1 failed, 100 passed.
   - Failing test: `test_the_test_alert_reaches_this_device_and_is_limited_to_five_an_hour`.
   - Last lines of the error:
     ```
     File "App/app/push.py", line 344, in send_test
       outbox_id = db.insert("push_outbox", {
     sqlite3.IntegrityError: UNIQUE constraint failed: push_outbox.idempotency_key
     ```
   - Cause: `send_test` (0204 code) builds the key as `TEST_KIND:<stamp to the second>:<subscription id>`. Five test sends in one second collide, and `db.insert` has no `ON CONFLICT` guard, so the second send raises. The same would happen in production if two "Send a test" taps land in the same second.
   - Not fixed: the fix belongs in `push.py` `send_test` (the brief names only `refresh()` there), so I stopped rather than change it or the test.
   - Pre-existing (per brief): the 3 `test_host_i18n.py` failures (language endpoint, Vietnamese dashboard, "no such table: apartment") are present and not fixed.
2. `tests/test_security*.py tests/test_auth_*.py`: not run (stopped at step 1 of the failing command).
3. `python3 scripts/context_lint.py`: OK.

## Deviations

Done: steps 1 to 6. Left: the failing test and the `send_test` idempotency key.

## Questions

1. Should `send_test` use a unique key (for example add a random or counter part) or `ON CONFLICT DO NOTHING` like the other insert at push.py line ~295? Either is a small change in `push.py`, outside this brief. Owner or orchestrator decision needed.
2. Should the test be kept as written once that is fixed?

## Owner steps left

None until the question is decided. Then run from `App/`:
`.venv/bin/python -m pytest tests/test_push_routes.py -q --tb=short 2>&1 | tail -30`

## Fix 1

Brief: `docs/tasks/0205-fix-1.md`. Commit `0205-fix-1: random key for each test alert`.

- Change: `App/app/push.py` imports `secrets`; `send_test` key is now `f"{TEST_KIND}:{secrets.token_hex(8)}:{row['id']}"`. `grep -n token_hex` shows one line.
- Command 1 (`test_push_routes`, `test_push`, `test_passkeys`, `test_flash_literals`, `test_no_em_dashes`): `87 passed, 1 warning`.
- Command 2 (`test_host_i18n.py`): `3 failed, 11 passed`. The 3 failures are the known K-T01 set: `test_language_endpoint_sets_cookie_and_rejects_open_redirects`, `test_a_signed_in_dashboard_keeps_vietnamese`, `test_language_endpoint_accepts_vietnamese`.
- Command 3 (`test_security*`, `test_auth_*`): `61 passed, 1 warning`.
- `python3 scripts/context_lint.py`: `context lint: OK`.
- Status: `0205-push-endpoints.md` and `0205-fix-1.md` set to `Status: review`.
- No PR opened, no push (per owner instruction).
