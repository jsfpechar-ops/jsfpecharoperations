# 0411: TTLock error codes, gateway check, no-gateway alert

Status: todo
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (may take two; commit per step)

## 1. Objective

Owner (Josef, 2026-10-26): lock 35874326 answers `-2012` ("not connected to any Gateway") and finding out why took an hour of SSH. Three changes, no look change, no new dependency:

1. Permanent TTLock errors stop being retried as "transient" and reach the host.
2. A read-only gateway check (`listByLock`, `detail`) that says whether the cloud sees a gateway for a lock, if it is online and how strong the signal is.
3. A repeated `-2012` raises one alert to the host instead of living only in logs.

## 2. Context

- `App/app/ttlock.py`: `ALLOWED_PATHS`, `GATEWAY_PATHS`, `ERROR_KINDS` (unknown code = `"transient"`), `_post`, `query_lock_time`.
- `App/app/door_codes.py` around lines 560-650: on `TTLockError` it sets FAILED or RETRYING from `exc.kind`; the `taken or via_add` branch and the plain branch each have their own kind tuple. FAILED raises alert `door_code_failed` and calls `mail_notify.door_code_notice`.
- Official codes: [docs/TTLOCK.md "Error codes"](../TTLOCK.md#error-codes). `-3037` means the LOCK is busy (not the gateway). Gateway and lock relation: only exists when lock and gateway belong to the same admin account, cached 30 minutes.
- TTLock docs show GET for the three gateway endpoints. `_post` sends POST like the other calls. If TTLock answers with a method error, STOP and ask.

## 3. Files

| Path | Action |
|---|---|
| App/app/ttlock.py | new error kinds, 3 allowed paths, `gateway_check()` |
| App/app/door_codes.py | add the two new kinds to the FAILED tuples; raise the no-gateway alert |
| App/app/alerts.py, App/app/host_i18n.py, App/app/host_vi_i18n.py | new alert kind `lock_no_gateway` wired like `door_code_failed` (grep it in all three) |
| deploy/lightsail/scripts/ttlock-check.sh | new word `gateway-state ACCOUNT_ID LOCK_ID` |
| App/tests/test_ttlock_errors_0411.py | new |
| docs/TTLOCK.md, docs/OPERATIONS.md ("Alert kinds") | update |

## 4. Steps

1. **Error kinds.** In `ERROR_KINDS` add: `-1003, -2025, -4043, -4037` -> `"lock_unusable"`; `-3006, -2032, -3045` -> `"bad_pin"`; `30008` -> `"config"`. Leave `-3002, -3003, -3036, -3037` unmapped (they retry as transient on purpose). In both kind tuples in `door_codes.py` (the `taken or via_add` branch and the plain branch) add `"lock_unusable"` and `"bad_pin"` next to `"permission"`. Test: each code maps to its kind; a `lock_unusable` error on issue ends FAILED with no retry.
2. **Gateway check.** Add `/v3/gateway/listByLock`, `/v3/gateway/detail` to `ALLOWED_PATHS` (not to `GATEWAY_PATHS`: they do not wake the lock, 5 s timeout). Add `gateway_check(account_id, lock_id) -> dict` returning `{"gateways": [{"id", "name", "rssi", "rssi_age_min"}], "details": [{"id", "online", "lock_num", "version"}]}`: call `listByLock` with `LOW` priority, then `detail` for each gateway id returned (max 3). Never return or log MAC addresses or the network name. Empty list is a normal answer, not an error. Test with `_post` patched.
3. **Alert.** In `door_codes.py`, where a code ends FAILED and `exc.code == -2012`, also `alerts.raise_alert("warning", "lock_no_gateway", ..., dedupe_key=f"lock_no_gateway:{apartment['id']}", apartment_id=apartment["id"], params={"property": apartment["internal_name"]})`. Copy for en, cs, vi: "The door lock cannot be reached. Check that the gateway is powered, online and paired with this lock in the TTLock app." Mirror how `door_code_failed` is wired in `alerts.py`, `host_i18n.py` and `host_vi_i18n.py`. Resolve the alert when a code for that apartment is issued (find where `alerts.resolve(f"door_code_delayed:...")` is called and add the same call). Test: two -2012 failures for one apartment give one open alert; a later issued code resolves it.
4. **Script.** In `ttlock-check.sh` add the case `gateway-state` that runs `ttlock.gateway_check(int(sys.argv[1]), sys.argv[2])` through `docker compose exec -T worker python -c`, printing `gateways found: N`, then per gateway `online yes/no, locks N, signal strong/medium/weak`. Add the word to the usage lines at the top. `bash -n` and shellcheck clean.
5. **Docs.** `docs/TTLOCK.md`: move the "known gap" sentence in the error table into the new kinds (`lock_unusable`, `bad_pin`) and add the two paths to the path list. `docs/OPERATIONS.md` "Alert kinds": add `lock_no_gateway`.

## 5. Do not touch

Storing gateway names/MACs, a new dependency, a new table or migration, changing retry timings, touching `-3037` handling, running `gateway_check` from a page or on a schedule (owner runs it by hand).

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_ttlock_errors_0411.py tests/test_ttlock*.py tests/test_door_code*.py -q --tb=short -x 2>&1 | tail -30`, then `.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_privacy_first.py -q 2>&1 | tail -30` (if `test_host_i18n.py` fails with `no such table`, that is the known isolation bug, see 0394 report: run it alone and say so). From the root: `python3 scripts/context_lint.py | tail -5`, `bash -n deploy/lightsail/scripts/ttlock-check.sh`.

## 7. Acceptance

- [ ] Each new code maps to its kind; the four transient gateway/lock codes still retry
- [ ] `lock_unusable` and `bad_pin` end FAILED with host mail and `door_code_failed` alert, no retry
- [ ] `gateway_check` returns the shape in step 2 and contains no MAC or network name
- [ ] One `lock_no_gateway` alert per apartment, resolved by the next issued code, en/cs/vi copy
- [ ] `ttlock-check.sh gateway-state` documented in the script header and `docs/TTLOCK.md`
- [ ] PR text says: new outbound paths on the existing TTLock host, reason = diagnose `-2012`; no new personal data, so no `retention.py` line
- [ ] Report `docs/tasks/0411-report.md`, one PR, do not merge

## 8. Stop and ask

An anchor is not found, TTLock rejects POST on the gateway paths, `door_code_failed` is wired in a way this brief does not describe, or a test fails twice.

## 9. Report

`docs/tasks/0411-report.md`, 600 tokens at most (executor.md), `Status: review`, one PR, owner merges and deploys. Owner steps after deploy: run `./scripts/ttlock-check.sh gateway-state 3 35874326` and read the answer.
