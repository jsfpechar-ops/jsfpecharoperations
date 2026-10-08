# 0009: TTLock client

Status: todo
Depends on: 0008 | Base commit: after 0008 merges | Branch: task/0009-ttlock-client
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

Create `App/app/ttlock.py`, the only module that talks to TTLock: a guarded HTTP call, the token store, the call budget, and six small API functions. Nothing calls it yet, so there is no visible change. Security rules are enforced by tests, not by comments.

## 2. Context

- Facts: `docs/TTLOCK.md`, all of it (short). Plan: `docs/plans/ttlock-door-codes.md` §7 (budget) and §8.2 (account and never-call list).
- Tables and settings from task 0008: `lock_account`, `lock_api_usage`, `config.DOOR_CODES_ENABLED`, `config.TTLOCK_*`.
- Helpers to reuse (`App/app/db.py`): `query_one`, `execute` (returns the row count), `insert`, `utcnow`, `encrypt_field`, `decrypt_field`. Time zone: `config.TIMEZONE` with `zoneinfo.ZoneInfo`. HTTP: `requests` (already a dependency).
- Rule 3: never log a token, password, PIN, `lockData` or `noKeyPwd`. Log the path, the TTLock `errcode` and ids only.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/ttlock.py` | create | Steps 1 to 5 |
| `App/tests/test_ttlock.py` | create | Step 6 |

No other file may change.

## 4. Steps

1. **Constants and errors.**
   - `ALLOWED_PATHS = frozenset({"/oauth2/token", "/v3/key/list", "/v3/lock/listKeyboardPwd", "/v3/keyboardPwd/get", "/v3/keyboardPwd/change", "/v3/keyboardPwd/delete"})`.
   - `GATEWAY_PATHS = frozenset({"/v3/keyboardPwd/change", "/v3/keyboardPwd/delete"})`.
   - `LOW, NORMAL, CRITICAL = "low", "normal", "critical"` (call priorities).
   - `class TTLockError(Exception)` with attributes `code: Optional[int]`, `kind: str` and `message: str` (TTLock's `errmsg`, at most 200 characters; it never holds secrets).
   - `ERROR_KINDS: Dict[int, str]`, from the table in `docs/TTLOCK.md` "Error codes": 10003 and 10004 → `"auth"`; 10011 → `"reauth"`; 10007 → `"login"`; 10000 and 10001 → `"config"`; 10005, 30001, -2018, 20002 → `"permission"`; 30006 → `"rate"`; 80000 → `"clock"`; -2012 → `"offline"`; -4056 → `"storage"`; 90000 and 1 → `"transient"`; -3 → `"bug"`. Unknown code → `"transient"`. No HTTP answer or bad JSON → `"network"`. Kill switch off → `"disabled"`. Budget refusal → `"budget"`.
2. **`_post(path, data, priority)`**, the single place that sends a request:
   - Raise `ValueError` if `path not in ALLOWED_PATHS`, before anything else.
   - Raise `TTLockError(kind="disabled")` if `not config.DOOR_CODES_ENABLED`.
   - Budget: read this UTC month's (`YYYY-MM`) `lock_api_usage.calls` for provider `ttlock`. With `limit = config.TTLOCK_MONTHLY_CALLS`: at 80 % or more refuse `LOW`; at 95 % or more refuse `NORMAL` too. A refusal raises `TTLockError(kind="budget")` and sends nothing.
   - Count the call before sending: `INSERT INTO lock_api_usage (month, provider, calls) VALUES (?, 'ttlock', 1) ON CONFLICT (month, provider) DO UPDATE SET calls = calls + 1`.
   - Body: for `/oauth2/token`, `{"clientId", "clientSecret"}` plus `data`. For every other path, `{"clientId", "date": <now in ms>}` plus `data`.
   - `requests.post(config.TTLOCK_API_BASE + path, data=body, timeout=...)` with a timeout of 35 s for paths in `GATEWAY_PATHS` (they go through the gateway, and TTLock itself waits up to 30 s, see `docs/TTLOCK.md` "How the gateway fits"), and 5 s for every other path. `requests.RequestException` or a non-JSON answer → `TTLockError(kind="network")`.
   - If the JSON has `errcode` and it is not 0, raise `TTLockError(code, ERROR_KINDS.get(code, "transient"))`. Otherwise return the dict.
   - Log one line per call: path, priority, and `errcode` if any.
3. **Tokens.**
   - `connect(owner_user_id, username, password) -> int`: send `username` and `password=hashlib.md5(password.encode()).hexdigest()` to `/oauth2/token` (`NORMAL`). Upsert `lock_account` (one row per owner and provider) with `access_token_enc`, `refresh_token_enc` (`db.encrypt_field`), `token_expires_at` (now plus `expires_in` seconds, UTC ISO), `token_version` plus 1, `status = 'ok'`. Return the row id. The password and its MD5 are never stored or logged.
   - `_refresh(account) -> str`: remember `v = account["token_version"]`, post `grant_type=refresh_token` and the decrypted refresh token. Then `UPDATE lock_account SET access_token_enc=?, refresh_token_enc=?, token_expires_at=?, token_version=?, updated_at=? WHERE id=? AND token_version=?` with `v + 1` and `v`. If the row count is 0, another process refreshed first: re-read the row and return its access token. On kind `reauth`, set `status = 'reauth_needed'` and re-raise.
   - `_access_token(account_id) -> str`: raise `TTLockError(kind="reauth")` if `status != 'ok'`. Refresh first if `token_expires_at` is less than 7 days away.
   - `_call(account_id, path, data, priority) -> dict`: add `accessToken` and call `_post`. On kind `auth`, refresh once and retry once. A second `auth` error is raised.
4. **Time.** `stay_window(date_from: str, date_to: str, checkin_hour: int, checkout_hour: int) -> Tuple[int, int]`: build `datetime(..., hour, 0, 0, tzinfo=ZoneInfo(config.TIMEZONE))` for both days and return epoch milliseconds. Raise `ValueError` if the end is not after the start, or an hour is outside 0 to 23.
5. **API functions**, each a few lines over `_call`:
   - `list_admin_locks(account_id) -> List[dict]` (`LOW`): page `/v3/key/list` with `pageSize=1000` until `pageNo >= pages`. Keep items with `keyRight == 1` and `str(keyStatus) == "110401"`. Build each item as **only** `{"lock_id": str(lockId), "alias": lockAlias or lockName, "battery": electricQuantity, "tz_offset_ms": timezoneRawOffset, "key_end": endDate}`. Store the list as JSON in `lock_account.locks_json` with `locks_fetched_at`, and return it.
   - `create_period_code(account_id, lock_id, start_ms, end_ms, name, priority=NORMAL) -> Tuple[str, str]`: `ValueError` unless both times are whole hours (`% 3_600_000 == 0`). Post `/v3/keyboardPwd/get` with `lockId=int(lock_id)`, `keyboardPwdType=3`, `keyboardPwdName=name`, `startDate`, `endDate`. Return `(str(keyboardPwd), str(keyboardPwdId))`.
   - `find_code_by_name(account_id, lock_id, name) -> Optional[Tuple[str, str]]` (`NORMAL`): `/v3/lock/listKeyboardPwd` with `searchStr=name`, `orderBy=1`, `pageNo=1`, `pageSize=20`. Return `(pin, code_id)` of the item whose `keyboardPwdName == name` exactly, else `None`.
   - `change_code_period(account_id, lock_id, code_id, start_ms, end_ms, priority=NORMAL) -> None`: same whole-hour check. Post `/v3/keyboardPwd/change` with `keyboardPwdId`, `startDate`, `endDate`, `changeType=2`. No new PIN is ever sent.
   - `delete_code(account_id, lock_id, code_id, priority=CRITICAL) -> None`: `/v3/keyboardPwd/delete` with `deleteType=2`.
   - `calls_this_month() -> int`.
6. **Tests** in `App/tests/test_ttlock.py`. A fixture monkeypatches `app.ttlock.requests.post` with a fake that records `(url, data, timeout)` and pops scripted JSON answers; any unscripted call fails the test. Another fixture sets `DOOR_CODES_ENABLED = True`, dummy client id and secret, and cleans `lock_account` and `lock_api_usage`. Tests, each asserting literal values:
   - `test_paths_outside_the_allowlist_are_refused`: `_post("/v3/lock/detail", {}, NORMAL)` raises `ValueError` with no HTTP call. Also reads the source of `app/ttlock.py` and asserts none of `lock/detail`, `key/get`, `getUnlockLink`, `key/send`, `key/authorize`, `lock/unlock` appears.
   - `test_kill_switch_sends_nothing`.
   - `test_timeouts_are_5_seconds_for_cloud_calls_and_35_for_gateway_calls`: `/v3/keyboardPwd/get` is sent with `timeout=5`, `/v3/keyboardPwd/delete` with `timeout=35`, both as form data.
   - `test_connect_stores_tokens_encrypted_and_never_the_password`: the plain password and its MD5 appear in no `lock_account` column and not in `caplog.text`. The token columns decrypt to the scripted tokens.
   - `test_expired_token_refreshes_once_and_retries` (10004, then refresh, then success: 3 HTTP calls, `token_version` up by 1).
   - `test_a_second_auth_error_is_raised`.
   - `test_dead_refresh_token_marks_the_account_for_reconnect` (10011 → `status == "reauth_needed"`).
   - `test_refresh_race_keeps_the_winner`: bump `token_version` in the database between the read and the update; the stored tokens are the winner's.
   - `test_budget_tiers`: usage at 80 % refuses `LOW` with no HTTP call and allows `NORMAL`; at 95 % refuses `NORMAL` and allows `CRITICAL`. Each sent call adds 1 to `calls_this_month()`.
   - `test_stay_window_across_daylight_saving`: `stay_window("2026-03-28", "2026-03-30", 15, 11)` is `(1774706400000, 1774861200000)` (14:00Z, 09:00Z). Also `("2026-10-24", "2026-10-26", 15, 11)` is `(1792846800000, 1793008800000)` (13:00Z, 10:00Z).
   - `test_code_times_must_be_whole_hours`.
   - `test_pin_keeps_its_leading_zero` (answer `"0563456"`).
   - `test_lock_list_keeps_admin_locks_and_drops_secrets`: scripted items with `lockData`, `noKeyPwd`, one `keyRight: 0`, one `keyStatus: "110405"`. Only the admin, normal lock is returned and stored, and neither secret string appears in `locks_json` or `caplog.text`.
   - `test_change_sends_the_new_window_through_the_gateway`: body has `keyboardPwdId`, `startDate`, `endDate`, `changeType=2`, no `newKeyboardPwd`, and `timeout=35`.
   - `test_error_codes_map_to_kinds` (-2012 `offline`, 80000 `clock`, 30006 `rate`, 12345 `transient`).

   Before writing the two `stay_window` tests, check each expected number with `datetime.fromtimestamp(ms / 1000, ZoneInfo("Europe/Prague"))`. If one does not read 15:00 or 11:00 local time, stop (§8).

## 5. Do not touch

Everything outside §3. No route, template, scheduler job or mail. Do not add `/v3/user/register` (not needed for the pilot).

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests -q` (expected: all pass) and `.venv/bin/python -m pytest tests/test_ttlock.py -q` (expected: 15 passed). From the repo root: `python3 scripts/context_lint.py` (expected last line: `context lint: OK`).

## 7. Acceptance

- [ ] The 15 tests pass, and the full suite passes.
- [ ] `grep -n "requests.post" App/app/ttlock.py` shows exactly one line, inside `_post`.
- [ ] `grep -n "log\." App/app/ttlock.py`: no line logs `data`, `body`, a token, a password or the JSON answer.
- [ ] `git diff --stat` shows only the files in §3.

## 8. Stop and ask

Stop, and write the report, if:

- a name in §2 is not found;
- a test fails twice;
- a `stay_window` expected value does not check out (step 6);
- a new dependency seems needed;
- a file outside §3 needs a change;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/0009-report.md` (1,500 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/ttlock.py`, all of it: `_post`, `_refresh`, `list_admin_locks`.

## Owner steps

None yet. The client id and secret go into the Lightsail `.env` in task 0010, when the connect screen exists.
