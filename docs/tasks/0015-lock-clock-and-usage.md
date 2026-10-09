# 0015: Lock clock check, call counter and budget alerts

Status: done
Depends on: 0014 | Base commit: after 0014 merges | Branch: task/0015-lock-clock-and-usage
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

Once a week UbyHost reads each door-code lock's clock through the gateway and corrects it when it is more than 2 minutes off, because a wrong lock clock makes valid codes fail. The admin Operations page shows how many of the 30,000 monthly TTLock calls are used, and the owner gets one alert at 80 % and one at 95 %.

## 2. Context

- Facts: `docs/TTLOCK.md` "Lock clock" (`/v3/lock/queryDate` returns `date` in ms; `/v3/lock/updateDate` sets the lock to the request's `date` and returns it; both need the gateway) and "How the gateway fits" (35 s, one at a time, worker only).
- `ttlock.py` (task 0009): `ALLOWED_PATHS`, `GATEWAY_PATHS`, `_call(account_id, path, data, priority)`, priorities `LOW` / `NORMAL`, `calls_this_month()`, `config.TTLOCK_MONTHLY_CALLS`. `tests/test_ttlock.py::test_paths_outside_the_allowlist_are_refused` scans the module source for forbidden paths.
- `door_codes.reconcile()` (tasks 0012 to 0014).
- Settings: `db.get_setting(key)`, `db.set_setting(key, value)`.
- Admin Operations: route `operations_admin` in `App/app/routes/admin_accounts.py` (near line 841) renders `admin_operations.html` with `{"ops": admin_ops.overview()}`; `admin_ops.overview()` (`App/app/admin_ops.py` near line 297) returns a dict with keys `filings`, `stuck`, `feeds`, `jobs`, `mail`, `alerts`. Sections look like:
  ```
  <section class="panel tight scroll-x" id="ops-mail">
    <h2 style="margin-top:0">{{ t('ops.mail.title') }} <span class="pill {{ 'amber' if ops.mail.count else 'green' }}">{{ ops.mail.count }}</span></h2>
    <p class="small muted">{{ t('ops.mail.help') }}</p>
  ```
- Alerts: `alerts.raise_alert(...)` with `dedupe_key`; `alerts.SYSTEM_ALERT_KINDS` is a frozenset of kinds that are not tied to a host (`{"job_failed", "turnstile_unavailable"}`). Card text from `notification.<kind>.title` and `notification.reason.<kind>`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/ttlock.py` | edit | Step 1 |
| `App/app/door_codes.py` | edit | Steps 2 and 3 |
| `App/app/alerts.py` | edit | Add `"ttlock_budget"` to `SYSTEM_ALERT_KINDS` only |
| `App/app/admin_ops.py` | edit | Step 4 |
| `App/app/templates/admin_operations.html` | edit | Step 4 |
| `App/app/host_i18n.py` | edit | Step 5 |
| `App/tests/test_lock_clock_and_usage.py` | create | Step 6 |
| `App/tests/test_ttlock.py` | edit | Only if the allowlist test needs the two new paths listed |

No other file may change.

## 4. Steps

1. **Client.** Add `"/v3/lock/queryDate"` and `"/v3/lock/updateDate"` to `ALLOWED_PATHS` and `GATEWAY_PATHS`. Add:
   - `query_lock_time(account_id, lock_id) -> int` (`LOW`): returns `int(answer["date"])`.
   - `adjust_lock_time(account_id, lock_id) -> int` (`NORMAL`): posts `lockId`; `_post` already sends `date` = now in ms; returns `int(answer["date"])`.
2. **Weekly clock check** in `door_codes.py`, `check_lock_clocks() -> dict`, called at the end of `reconcile()`:
   - Locks to check: distinct `(owner_user_id, lock_id)` over apartments with `lock_provider = 'ttlock'` whose owner passes `ttlock.allowed_for` and has an `ok` account.
   - Per lock, setting key `f"ttlock_clock_checked:{lock_id}"`. Check only locks whose setting is missing or older than 7 days, and **at most one lock per run** (gateway calls one at a time; the job runs every minute, so all locks are covered quickly).
   - `drift_ms = query_lock_time(...) - now_ms`. If `abs(drift_ms) > 120_000`, call `adjust_lock_time(...)` and write `db.audit("lock_clock_adjusted", f"lock={lock_id} drift_s={drift_ms // 1000}", actor="system", owner_user_id=owner)`. Then set the setting to now.
   - `TTLockError` of kind `offline`, `transient`, `network`, `rate` or `budget`: set the setting to now minus 6 days (try again tomorrow). Other kinds: raise one alert `door_code_clock` with `dedupe_key=f"door_code_clock:{lock_id}"`, the apartment id of one property using the lock, and `params={"property": <its internal_name>}`; set the setting to now.
   - Return `{"clock_checked": n, "clock_adjusted": m}`.
3. **Budget alerts**, also at the end of `reconcile()`: with `used = ttlock.calls_this_month()` and `limit = config.TTLOCK_MONTHLY_CALLS`, if `used >= 0.8 * limit` raise `alerts.raise_alert("warning", "ttlock_budget", "TTLock calls 80 %", dedupe_key=f"ttlock_budget:{month}:80", params={"percent": 80, "used": used, "limit": limit})`; at `>= 0.95 * limit` the same with level `critical`, `95` in the key and params. `month` is the UTC `YYYY-MM` used by the counter.
4. **Operations page.** `admin_ops.overview()` gets a key `ttlock`: `{"used": ttlock.calls_this_month(), "limit": config.TTLOCK_MONTHLY_CALLS, "issued": <door_code rows issued this month>, "failed": <rows in failed or revoke_failed>, "enabled": config.DOOR_CODES_ENABLED, "live": config.DOOR_CODES_LIVE}`. In `admin_operations.html`, after the `ops-mail` section, add:
   ```
   {% if ops.ttlock.enabled %}
   <section class="panel tight scroll-x" id="ops-ttlock">
     <h2 style="margin-top:0">{{ t('ops.ttlock.title') }} <span class="pill {{ 'amber' if ops.ttlock.used >= ops.ttlock.limit * 0.8 else 'green' }}">{{ ops.ttlock.used }} / {{ ops.ttlock.limit }}</span></h2>
     <p class="small muted">{{ t('ops.ttlock.help') }}</p>
     <p class="small">{{ t('ops.ttlock.counts', issued=ops.ttlock.issued, failed=ops.ttlock.failed) }} · {{ t('ops.ttlock.live') if ops.ttlock.live else t('ops.ttlock.test_mode') }}</p>
   </section>
   {% endif %}
   ```
5. **Strings** (EN, CS):

   | Key | EN | CS |
   |---|---|---|
   | `ops.ttlock.title` | TTLock calls this month | Volání TTLock tento měsíc |
   | `ops.ttlock.help` | The free plan allows 30,000 calls a month for the whole app. | Bezplatný tarif dovoluje 30 000 volání měsíčně pro celou aplikaci. |
   | `ops.ttlock.counts` | Codes issued this month: %(issued)s · failed: %(failed)s | Kódy vydané tento měsíc: %(issued)s · neúspěšné: %(failed)s |
   | `ops.ttlock.live` | Live | Ostrý provoz |
   | `ops.ttlock.test_mode` | Test mode (manual stays only) | Testovací režim (jen ručně přidané pobyty) |
   | `notification.ttlock_budget.title` | TTLock calls: %(percent)s %% of the monthly limit used (%(used)s of %(limit)s). | Volání TTLock: vyčerpáno %(percent)s %% měsíčního limitu (%(used)s z %(limit)s). |
   | `notification.reason.ttlock_budget` | Lock list refreshes and clock checks pause first. New codes keep working until 95 %. | Nejdřív se pozastaví obnovování seznamu zámků a kontrola hodin. Nové kódy fungují až do 95 %. |
   | `notification.door_code_clock.title` | %(property)s: the lock's clock could not be checked. | %(property)s: hodiny zámku se nepodařilo zkontrolovat. |
   | `notification.reason.door_code_clock` | Open the lock in the TTLock app and calibrate its time (Settings, Lock Time). | Otevřete zámek v aplikaci TTLock a zkalibrujte čas (Nastavení, Čas zámku). |

   Follow the existing convention for a literal percent sign in host strings (grep `%%`).
6. **Tests** (`App/tests/test_lock_clock_and_usage.py`), with `ttlock._post` or the two new functions faked:
   - `test_clock_is_checked_once_a_week_per_lock` (two runs: one call; with the setting 8 days old: a second call).
   - `test_only_one_lock_per_run`.
   - `test_small_drift_is_left_alone` (60 s: no adjust call).
   - `test_large_drift_is_corrected_and_audited` (5 min: one adjust call, one `lock_clock_adjusted` audit row with `drift_s=300`).
   - `test_unreachable_lock_is_tried_again_tomorrow`.
   - `test_permission_error_raises_one_alert`.
   - `test_budget_alerts_at_80_and_95_percent` (seed `lock_api_usage`; one alert per threshold per month, no duplicate on a second run).
   - `test_operations_page_shows_the_counter` (admin login as in existing admin tests; `id="ops-ttlock"` and `123 / 30000` present).
   - `test_operations_page_hides_the_counter_when_off`.

## 5. Do not touch

Everything outside §3. Never call `/v3/lock/detail`.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests -q` (all pass), and `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_geometry.py -q -rs` (0 skipped). From the repo root: `python3 scripts/context_lint.py` (last line `context lint: OK`).

## 7. Acceptance

- [ ] The 9 tests in step 6 pass; `tests/test_ttlock.py` passes; the full suite passes.
- [ ] A screenshot of the Operations page section at 1280 px in `docs/tasks/0015-shots/`.
- [ ] The PR description lists the outbound TTLock requests this task adds and why (rule 2).
- [ ] `git diff --stat` shows only the files in §3 plus the screenshot.

## 8. Stop and ask

Stop, and write the report, if:

- a name or excerpt in §2 is not found;
- adding to `SYSTEM_ALERT_KINDS` changes who sees other alerts;
- a test fails twice;
- a new dependency seems needed;
- a file outside §3 needs a change;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/0015-report.md` (1,500 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/ttlock.py` (the two new paths)
- `App/app/door_codes.py` (`check_lock_clocks`)

## Owner steps

None. After this task the production acceptance test in `docs/plans/ttlock-door-codes.md` §12 can start.
